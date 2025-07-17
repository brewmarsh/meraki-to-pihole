# Meraki Pi-hole DNS Sync 🔄

## 📝 Project Overview

This project provides a Docker container that syncs client information from the Meraki API to a Pi-hole instance. Specifically, it identifies Meraki clients with **Fixed IP Assignments (DHCP Reservations)** and creates corresponding custom DNS records in Pi-hole. This ensures reliable local DNS resolution for these statically assigned devices.

The script runs on a configurable interval, and all configurations are managed via environment variables. Logs are written to a file within the container and can be accessed via a mounted volume on the host or the web UI.

## ✨ Features

*   Fetches client IP information specifically for devices with **Fixed IP Assignments** from specified Meraki networks (or all networks in an organization).
*   Uses the client's description or DHCP hostname from Meraki as the basis for the DNS record.
*   Adds/updates custom DNS records in Pi-hole for these fixed IP clients.
*   **Runs on a configurable interval.**
*   **All configuration is managed via environment variables.**
*   Securely handles Meraki & Pi-hole API keys.
*   Easy deployment using Docker and `docker-compose.yml`.
*   **Logs script activity to `/app/logs/sync.log` inside the container, accessible via a host-mounted volume or the web UI.**
*   **Web UI for monitoring and interaction.**

## Directory Structure

```
.
├── app/
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── meraki_client.py
│   │   └── pihole_client.py
│   ├── meraki_pihole_sync.py  # Main Python script
│   └── VERSION.txt            # Contains the current application version
├── scripts/
│   └── docker-entrypoint.sh   # Docker entrypoint script for cron setup & initial run
├── tests/
│   ├── __init__.py
│   ├── test_meraki_client.py
│   └── test_pihole_client.py
├── .env.example               # Example environment file for docker-compose
├── Dockerfile
├── docker-compose.yml         # Docker Compose file for easy deployment
├── LICENSE                    # MIT License file
└── README.md                  # This file
```

## Running Tests

To run the unit tests, run the following command from the root of the project:

```bash
python3 -m unittest discover tests
```

## 🚀 How it Works

1.  The Docker container starts, launching the Gunicorn web server and the `sync_runner.py` script.
2.  The `sync_runner.py` script runs the `meraki_pihole_sync.py` script on a loop, with a configurable sleep interval between each run.
3.  The Python script (`meraki_pihole_sync.py`) reads its configuration from environment variables.
4.  It connects to the Meraki API and fetches a list of all clients in the organization.
5.  It connects to the Pi-hole API and retrieves the current list of custom DNS records.
6.  For each relevant Meraki client (with a valid Fixed IP Assignment):
    *   Constructs a hostname using the client's Meraki description or MAC address, sanitizes it, and appends the `HOSTNAME_SUFFIX`.
    *   Adds or updates the DNS record in Pi-hole for this hostname and its fixed IP.
7.  The Python script logs its detailed actions to a log file, which is visible in the web UI and optionally on the host.

## 🛠️ Installation

This application is designed to be run using Docker and Docker Compose.

### ✅ Prerequisites

*   **Docker and Docker Compose**: Ensure they are installed.
*   **Git**: For cloning this repository.
*   **Meraki API Key**: From your Meraki Dashboard with read access.
*   **Pi-hole Instance**: A running Pi-hole with its IP/hostname.
*   **Pi-hole API Token**: If your Pi-hole admin interface is password-protected (recommended), get the token from Pi-hole Settings -> API / Web interface.

### ⚙️ Steps

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
    Edit the `.env` file with your specific details. See the Configuration Summary section for more details.

3.  **Prepare Log Directory (Optional but Recommended):**
    The `docker-compose.yml` is configured to mount `./logs` on your host to `/app/logs` in the container. Create this directory on your host if you want persistent logs:
    ```bash
    mkdir ./logs
    ```
    You can change this path in `docker-compose.yml` if desired.

4.  **Build and Run the Docker Container:**
    ```bash
    docker-compose build
    docker-compose up -d
    ```
    This builds the image and starts the container. The sync script will start running immediately.

    To pass specific version information during the build (e.g., in a CI environment or scripted build):
    ```bash
    # Example: Read version from app/VERSION.txt and get current git commit
    APP_VERSION=$(cat app/VERSION.txt)
    COMMIT_SHA=$(git rev-parse --short HEAD)

    docker-compose build --build-arg APP_VERSION=${APP_VERSION} --build-arg COMMIT_SHA=${COMMIT_SHA}
    docker-compose up -d
    ```

## 🖥️ Usage

### Web UI

The application includes a web UI for monitoring and interacting with the sync process. The web UI is available on port `24653` by default.

#### Features

*   **📊 View Mappings:** See the custom DNS mappings currently loaded in Pi-hole.
*   **🔄 Force Sync:** Manually trigger a sync process.
*   **📝 View Logs:** View the `sync.log` file in real-time.
*   **⚙️ Update Sync Interval:** Change the sync interval on the fly.
*   **🗑️ Clear Logs:** Clear the log file.

### Viewing Logs

Logs are available in the web UI, or you can access them directly:

*   **Live script output:**
    ```bash
    docker-compose logs -f meraki-pihole-sync
    ```
*   **Persistent application log file:**
    Check the file `./logs/sync.log` on your host (or the directory you configured for the volume mount).

### Stopping the Container
```bash
docker-compose down
```

### Forcing a Sync

You can force a sync using the web UI, or by running the following command:
```bash
docker-compose exec meraki-pihole-sync python3 /app/meraki_pihole_sync.py
```

## 📋 Configuration Summary (Environment Variables in `.env` file)

| Environment Variable    | Required? | Description                                                                                                | Example                                                              |
|-------------------------|-----------|------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| `MERAKI_API_KEY`        | Yes       | Your Cisco Meraki Dashboard API key.                                                                         | `YOUR_MERAKI_API_KEY`                                                |
| `MERAKI_ORG_ID`         | Yes       | Your Meraki Organization ID.                                                                               | `YOUR_MERAKI_ORGANIZATION_ID`                                        |
| `MERAKI_NETWORK_IDS`    | No        | Comma-separated list of Meraki Network IDs to sync. If blank or not set, all networks in the organization will be queried. | `L_123,L_456`                                                        |
| `PIHOLE_API_URL`        | Yes       | Full URL to your Pi-hole API endpoint.                                                                     | `http://192.168.1.10/admin` or `http://pi.hole/admin` (script appends `/api.php`) |
| `PIHOLE_API_KEY`        | No        | Your Pi-hole API token (Webpassword/API Token). Required if Pi-hole admin interface is password-protected.   | `YOUR_PIHOLE_API_TOKEN`                                              |
| `HOSTNAME_SUFFIX`       | Yes       | Domain suffix for DNS records (e.g., `.lan`, `.home.arpa`). Ensure it starts with a `.` if intended.          | `.example.local`                                                     |
| `MERAKI_CLIENT_TIMESPAN_SECONDS` | No | Optional. Timespan in seconds for fetching Meraki clients (e.g., clients seen in the last X seconds). Defaults to `86400` (24 hours). | `259200` (72 hours)                                                 |
| `SYNC_INTERVAL_SECONDS` | No        | The interval, in seconds, at which to sync the clients. Defaults to `300`. This can also be set from the web UI. | `600` (10 minutes)                                                   |
| `LOG_LEVEL`             | No        | Logging level for the Python script. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Defaults to `INFO`. | `DEBUG`                                                              |
| `TZ`                    | No        | Timezone for the container (e.g., `America/New_York`). Affects log timestamps. Defaults to UTC. | `Europe/London`                                                      |

## 🤔 Troubleshooting

*   **"python: not found" or "python3: not found" in logs:**
    *   This should be resolved with the latest updates to `Dockerfile` and `docker-entrypoint.sh` which explicitly use `python3` and make the script executable. Ensure you have pulled the latest changes and rebuilt your Docker image (`docker-compose build`).
*   **"No relevant Meraki clients found" but you expect clients:**
    *   **Verify Meraki Configuration:** The most common reason is that clients in your Meraki network do not meet the script's criteria:
        *   They MUST have a **Fixed IP assignment** (DHCP reservation) configured in the Meraki dashboard.
        *   Their **current, active IP address** on the network MUST match this Fixed IP assignment. If a client is configured for a fixed IP but is currently offline or has a different IP, it won't be synced.
    *   **Check API Key and IDs:** Double-check `MERAKI_API_KEY`, `MERAKI_ORG_ID`, and `MERAKI_NETWORK_IDS` (if used) in your `.env` file for typos or incorrect values.
    *   **Client Activity Timespan:** Consider increasing `MERAKI_CLIENT_TIMESPAN_SECONDS` (e.g., to `259200` for 3 days) if your clients might not have been seen by Meraki within the default 24-hour window.
    *   **Enable DEBUG Logging:** This is crucial for diagnosing this issue.
        1.  Set `LOG_LEVEL=DEBUG` in your `.env` file.
        2.  Restart the container: `docker-compose up -d --force-recreate meraki-pihole-sync`.
        3.  Check the script log in the web UI or by running: `docker-compose logs meraki-pihole-sync` or look in `./logs/sync.log`.
        4.  With DEBUG logging, the script will output messages for each client it processes, indicating why it might be skipping them (e.g., "does not have a fixed IP assignment," "fixed IP assignment (...) but current IP (...) differs," "Skipping client ... due to missing name, current IP, or client ID"). The script will also explicitly state if it suggests enabling DEBUG logging if it's not already on.
*   **Environment Variable Issues (e.g., "Missing mandatory environment variables"):**
    *   Ensure your `.env` file is in the same directory as `docker-compose.yml` and is named exactly `.env`.
    *   Verify all required variables (see table above) are present and correctly spelled in your `.env` file with non-empty values where required (e.g., `HOSTNAME_SUFFIX` cannot be blank).
    *   If you updated `.env` after the container was started, you must restart the container for changes to take effect: `docker-compose restart meraki-pihole-sync` or `docker-compose up -d --force-recreate`. A full rebuild (`docker-compose build`) is only needed if you change `Dockerfile` or files copied into the image.
    *   The `docker-compose.yml` file explicitly includes `env_file: - .env`. If issues persist, ensure no other mechanism (like shell-exported variables of the same name with empty values) is overriding the `.env` file content for the `docker-compose` execution environment.
*   **Log File Issues:**
    *   If `./logs` (or your custom host path) is not showing logs, check permissions on the host directory. The `docker-entrypoint.sh` now attempts to `chmod 0666` the log files inside the container, which should help with most permission issues.
    *   Ensure the volume mount in `docker-compose.yml` is correct: `- ./logs:/app/logs`.
*   **Pi-hole API Errors / Records Not Updating** (Check the web UI log viewer or `/app/logs/sync.log`):
    *   **URL:** Double-check `PIHOLE_API_URL`. It should point to the admin directory (e.g., `http://pi.hole/admin` or `http://192.168.1.10/admin`). The script automatically appends `/api.php`.
    *   **API Key:** Ensure `PIHOLE_API_KEY` (your Pi-hole Webpassword/API Token) is correct if your Pi-hole admin interface is password-protected. If it's not password-protected, you can leave `PIHOLE_API_KEY` blank.
    *   **Connectivity:** Confirm the container can reach Pi-hole. Use `docker-compose exec meraki-pihole-sync curl -v <PIHOLE_API_URL>` (e.g. `http://pi.hole/admin/api.php`) to test.
*   **Meraki API Errors** (Check logs, set `LOG_LEVEL=DEBUG` for more details):
    *   **API Key/Org ID:** Verify `MERAKI_API_KEY` has necessary read permissions and `MERAKI_ORG_ID` is correct.
    *   **Network IDs:** If `MERAKI_NETWORK_IDS` is used, ensure IDs are valid and exist in your organization.
    *   **Rate Limits:** For very large setups with many networks/clients, Meraki API rate limits (HTTP 429 errors) could be a factor. The script has a basic retry mechanism.

## 📦 Versioning

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

## 🤝 Contributing

Contributions are welcome! Please fork, branch, commit, and open a pull request. For issues or suggestions, please open an issue on the project's tracker.

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
