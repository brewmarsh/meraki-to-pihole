#!/usr/local/bin/python3
# Python script to sync Meraki client IPs to Pi-hole
"""
Meraki Pi-hole DNS Sync

This script synchronizes client information from the Meraki API to a Pi-hole instance.
It identifies Meraki clients with Fixed IP Assignments (DHCP Reservations) and
creates corresponding custom DNS records in Pi-hole. This ensures reliable local
DNS resolution for these statically assigned devices.

The script fetches clients from specified Meraki networks (or all networks in an
organization if none are specified). It then compares these clients against existing
custom DNS records in Pi-hole and makes necessary additions or updates.

Configuration is managed entirely through environment variables.
"""

import sys
import structlog
from .sync_logic import sync_pihole_dns

log = structlog.get_logger()

if __name__ == "__main__":
    try:
        sync_pihole_dns()
    except Exception:
        log.critical("An unhandled exception occurred in main", exc_info=True)
        sys.exit(1)
