#!/bin/bash
set -e

# Default command to run (passed as CMD from Dockerfile or docker run)
APP_COMMAND=("$@")

# Check if CRON_SCHEDULE is set, otherwise use a default or exit
if [ -z "$CRON_SCHEDULE" ]; then
  echo "CRON_SCHEDULE environment variable not set. Exiting."
  exit 1
fi

LOG_DIR="/app/logs"
APP_LOG_FILE="${LOG_DIR}/sync.log"
CRON_OUTPUT_LOG_FILE="${LOG_DIR}/cron_output.log"

# Ensure log directory and initial log files exist
# The Dockerfile should have created ${LOG_DIR}, but make sure again and touch files.
mkdir -p "${LOG_DIR}"
touch "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
# Permissions might be needed if cron runs as a different user than the script, though often it's root.
# For simplicity, assuming container user can write or files created by root are writable by app.
# If issues, `chmod -R 777 "${LOG_DIR}"` could be used but is broad.

# Run the application script once on startup
# APP_COMMAND is expected to be ["python", "meraki_pihole_sync.py"]
# Python script itself logs to APP_LOG_FILE and stdout. We just execute it.
echo "Running initial sync on container startup..."
if "${APP_COMMAND[@]}"; then
    echo "Initial sync script finished." # Further details are in APP_LOG_FILE and container logs (stdout)
else
    echo "Initial sync script execution failed with an error code." # Further details in logs
fi
# Python script will write a separator to its own log file if needed.

# Create a cron job file
# APP_COMMAND is ["python", "meraki_pihole_sync.py"]
# Ensure absolute path to python for cron environment
PYTHON_EXEC_PATH="/usr/local/bin/python"
CRON_JOB_SCRIPT_COMMAND="${PYTHON_EXEC_PATH} ${APP_COMMAND[@]:1}" # Use array slicing to get script part

CRON_JOB_FULL_COMMAND="${CRON_JOB_SCRIPT_COMMAND} >> ${CRON_OUTPUT_LOG_FILE} 2>&1"

echo "Initializing cron job with schedule: $CRON_SCHEDULE"
echo "Cron job command will be: ${CRON_JOB_FULL_COMMAND}"
echo "${CRON_SCHEDULE} ${CRON_JOB_FULL_COMMAND}" > /etc/cron.d/meraki-pihole-sync-cron

# Give execution rights on the cron job file
chmod 0644 /etc/cron.d/meraki-pihole-sync-cron

# Apply cron job
crontab /etc/cron.d/meraki-pihole-sync-cron

# Start cron in the foreground and tail the application and cron output log files
echo "Starting cron daemon..."
cron
echo "Tailing application log (${APP_LOG_FILE}) and cron job output log (${CRON_OUTPUT_LOG_FILE})..."
# Tail both files. If one doesn't exist yet, tail won't fail immediately with -F.
# The python script also logs to stdout, so `docker logs` will still show the live python script logs.
# Tailing APP_LOG_FILE here is mostly for direct output if python script was not logging to its own stdout.
# Given python logs to its own stdout (and FileHandler), `docker logs` is primary for live script output.
# Tailing CRON_OUTPUT_LOG_FILE is important to see cron execution results.
tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
