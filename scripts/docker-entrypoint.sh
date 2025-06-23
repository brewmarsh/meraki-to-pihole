#!/bin/bash
set -e

# Default command to run (passed as CMD from Dockerfile or docker run)
APP_COMMAND=("$@")

# Check if CRON_SCHEDULE is set, otherwise use a default or exit
if [ -z "$CRON_SCHEDULE" ]; then
  echo "CRON_SCHEDULE environment variable not set. Exiting."
  exit 1
fi

echo "Initializing cron job with schedule: $CRON_SCHEDULE"

# Create a cron job file
echo "${CRON_SCHEDULE} /usr/local/bin/python ${APP_COMMAND[@]} >> /var/log/cron.log 2>&1" > /etc/cron.d/meraki-pihole-sync-cron

# Give execution rights on the cron job file
chmod 0644 /etc/cron.d/meraki-pihole-sync-cron

# Apply cron job
crontab /etc/cron.d/meraki-pihole-sync-cron

# Create the log file to be able to run tail
touch /var/log/cron.log

# Start cron in the foreground and tail the log file
echo "Starting cron daemon..."
cron && tail -f /var/log/cron.log
