# Meraki Pi-hole DNS Sync

## Project Overview

This project provides a Docker container that syncs client information from the Meraki API to a Pi-hole instance. Specifically, it identifies Meraki clients with **Fixed IP Assignments (DHCP Reservations)** and creates corresponding custom DNS records in Pi-hole. This ensures reliable local DNS resolution for these statically assigned devices.

The script runs once on container startup and then on a configurable cron schedule. All configurations are managed via environment variables. Logs are written to a file within the container and can be accessed via a mounted volume on the host.

## Features

*   Fetches client IP information specifically for devices with **Fixed IP Assignments** from specified Meraki networks (or all networks in an organization).
*   Uses the client's description or DHCP hostname from Meraki as the basis for the DNS record.
*   Adds/updates custom DNS records in Pi-hole for these fixed IP clients.
*   Removes stale DNS records from Pi-hole if they are no longer found in Meraki with a fixed IP (scoped by a configurable hostname suffix).
*   **Runs on container initialization and then on a configurable cron schedule.**
*   **All configuration is managed via environment variables (no more `config.ini`).**
*   Securely handles Meraki & Pi-hole API keys.
*   Easy deployment using Docker and `docker-compose.yml`.
*   **Logs script activity to `/app/logs/sync.log` and cron job output to `/app/logs/cron_output.log` inside the container, accessible via a host-mounted volume.**

## Directory Structure

```
.
├── app/
│   ├── meraki_pihole_sync.py  # Main Python script
│   └── VERSION.txt            # Contains the current application version
├── scripts/
│   └── docker-entrypoint.sh   # Docker entrypoint script for cron setup & initial run
├── .env.example               # Example environment file for docker-compose
├── Dockerfile
├── docker-compose.yml         # Docker Compose file for easy deployment
├── LICENSE                    # MIT License file
└── README.md                  # This file
```

## How it Works

1.  The Docker container starts. The `docker-entrypoint.sh` script immediately runs the `meraki_pihole_sync.py` Python script for an initial sync. Output is logged to `/app/logs/sync.log`.
2.  After the initial run, the `docker-entrypoint.sh` script sets up a cron job based on the `CRON_SCHEDULE` environment variable.
3.  At each scheduled time, cron executes the `meraki_pihole_sync.py` script. Output from these scheduled runs is logged to `/app/logs/cron_output.log`.
4.  The Python script (`meraki_pihole_sync.py`) reads all its configuration (Meraki API Key, Org ID, Network IDs, Pi-hole URL/Key, Hostname Suffix) from environment variables.
5.  It connects to the Meraki API:
    *   Fetches a list of networks for the configured `MERAKI_ORG_ID`.
    *   Filters for specific networks if `MERAKI_NETWORK_IDS` is set.
    *   For each relevant network, it fetches clients and filters them to include only those with a "Fixed IP Assignment" where the assigned IP matches the client's current IP.
6.  It connects to the Pi-hole API (using `PIHOLE_API_URL` and `PIHOLE_API_KEY`):
    *   Retrieves the current list of custom DNS records.
7.  For each relevant Meraki client (with a valid Fixed IP Assignment):
    *   Constructs a hostname using the client's Meraki description/DHCP hostname and the `HOSTNAME_SUFFIX`.
    *   Adds or updates the DNS record in Pi-hole for this hostname and its fixed IP.
8.  The script performs a cleanup: DNS records in Pi-hole matching the `HOSTNAME_SUFFIX` but no longer corresponding to an active Meraki client with a Fixed IP Assignment are removed.
9.  The Python script logs its detailed actions to `/app/logs/sync.log` (and also to stdout, visible with `docker logs`).

## Installation

This application is designed to be run using Docker and Docker Compose.

### Prerequisites

*   **Docker and Docker Compose**: Ensure they are installed.
*   **Git**: For cloning this repository.
*   **Meraki API Key**: From your Meraki Dashboard with read access.
*   **Pi-hole Instance**: A running Pi-hole with its IP/hostname.
*   **Pi-hole API Token**: If your Pi-hole admin interface is password-protected (recommended), get the token from Pi-hole Settings -> API / Web interface.

### Steps

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url> # Replace <repository_url>
    cd <repository_name>     # Replace <repository_name>
    ```

2.  **Configure Environment Variables:**
    All configuration is now done via a `.env` file. Copy the example:
    ```bash
    cp .env.example .env
    ```
    Edit the `.env` file with your specific details. See `.env.example` for all available variables and their descriptions (e.g., `MERAKI_API_KEY`, `MERAKI_ORG_ID`, `MERAKI_NETWORK_IDS`, `PIHOLE_API_URL`, `PIHOLE_API_KEY`, `HOSTNAME_SUFFIX`, `CRON_SCHEDULE`, `TZ`).

3.  **Prepare Log Directory (Optional but Recommended):**
    The `docker-compose.yml` is configured to mount `./meraki_sync_logs` on your host to `/app/logs` in the container. Create this directory on your host if you want persistent logs:
    ```bash
    mkdir ./meraki_sync_logs
    ```
    You can change this path in `docker-compose.yml` if desired.

4.  **Build and Run the Docker Container:**
    ```bash
    docker-compose build
    docker-compose up -d
    ```
    This builds the image (passing default build arguments specified in `docker-compose.yml`) and starts the container. The sync script will run once immediately, then follow the cron schedule. The script will log its version and commit SHA (if provided during build) on startup.

    To pass specific version information during the build (e.g., in a CI environment or scripted build):
    ```bash
    # Example: Read version from app/VERSION.txt and get current git commit
    APP_VERSION=$(cat app/VERSION.txt)
    COMMIT_SHA=$(git rev-parse --short HEAD)

    docker-compose build --build-arg APP_VERSION=${APP_VERSION} --build-arg COMMIT_SHA=${COMMIT_SHA}
    docker-compose up -d
    ```

## Usage

### Viewing Logs

*   **Live script output (stdout of Python script):**
    ```bash
    docker-compose logs -f meraki-pihole-sync
    ```
*   **Persistent application log file (from initial run and subsequent script runs if it also logs to file):**
    Check the file `./meraki_sync_logs/sync.log` on your host (or the directory you configured for the volume mount).
*   **Persistent cron job output log file:**
    Check the file `./meraki_sync_logs/cron_output.log` on your host.
*   **To tail logs from within the container (if needed for debugging):**
    ```bash
    docker-compose exec meraki-pihole-sync tail -F /app/logs/sync.log /app/logs/cron_output.log
    ```

### Stopping the Container
```bash
docker-compose down
```

### Forcing a Sync (Manual Script Execution)
To run the sync process manually outside of the cron schedule or initial run:
```bash
docker-compose exec meraki-pihole-sync python app/meraki_pihole_sync.py
```
This executes the script inside the running container, using its existing environment variables. Output will go to `/app/logs/sync.log` and stdout.

## Configuration Summary (Environment Variables in `.env` file)

| Environment Variable    | Required? | Description                                                                                                | Example                                                              |
|-------------------------|-----------|------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| `MERAKI_API_KEY`        | Yes       | Your Cisco Meraki Dashboard API key.                                                                         | `YOUR_MERAKI_API_KEY`                                                |
| `MERAKI_ORG_ID`         | Yes       | Your Meraki Organization ID.                                                                               | `YOUR_MERAKI_ORGANIZATION_ID`                                        |
| `MERAKI_NETWORK_IDS`    | No        | Comma-separated list of Meraki Network IDs to sync. Blank for all in org.                                  | `L_123,L_456`                                                        |
| `PIHOLE_API_URL`        | Yes       | Full URL to your Pi-hole API endpoint.                                                                     | `http://192.168.1.10/admin/api.php`                                  |
| `PIHOLE_API_KEY`        | No        | Your Pi-hole API token. Required if Pi-hole is password-protected.                                           | `YOUR_PIHOLE_API_TOKEN`                                              |
| `HOSTNAME_SUFFIX`       | Yes       | Domain suffix for DNS records (e.g., `.lan`, `.home.arpa`).                                                  | `.example.local`                                                     |
| `CRON_SCHEDULE`         | No        | Cron schedule for syncs. Default in `docker-compose.yml` is `0 3 * * *`.                                     | `"0 */6 * * *"` (every 6 hours)                                      |
| `TZ`                    | No        | Timezone for the container (e.g., `America/New_York`). Defaults to UTC.                                    | `Europe/London`                                                      |

## Troubleshooting

*   **Environment Variable Issues (e.g., "Missing mandatory environment variables"):**
    *   Ensure your `.env` file is in the same directory as `docker-compose.yml` and is named exactly `.env`.
    *   Verify all required variables (see table above) are present and correctly spelled in your `.env` file with non-empty values where required (e.g., `HOSTNAME_SUFFIX` cannot be blank).
    *   If you updated `.env` after the container was started, you must rebuild and restart: `docker-compose down && docker-compose build && docker-compose up -d`.
    *   The `docker-compose.yml` file explicitly includes `env_file: - .env`. If issues persist, ensure no other mechanism (like shell-exported variables of the same name with empty values) is overriding the `.env` file content.
*   **Log File Issues:**
    *   If `./meraki_sync_logs` (or your custom host path) is not showing logs, check permissions on the host directory.
    *   Ensure the volume mount in `docker-compose.yml` is correct: `- ./meraki_sync_logs:/app/logs`.
*   **Pi-hole API Errors / Records Not Updating** (Check `/app/logs/sync.log` or `cron_output.log`):
    *   **URL:** Double-check `PIHOLE_API_URL`.
    *   **API Key:** Ensure `PIHOLE_API_KEY` is correct if your Pi-hole is password-protected.
    *   **Connectivity:** Confirm the container can reach Pi-hole.
*   **Meraki API Errors** (Check logs):
    *   **API Key/Org ID:** Verify `MERAKI_API_KEY` permissions and `MERAKI_ORG_ID`.
    *   **Network IDs:** If `MERAKI_NETWORK_IDS` is used, ensure IDs are valid.
    *   **Rate Limits:** For very large setups, Meraki API rate limits could be a factor.
*   **Cron Job Not Running / Incorrect Times**
    *   Verify `CRON_SCHEDULE` syntax.
    *   Check `/app/logs/cron_output.log` for output from scheduled runs.
    *   Ensure `TZ` is set correctly if jobs run at unexpected UTC times.
    *   Exec into the container (`docker-compose exec meraki-pihole-sync bash`) and check `crontab -l`.

## Versioning

This project uses a manual versioning approach for simplicity, with infrastructure to support build-time version and commit tracking.

*   **`app/VERSION.txt`**: This file, located in the `app` directory, should contain the current semantic version of the application (e.g., `0.1.0`). It should be updated manually when a new version is being prepared.
*   **Build Arguments:** The `Dockerfile` accepts two build arguments:
    *   `APP_VERSION`: The application version (intended to be sourced from `app/VERSION.txt`).
    *   `COMMIT_SHA`: The short Git commit SHA.
*   **Environment Variables:** These build arguments are baked into the Docker image as environment variables `APP_VERSION` and `COMMIT_SHA`.
*   **Logging:** The Python script reads these environment variables on startup and includes them in its initial log message, e.g., "Starting Meraki Pi-hole Sync Script - Version: 0.1.0, Commit: abc1234".
*   **`docker-compose.yml`:** The `docker-compose.yml` file includes an `args` section under `build` to demonstrate how these can be passed. For local development, it uses placeholder values.
    ```yaml
    # In docker-compose.yml
    build:
      context: .
      args:
        - APP_VERSION=0.1.0_manual # Should match app/VERSION.txt
        - COMMIT_SHA=dev_build     # 'dev_build' or similar for local
    ```
*   **Building with Specific Version Info:**
    When creating an official build (e.g., via a script or CI/CD pipeline), you should pass these arguments dynamically:
    ```bash
    APP_VERSION=$(cat app/VERSION.txt)
    COMMIT_SHA=$(git rev-parse --short HEAD) # Gets the current short commit SHA
    docker-compose build \
      --build-arg APP_VERSION=${APP_VERSION} \
      --build-arg COMMIT_SHA=${COMMIT_SHA}
    # Followed by docker-compose up -d
    ```

This setup allows the running application and its logs to be clearly associated with a specific version and code commit, aiding in debugging and release management. Automation of `app/VERSION.txt` updates and build argument injection can be achieved with CI/CD pipelines.

## Contributing

Contributions are welcome! Please fork, branch, commit, and open a pull request. For issues or suggestions, please open an issue on the project's tracker.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
