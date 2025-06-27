#!/bin/bash
set -e

# APP_COMMAND is passed from Dockerfile CMD, e.g., ["python", "meraki_pihole_sync.py"]
# APP_COMMAND is passed from Dockerfile CMD, e.g., ["python", "meraki_pihole_sync.py"]
APP_COMMAND=("$@")

LOG_DIR="/app/logs"
APP_LOG_FILE="${LOG_DIR}/sync.log" # Python script logs here (via FileHandler) and to stdout
CRON_OUTPUT_LOG_FILE="${LOG_DIR}/cron_output.log" # Cron's stdout/stderr for the job goes here
APP_LOG_FILE="${LOG_DIR}/sync.log" # Python script logs here (via FileHandler) and to stdout
CRON_OUTPUT_LOG_FILE="${LOG_DIR}/cron_output.log" # Cron's stdout/stderr for the job goes here

# Ensure log directory and initial log files exist. Dockerfile should also create LOG_DIR.
# Ensure log directory and initial log files exist. Dockerfile should also create LOG_DIR.
mkdir -p "${LOG_DIR}"
touch "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
chmod 666 "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"

echo "Entrypoint: Running initial sync on container startup..."
# The Python script (APP_COMMAND) is configured to log to both its own file handler (${APP_LOG_FILE}) and stdout.
# Docker's `logs` command will capture the stdout.
if "${APP_COMMAND[@]}"; then
    echo "Entrypoint: Initial sync script finished."
else
    echo "Entrypoint: Initial sync script execution failed with an error code. Check ${APP_LOG_FILE} and Docker logs for details from the script."
fi

# Setup cron job
if [ -z "$CRON_SCHEDULE" ]; then
  echo "Entrypoint: CRON_SCHEDULE environment variable not set. Cron job will not be scheduled."
  echo "Entrypoint: Container will continue running and tailing logs."
  tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}" /dev/null
else
  echo "Entrypoint: Initializing cron job with schedule: $CRON_SCHEDULE"
  PYTHON_EXEC_PATH="/usr/local/bin/python"

  PYTHON_SCRIPT_NAME="${APP_COMMAND[1]}"
  CRON_JOB_SCRIPT_COMMAND="${PYTHON_EXEC_PATH} /app/${PYTHON_SCRIPT_NAME}"

  CRON_JOB_FULL_COMMAND="(date; ${CRON_JOB_SCRIPT_COMMAND}) >> ${CRON_OUTPUT_LOG_FILE} 2>&1"

  echo "Entrypoint: Cron job command will be: ${CRON_SCHEDULE} root bash -c '${CRON_JOB_FULL_COMMAND}'"
  echo "${CRON_SCHEDULE} root bash -c '${CRON_JOB_FULL_COMMAND}'" > /etc/cron.d/meraki-pihole-sync-cron
  echo "" >> /etc/cron.d/meraki-pihole-sync-cron
  chmod 0644 /etc/cron.d/meraki-pihole-sync-cron
  crontab /etc/cron.d/meraki-pihole-sync-cron
  echo "Entrypoint: Cron job set up."

  echo "Entrypoint: Starting cron daemon..."
  cron -f &

  echo "Entrypoint: Tailing application log (${APP_LOG_FILE}) and cron job output log (${CRON_OUTPUT_LOG_FILE})..."
  tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
fi
