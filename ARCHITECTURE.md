# Architecture Overview

This document provides a high-level overview of the application's architecture.

## Components

The application consists of the following components:

*   **FastAPI Web UI:** A web UI built with FastAPI that allows users to view the current custom DNS mappings in Pi-hole, force a synchronization, view the application logs, and update the sync interval.
*   **Meraki Client:** A client that fetches client information from the Meraki API.
*   **Pi-hole Client:** A client that adds, updates, and removes custom DNS records in Pi-hole.
*   **Sync Runner:** A component that runs the synchronization process at a configurable interval.

## Data Flow

1.  The `sync_runner` component runs the `meraki_pihole_sync` script at a configurable interval.
2.  The `meraki_pihole_sync` script fetches client information from the Meraki API using the `meraki_client`.
3.  The `meraki_pihole_sync` script adds, updates, and removes custom DNS records in Pi-hole using the `pihole_client`.
4.  The web UI displays the current custom DNS mappings in Pi-hole, the application logs, and allows the user to force a synchronization and update the sync interval.
