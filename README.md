# Meraki to Pi-hole Client Sync

[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Python Version](https://img.shields.io/badge/python-3-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This script is a simple Python application designed to run as a service, either in a Docker container or directly on a host. Its primary function is to synchronize client information from your Meraki network dashboard to your Pi-hole instance.

This solves the problem of having only IP addresses in your Pi-hole logs. With this script, your Pi-hole query logs and dashboards will show the actual device hostnames (e.g., `david-iphone`, `living-room-tv`) as they are known by your Meraki network, making it much easier to identify network activity.

## Features

-   Fetches all clients from your Meraki organization.
-   Connects to your Pi-hole's database (`gravity.db`) via SQLite.
-   Adds or updates the Pi-hole `client` table with the client's IP address, Meraki-known hostname, and a comment.
-   Runs on a continuous loop, re-syncing every `X` minutes (configurable).
-   Packaged as a lightweight Docker container.

## How It Works

1.  **Meraki API:** The script uses the Meraki Dashboard API to fetch a list of all clients across your organization.
2.  **Pi-hole Database:** It opens a direct connection to the Pi-hole `gravity.db` SQLite database.
3.  **Sync Logic:**
    -   It iterates through all Meraki clients.
    -   For each client, it checks if a client with that IP address already exists in the Pi-hole database.
    -   If **yes**, it updates the `name` and `comment` fields with the Meraki data.
    -   If **no**, it inserts a new row with the IP, name, and a comment (e.g., "Added by Meraki-Pihole Sync").
4.  **Loop:** The script then sleeps for a configurable interval before running the sync again.

## Requirements

-   Python 3
-   Meraki Dashboard API Key
-   Your Meraki Organization ID
-   Network access from the script's host to your Pi-hole instance (specifically to the `gravity.db` file).

## Installation & Setup

### Option 1: Docker (Recommended)

This is the easiest way to run the script as a persistent service.

1.  **Pi-hole `gravity.db` Location:** You *must* make your Pi-hole's `gravity.db` file available to this container. The most common way is to mount the Pi-hole configuration directory as a volume.
    -   If your Pi-hole is also running in Docker, you can use the same volume you mapped for its `/etc/pihole/` directory.
    -   If Pi-hole is running on a bare-metal host, you'll need to mount its directory, e.g., `-v /etc/pihole/:/pihole-db/`.

2.  **Run the container:**
    Use the following Docker run command, replacing the placeholders with your values.

    ```bash
    docker run -d \
      --name meraki-pihole-sync \
      -e MERAKI_API_KEY="YOUR_API_KEY" \
      -e MERAKI_ORG_ID="YOUR_ORG_ID" \
      -e PIHOLE_DB_PATH="/pihole-db/gravity.db" \
      -e SYNC_INTERVAL_MINUTES="15" \
      -v /path/to/your/pihole/config:/pihole-db \
      --restart always \
      brewmarsh/meraki-to-pihole:latest
    ```

### Option 2: Docker Compose

If you manage your Pi-hole with `docker-compose.yml`, you can simply add this as another service.

1.  **Add to `docker-compose.yml`:**
    Add this service definition to your existing `docker-compose.yml` file.

    ```yaml
    services:
      pihole:
        # ... your existing pihole configuration ...
        container_name: pihole
        volumes:
          - './pihole-config/etc-pihole:/etc/pihole'
          - './pihole-config/etc-dnsmasq.d:/etc/dnsmasq.d'
        # ... rest of your config ...

      meraki-sync:
        container_name: meraki-sync
        image: brewmarsh/meraki-to-pihole:latest
        restart: always
        depends_on:
          - pihole
        environment:
          - MERAKI_API_KEY=YOUR_API_KEY
          - MERAKI_ORG_ID=YOUR_ORG_ID
          - PIHOLE_DB_PATH=/pihole-db/gravity.db
          - SYNC_INTERVAL_MINUTES=15
        volumes:
          # This MUST match the volume used by your pihole service for /etc/pihole
          - './pihole-config/etc-pihole:/pihole-db'
    ```
    *Note: The key is that the `volumes` path for `meraki-sync`'s `/pihole-db` points to the *same host directory* as `pihole`'s `/etc/pihole`.*

2.  **Start:**
    ```bash
    docker-compose up -d
    ```

### Option 3: Manual Python Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/brewmarsh/meraki-to-pihole.git](https://github.com/brewmarsh/meraki-to-pihole.git)
    cd meraki-to-pihole
    ```

2.  **Install dependencies:**
    This project uses Poetry for dependency management.
    ```bash
    pip install poetry
    poetry install --no-dev
    ```

3.  **Set Environment Variables:**
    ```bash
    export MERAKI_API_KEY="YOUR_API_KEY"
    export MERAKI_ORG_ID="YOUR_ORG_ID"
    export PIHOLE_DB_PATH="/etc/pihole/gravity.db" # Or wherever your DB is
    export SYNC_INTERVAL_MINUTES="15"
    ```

4.  **Run the script:**
    ```bash
    poetry run python app/main.py
    ```

## Environment Variables

| Variable | Required | Description | Default |
| :--- | :--- | :--- | :--- |
| `MERAKI_API_KEY` | **Yes** | Your Meraki Dashboard API key. | `None` |
| `MERAKI_ORG_ID` | **Yes** | Your Meraki Organization ID. | `None` |
| `PIHOLE_DB_PATH` | **Yes** | Full path to the `gravity.db` file. e.g., `/pihole-db/gravity.db` | `None` |
| `SYNC_INTERVAL_MINUTES` | No | The time (in minutes) to wait between syncs. | `15` |
| `LOG_LEVEL` | No | Set the logging level. | `INFO` |

## How to Contribute

We welcome contributions! Please see our [**CONTRIBUTING.md**](CONTRIBUTING.md) file for development guidelines and setup instructions.

## License

MIT
