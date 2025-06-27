#!/bin/bash
set -e

# APP_COMMAND is passed from Dockerfile CMD, e.g., ["python", "meraki_pihole_sync.py"]
APP_COMMAND=("$@")

LOG_DIR="/app/logs"
APP_LOG_FILE="${LOG_DIR}/sync.log" # Python script logs here (via FileHandler) and to stdout
CRON_OUTPUT_LOG_FILE="${LOG_DIR}/cron_output.log" # Cron's stdout/stderr for the job goes here

# Ensure log directory and initial log files exist. Dockerfile should also create LOG_DIR.
mkdir -p "${LOG_DIR}"
touch "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
# Permissions: Dockerfile creates /app/logs. If cron runs as different user, it might need write access.
# Usually, cron jobs run as root or the user who owns the crontab, which should be fine.
# If issues arise, `chmod 666 "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"` or ensuring group writability might be needed.

# Run the application script once on startup
echo "Entrypoint: Running initial sync on container startup..."
# The Python script (APP_COMMAND) is configured to log to both its own file handler (${APP_LOG_FILE}) and stdout.
# Docker's `logs` command will capture the stdout. We don't need to redirect shell stdout to APP_LOG_FILE here.
if "${APP_COMMAND[@]}"; then
    echo "Entrypoint: Initial sync script finished." # This goes to Docker logs and stdout
else
    # This also goes to Docker logs and stdout
    echo "Entrypoint: Initial sync script execution failed with an error code. Check ${APP_LOG_FILE} and Docker logs for details from the script."
fi

# Setup cron job
if [ -z "$CRON_SCHEDULE" ]; then
  echo "Entrypoint: CRON_SCHEDULE environment variable not set. Cron job will not be scheduled. Script will only run on startup."
else
  echo "Entrypoint: Initializing cron job with schedule: $CRON_SCHEDULE"
  PYTHON_EXEC_PATH="/usr/local/bin/python" # Absolute path for Python in cron
  # APP_COMMAND is ["python", "meraki_pihole_sync.py"]. We need the script part.
  # So, ${APP_COMMAND[@]:1} gives "meraki_pihole_sync.py"
  CRON_JOB_SCRIPT_COMMAND="${PYTHON_EXEC_PATH} ${APP_COMMAND[@]:1}"
  CRON_JOB_FULL_COMMAND="${CRON_JOB_SCRIPT_COMMAND} >> ${CRON_OUTPUT_LOG_FILE} 2>&1"

  echo "Entrypoint: Cron job command will be: ${CRON_JOB_FULL_COMMAND}"
  echo "${CRON_SCHEDULE} ${CRON_JOB_FULL_COMMAND}" > /etc/cron.d/meraki-pihole-sync-cron
  chmod 0644 /etc/cron.d/meraki-pihole-sync-cron
  crontab /etc/cron.d/meraki-pihole-sync-cron
  echo "Entrypoint: Cron job set up."
fi

# Start cron daemon in the foreground (if scheduled) and tail logs
if [ -n "$CRON_SCHEDULE" ]; then
  echo "Entrypoint: Starting cron daemon..."
  # Start cron in background, then tail logs to keep container foregrounded
  cron -f & # Start cron in foreground and background it with & if more commands follow for tailing
  echo "Entrypoint: Tailing application log (${APP_LOG_FILE}) and cron job output log (${CRON_OUTPUT_LOG_FILE})..."
  # Use tail -F to follow by name, handles log rotation if it ever occurs.
  # The primary way to see live Python script output is `docker logs <container>`.
  # Tailing these files via entrypoint is secondary but can be useful.
  tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
else
  echo "Entrypoint: No CRON_SCHEDULE set. Script ran on startup. Container will now exit unless there's a long-running process or it's kept alive by Docker's restart policy."
  # If there's no cron, and the initial script is short-lived, the container might stop.
  # For a cron-based job, we usually want it to stay running.
  # If CRON_SCHEDULE is optional and can be empty, we might need a `sleep infinity` here or rely on user's restart policy.
  # However, the original request implied cron is central.
  # If CRON_SCHEDULE can be legitimately empty and user wants container to stay alive, this part needs thought.
  # For now, assuming CRON_SCHEDULE will typically be set.
  # If it's not set, and initial run is done, this script will end, and container will stop if CMD is this script.
  # Let's assume for now that if cron is not scheduled, the user might be running it for a one-shot task.
  # A `tail -f /dev/null` could keep it alive if CRON_SCHEDULE is empty but we want to exec in.
  # For now, let it exit if no cron.
  echo "Entrypoint: Exiting as there is no cron job to keep the container running."
fi
