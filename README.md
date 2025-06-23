# Meraki Pi-hole DNS Sync

## Project Overview

This project provides a Docker container that regularly fetches client information from the Meraki API for devices with **Fixed IP Assignments (DHCP Reservations)** and pushes them as custom DNS records to a Pi-hole instance. This allows for reliable local DNS resolution of these specific Meraki clients using their configured hostnames.

## Features

*   Fetches client IP information specifically for devices with **Fixed IP Assignments** from specified Meraki networks (or all networks in an organization).
*   Uses the client's description or DHCP hostname from Meraki as the basis for the DNS record.
*   Adds/updates custom DNS records in Pi-hole for these fixed IP clients.
*   Removes stale DNS records from Pi-hole if they are no longer found in Meraki (scoped by a configurable hostname suffix).
*   Runs on a configurable schedule using cron, managed within the Docker container.
*   Configuration via a `config.ini` file for Meraki specifics and script behavior.
*   Securely handles Meraki API key and Pi-hole API key/URL via environment variables (preferred) or `config.ini`.
*   Easy deployment using Docker and `docker-compose.yml`.
*   Logging of actions for monitoring and troubleshooting.

## Directory Structure

```
.
├── app/
│   └── meraki_pihole_sync.py  # Main Python script
├── config/
│   └── config.ini.sample      # Sample configuration file
├── scripts/
│   └── docker-entrypoint.sh   # Docker entrypoint script for cron setup
├── .env.example               # Example environment file for docker-compose
├── Dockerfile
├── docker-compose.yml         # Docker Compose file for easy deployment
└── README.md                  # This file
```

## How it Works

1.  The Docker container starts, and the `docker-entrypoint.sh` script initializes a cron job based on the `CRON_SCHEDULE` environment variable.
2.  At the scheduled time, the `meraki_pihole_sync.py` Python script is executed.
3.  The script reads its configuration:
    *   **Meraki API Key**: From the `MERAKI_API_KEY` environment variable.
    *   **Pi-hole API URL & Key**: Prioritizes `PIHOLE_API_URL` and `PIHOLE_API_KEY` environment variables. If these are not set, it falls back to the values in the `/config/config.ini` file.
    *   **Other Settings**: Meraki Organization ID, specific Network IDs to sync, and the hostname suffix for DNS records are read from `/config/config.ini` (which is mounted from the host).
4.  The script connects to the Meraki API:
    *   It fetches a list of networks for the given organization ID.
    *   If specific `network_ids` are configured, it filters for these. Otherwise, it processes all accessible networks.
    *   For each relevant network, it fetches the list of clients seen recently. **Crucially, it then filters these clients to include only those that have a "Fixed IP Assignment" (DHCP reservation) configured in Meraki, and where the client's current IP matches this fixed assignment.**
5.  The script connects to the Pi-hole API:
    *   It retrieves the current list of custom DNS records to understand the existing state.
6.  The script processes each relevant Meraki client (i.e., those with a valid and matching Fixed IP Assignment):
    *   It identifies a suitable hostname (preferring the client's 'description', then 'dhcpHostname').
    *   It constructs a fully qualified domain name (FQDN) using this hostname and the configured `hostname_suffix` (e.g., `my-device.lan`).
    *   It then checks this FQDN against the records in Pi-hole:
        *   If the record exists with the correct (fixed) IP address, no action is taken.
        *   If the record exists but with a different IP address, the old record is removed, and the new one (with the current fixed IP) is added.
        *   If the record does not exist, it is added to Pi-hole, mapping the hostname to the client's fixed IP.
7.  After processing all relevant Meraki clients, the script performs a cleanup of stale DNS records:
    *   It iterates through the custom DNS records previously fetched from Pi-hole.
    *   If a record's domain matches the `hostname_suffix` (indicating it was likely managed by this script) but was not found in the current list of active Meraki clients **with Fixed IP Assignments**, that record is deleted from Pi-hole.
8.  All actions, errors, and summaries are logged to standard output, which can be viewed via Docker logs.

## Installation

This application is designed to be run using Docker and Docker Compose.

### Prerequisites

*   **Docker and Docker Compose**: Ensure they are installed on your system.
*   **Git**: For cloning this repository.
*   **Meraki API Key**: You'll need an API key from your Meraki Dashboard with at least read access to the organization(s) and network(s) you intend to sync.
*   **Pi-hole Instance**: A running Pi-hole instance. You'll need its IP address or hostname.
*   **Pi-hole API Token**: If your Pi-hole admin interface is password-protected (which is highly recommended), you need the API token. This can be found in your Pi-hole admin dashboard under **Settings -> API / Web interface -> Show API Token** (click the "QR Code" button to reveal it).

### Steps

1.  **Clone the Repository:**
    If you haven't already, clone this repository to your local machine:
    ```bash
    git clone <repository_url> # Replace <repository_url> with the actual URL
    cd <repository_name>     # Replace <repository_name> with the cloned folder name
    ```

2.  **Configure Environment Variables:**
    The application uses a `.env` file (read by `docker-compose`) for sensitive or environment-specific settings.
    Copy the example file:
    ```bash
    cp .env.example .env
    ```
    Now, edit the newly created `.env` file with your actual credentials and settings:
    ```env
    # .env
    MERAKI_API_KEY=your_meraki_api_key_goes_here
    PIHOLE_API_URL=http://your_pihole_ip_or_hostname/admin/api.php
    PIHOLE_API_KEY=your_pihole_api_token_goes_here # Can be left blank if Pi-hole has no password (not recommended)
    CRON_SCHEDULE="15 3 * * *" # Optional: Default is 3:15 AM daily. Customize cron schedule as needed.
    TZ=America/New_York        # Optional: Set to your local timezone (e.g., Europe/London). Defaults to UTC.
    ```
    *   `MERAKI_API_KEY`: **Required.** Your Cisco Meraki Dashboard API key.
    *   `PIHOLE_API_URL`: **Required (if not in config.ini).** Full URL to your Pi-hole API endpoint.
    *   `PIHOLE_API_KEY`: **Required if Pi-hole is password-protected (if not in config.ini).** Your Pi-hole API token.
    *   `CRON_SCHEDULE`: Optional. Sets how often the sync script runs. Uses standard cron format (minute hour day_of_month month day_of_week). Default in `docker-compose.yml` is `0 3 * * *` (3 AM daily).
    *   `TZ`: Optional. Timezone for the container. This affects when cron jobs run according to "local" time. List of valid TZ database names (e.g., `America/Los_Angeles`, `Europe/Berlin`).

3.  **Configure Application Specifics (`config.ini`):**
    The script uses a `config.ini` file for Meraki organization details, network filtering, and hostname formatting. You need to create this file on your host machine, and it will be mounted into the Docker container.
    The `docker-compose.yml` file is set up to look for this configuration at `./config_prod/config.ini` on your host.

    Create the directory and copy the sample configuration:
    ```bash
    mkdir -p config_prod
    cp config/config.ini.sample ./config_prod/config.ini
    ```
    Edit `./config_prod/config.ini` with your settings:
    ```ini
    # ./config_prod/config.ini

    [meraki]
    # Your Meraki Organization ID (Required)
    organization_id = YOUR_MERAKI_ORGANIZATION_ID

    # Comma-separated list of Meraki network IDs to sync. (Optional)
    # Leave empty to attempt to sync clients from all networks in the organization.
    # Example: network_ids = L_123456789012345678,L_987654321098765432
    network_ids =

    [pihole]
    # Fallback if PIHOLE_API_URL environment variable is NOT set.
    # It's STRONGLY recommended to set PIHOLE_API_URL in the .env file instead.
    api_url = http://your_pihole_ip_or_hostname/admin/api.php

    # Fallback if PIHOLE_API_KEY environment variable is NOT set.
    # It's STRONGLY recommended to set PIHOLE_API_KEY in the .env file instead.
    api_key = YOUR_PIHOLE_API_KEY_FALLBACK

    [script]
    # Suffix to append to client hostnames when creating DNS records. (Required)
    # Example: .lan, .home, .yourcustomdomain.local
    # If a client's Meraki name is "my-pc" and suffix is ".lan", DNS record will be "my-pc.lan".
    hostname_suffix = .local

    # This setting is NOT used when running via Docker with cron.
    # It's for standalone script execution if you were to run the Python script directly.
    sync_interval_seconds = 3600
    ```
    *   `organization_id`: **Required.** Find this in your Meraki Dashboard URL (e.g., `nXXX.meraki.com/o/YOUR_ORG_ID/manage/...`).
    *   `network_ids`: Optional. If you want to sync only specific networks, list their IDs here, separated by commas. Network IDs (e.g., `L_xxxxxxxxxxxxxxxxx`) can also be found in the Meraki Dashboard URL when viewing a specific network.
    *   `api_url` & `api_key` (under `[pihole]` section): These are fallbacks. **Prefer setting `PIHOLE_API_URL` and `PIHOLE_API_KEY` in your `.env` file.**
    *   `hostname_suffix`: **Required.** This defines the local domain for your Meraki devices (e.g., `.home.arpa`, `.internal`, `.lan`).

4.  **Build and Run the Docker Container:**
    Once your `.env` file and `./config_prod/config.ini` are prepared, use Docker Compose to build and run the container:
    ```bash
    docker-compose build
    docker-compose up -d
    ```
    This command will:
    *   Build the Docker image using the `Dockerfile` if it doesn't exist or if files have changed.
    *   Start the container in detached mode (`-d`), meaning it runs in the background.
    *   The container will automatically start the cron service, and your sync script will run based on the `CRON_SCHEDULE`.

## Usage

### Viewing Logs

To monitor the script's activity, check for errors, or see when syncs occur:
```bash
docker-compose logs -f meraki-pihole-sync
```
(If you changed the service name in `docker-compose.yml`, use that name instead of `meraki-pihole-sync`).

The cron daemon also logs its own activity to `/var/log/cron.log` inside the container. You can view this with:
```bash
docker-compose exec meraki-pihole-sync tail -f /var/log/cron.log
```

### Stopping the Container

To stop the running service:
```bash
docker-compose down
```
This will stop and remove the container. Your configuration files (`.env`, `./config_prod/config.ini`) and the Docker image will remain.

### Forcing a Sync (Manual Script Execution)

If you want to trigger a sync immediately for testing or other reasons, without waiting for the cron schedule:
```bash
docker-compose exec meraki-pihole-sync python meraki_pihole_sync.py --config /config/config.ini
```
This command executes the Python script directly within the running container. It will use all the environment variables and the mounted `config.ini` that the container is already configured with.

## Configuration Summary

The script's behavior is controlled by a combination of environment variables (via `.env` and `docker-compose.yml`) and the `config.ini` file.

| Setting                 | Primary Control Method                                 | File(s) Involved              | Python Script Source Priority                                   | Notes                                                                 |
|-------------------------|--------------------------------------------------------|-------------------------------|-----------------------------------------------------------------|-----------------------------------------------------------------------|
| **Meraki API Key**      | `MERAKI_API_KEY` environment variable                  | `.env`                        | 1. Environment Variable (`MERAKI_API_KEY`)                      | **Required.**                                                         |
| **Pi-hole API URL**     | `PIHOLE_API_URL` environment variable                  | `.env`                        | 1. Environment Variable (`PIHOLE_API_URL`) <br> 2. `config.ini` | **Required.** Env var preferred.                                      |
|                         | `api_url` key in `[pihole]` section of `config.ini`    | `./config_prod/config.ini`    |                                                                 | Fallback if env var not set.                                          |
| **Pi-hole API Key**     | `PIHOLE_API_KEY` environment variable                  | `.env`                        | 1. Environment Variable (`PIHOLE_API_KEY`) <br> 2. `config.ini` | **Required if Pi-hole is password-protected.** Env var preferred.     |
|                         | `api_key` key in `[pihole]` section of `config.ini`    | `./config_prod/config.ini`    |                                                                 | Fallback if env var not set.                                          |
| **Cron Schedule**       | `CRON_SCHEDULE` environment variable                   | `.env`                        | `docker-entrypoint.sh` reads this                               | Defines sync frequency.                                               |
| **Timezone**            | `TZ` environment variable                              | `.env`                        | Container's system environment                                  | Affects cron job timing relative to local time.                     |
| **Meraki Org ID**       | `organization_id` key in `[meraki]` section            | `./config_prod/config.ini`    | `config.ini`                                                    | **Required.**                                                         |
| **Meraki Network IDs**  | `network_ids` key in `[meraki]` section (optional)     | `./config_prod/config.ini`    | `config.ini`                                                    | Filters which networks to sync. Blank means all in org.             |
| **Hostname Suffix**     | `hostname_suffix` key in `[script]` section            | `./config_prod/config.ini`    | `config.ini`                                                    | **Required.** Defines the local domain part (e.g., `.lan`).           |

## Troubleshooting

*   **"MERAKI_API_KEY environment variable not set."** (Error in logs)
    *   Ensure `MERAKI_API_KEY` is correctly set in your `.env` file.
    *   Verify that `docker-compose` is using the `.env` file (it should by default if named `.env` and in the same directory as `docker-compose.yml`).
    *   If you recently created or edited the `.env` file, you might need to restart the container: `docker-compose down && docker-compose build && docker-compose up -d`.

*   **"Configuration file not found at /config/config.ini"** (Error in logs)
    *   Confirm that the volume mount in `docker-compose.yml` (e.g., `volumes: - ./config_prod:/config:ro`) correctly points to your host directory.
    *   Ensure you have created the `./config_prod` directory on your host (relative to your `docker-compose.yml`).
    *   Verify that a `config.ini` file exists inside your host's `./config_prod` directory and is readable.

*   **Pi-hole API Errors / Records Not Updating** (Check script logs for detailed error messages)
    *   **URL:** Double-check `PIHOLE_API_URL` (in `.env` or `config.ini`). It must be the full path to the API, typically ending in `/admin/api.php`.
    *   **API Key:** If your Pi-hole admin interface has a password, `PIHOLE_API_KEY` (in `.env` or `config.ini`) must be the correct API token from Pi-hole's settings page.
    *   **Connectivity:** Ensure the Docker container can reach the Pi-hole IP/hostname and port.
    *   **Pi-hole Logs:** Check Pi-hole's own logs (e.g., `/var/log/pihole-FTL.log` or via the Pi-hole web UI under Tools -> Log) for any errors reported by Pi-hole when API calls are made.

*   **Meraki API Errors** (Check script logs for detailed error messages)
    *   **API Key Permissions:** Confirm your `MERAKI_API_KEY` has at least read permissions for the specified organization and any target networks.
    *   **Organization ID:** Verify the `organization_id` in `./config_prod/config.ini` is correct.
    *   **Network IDs:** If using `network_ids`, ensure they are correct and exist within the specified organization.
    *   **Rate Limits:** Meraki's API has rate limits (typically 10 requests/second per IP for Dashboard API v1). For very large organizations with many networks, the script could potentially hit these limits if it tries to query too many networks too quickly. The script currently makes one call to list all organization networks, then one call per target network to list its clients.

*   **Cron Job Not Running or Running at Unexpected Times**
    *   **Schedule Format:** Check the `CRON_SCHEDULE` in your `.env` file for correct cron syntax.
    *   **Container Logs:** View the main container logs (`docker-compose logs -f meraki-pihole-sync`) for messages from `docker-entrypoint.sh` about cron initialization, and for any Python script errors when it attempts to run.
    *   **Cron's Own Log:** Exec into the container (`docker-compose exec meraki-pihole-sync bash`) and inspect `crontab -l` to see the job as installed, and `cat /var/log/cron.log` (or `tail -f`) for cron daemon messages.
    *   **Timezone (`TZ`):** If cron jobs are running at UTC times instead of your expected local time, ensure the `TZ` environment variable is correctly set in your `.env` file to a valid TZ database name (e.g., `America/Chicago`).

## Contributing

Contributions are welcome! If you have improvements, bug fixes, or new features:

1.  Fork the repository.
2.  Create a new branch for your feature or fix.
3.  Make your changes and commit them with clear messages.
4.  Push your branch to your fork.
5.  Open a pull request against the main repository.

Please also feel free to open an issue if you encounter bugs or have suggestions.

## License

This project is licensed under the MIT License. (It's good practice to add a `LICENSE` file containing the full MIT License text to the repository root).
