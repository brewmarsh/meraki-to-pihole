import os
import sys
import logging
from meraki_pihole_sync import main
from clients.pihole_client import authenticate

def run_sync():
    pihole_url = os.getenv("PIHOLE_API_URL")
    pihole_password = os.getenv("PIHOLE_API_KEY")
    session = authenticate(pihole_url, pihole_password)
    if not session:
        logging.error("Failed to authenticate with Pi-hole. Halting sync.")
        sys.exit(1)
    main(session)
