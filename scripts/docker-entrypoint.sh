#!/bin/bash
set -e

# Load environment variables from .env file
if [ -f /app/.env ]; then
  set -o allexport
  source /app/.env
  set +o allexport
fi

# APP_COMMAND is passed from Dockerfile CMD. After Dockerfile update, this will be e.g., ["python3", "meraki_pihole_sync.py"]
APP_COMMAND=("$@")

LOG_DIR="/app/logs"
APP_LOG_FILE="${LOG_DIR}/sync.log"        # Python script logs here (via FileHandler) and to stdout

# Ensure log directory and initial log files exist. Dockerfile also creates LOG_DIR.
mkdir -p "${LOG_DIR}"
# Create files if they don't exist, and ensure they are writable by any user (cron might run as different user)
touch "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}"
chmod 0666 "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}" # Allow write access for cron and app user

echo "Entrypoint: Running initial sync on container startup..."
echo "Entrypoint: Using python at $(which python)"
# The Python script (APP_COMMAND) is configured to log to both its own file handler (${APP_LOG_FILE}) and stdout.
# Docker's `logs` command will capture the stdout from this initial run.
# APP_COMMAND will now correctly be ["python3", "meraki_pihole_sync.py"] due to Dockerfile CMD change.
if "${APP_COMMAND[@]}"; then
    echo "Entrypoint: Initial sync script finished successfully."
else
    # Capture the exit code of the script
    exit_code=$?
    echo "Entrypoint: WARNING - Initial sync script execution failed with exit code ${exit_code}. Check ${APP_LOG_FILE} and Docker logs for details from the script."
    # Depending on severity, one might choose to exit the container here, but for now, allow cron to still be set up.
fi

# Setup cron job
if [ -z "$CRON_SCHEDULE" ]; then
  echo "Entrypoint: CRON_SCHEDULE environment variable not set or empty. Cron job will not be scheduled."
  echo "Entrypoint: Container will continue running and tailing logs (if any from initial run)."
  # Tail /dev/null to keep container running if logs are empty or not being written to
  tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}" /dev/null
else
  echo "Entrypoint: Initializing cron job with schedule: $CRON_SCHEDULE"
  ln -sf /usr/local/bin/python3 /usr/local/bin/python
  # Use python3 explicitly for the cron job. /usr/local/bin/python3 is standard in python:*-slim images.
  PYTHON3_EXEC_PATH="/usr/local/bin/python3"

  # APP_COMMAND[0] would be "python3", APP_COMMAND[1] would be "meraki_pihole_sync.py"
  # Ensure script name is correctly identified if APP_COMMAND has more parts, though it shouldn't for this app.
  if [ ${#APP_COMMAND[@]} -lt 2 ]; then
    echo "Entrypoint: ERROR - APP_COMMAND is not in the expected format ('executable scriptname ...'). Cannot determine script name for cron."
    # Fallback to tailing logs and not setting up cron
    tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}" /dev/null
    exit 1 # Exit because cron setup is critical if CRON_SCHEDULE is set
  fi
  PYTHON_SCRIPT_NAME="${APP_COMMAND[1]}" # e.g., meraki_pihole_sync.py

  # Construct the command that cron will run.
  # It will execute the python3 script directly (now that it's executable and has a shebang)
  # or via the explicit python3 path.
  # Using the direct script path relies on the shebang working in cron's environment.
  # Using PYTHON3_EXEC_PATH is more explicit. Let's stick to explicit for now.
  CRON_JOB_SCRIPT_COMMAND="python3 /app/${PYTHON_SCRIPT_NAME}"

  # Create the cron file. Cron requires a newline at the end of the file.
  CRON_FILE_PATH="/etc/cron.d/meraki-pihole-sync-cron"

  # Remove old cron file if it exists, to ensure no stale entries from previous versions or failed runs
  rm -f "${CRON_FILE_PATH}"
  echo "Entrypoint: Removed old cron file (if any) at ${CRON_FILE_PATH}."

  echo "Entrypoint: Writing new cron job definition to ${CRON_FILE_PATH}"
  # Simplified cron command. Output redirection handles basic logging of execution.
  # The Python script itself handles detailed logging, including timestamps.
  # The user 'root' is typically available and has permissions.
  # No complex subshells like (echo ...; command; echo ...) to reduce shell interpretation issues.
  # Explicitly set PATH for the cron job environment. These are common paths.
  echo "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin" > "${CRON_FILE_PATH}"
  # Removing 'root' user from the cron line. For /etc/cron.d files, this typically means the command runs as root.
  # The command will now be the wrapper script, explicitly run with /bin/bash.
  CRON_WRAPPER_SCRIPT_PATH="/app/run_sync_for_cron.sh" # Path where the wrapper will be in the container
  echo "${CRON_SCHEDULE} /bin/bash ${CRON_WRAPPER_SCRIPT_PATH}" >> "${CRON_FILE_PATH}" # Wrapper script handles its own logging to CRON_OUTPUT_LOG_FILE
  echo "" >> "${CRON_FILE_PATH}" # Ensure cron file ends with a newline
  chmod 0644 "${CRON_FILE_PATH}"

  # Log the exact content of the cron file to the main application log for debugging
  echo "Entrypoint: DEBUG - Content of ${CRON_FILE_PATH} as written by entrypoint:" >> "${APP_LOG_FILE}"
  cat "${CRON_FILE_PATH}" >> "${APP_LOG_FILE}"
  echo "" >> "${APP_LOG_FILE}" # Add a newline after cat output for readability
  echo "Entrypoint: DEBUG - End of ${CRON_FILE_PATH} content." >> "${APP_LOG_FILE}"

  # Apply the cron job. Some cron versions might not need crontab command if using /etc/cron.d/
  # but it's safer to include it or ensure the cron daemon picks it up.
  # For busybox cron (often in alpine/slim), files in /etc/cron.d are read automatically.
  # For standard vixie-cron, `crontab` command is usually for user crontabs, not /etc/cron.d.
  # The presence of the file in /etc/cron.d with correct permissions should be enough for most daemons.
  # `crontab /etc/cron.d/meraki-pihole-sync-cron` might show "bad minute" if it tries to parse the user field.
  # We'll rely on cron daemon picking up /etc/cron.d files.

  echo "Entrypoint: Cron job file created at ${CRON_FILE_PATH}."

  echo "Entrypoint: Starting cron daemon in foreground..."
  # `-f` keeps cron in the foreground. Combined with `tail -F` ensures container stays running.
  cron -f &
  CRON_PID=$!

  echo "Entrypoint: Tailing application log (${APP_LOG_FILE}) and cron job output log (${CRON_OUTPUT_LOG_FILE})..."
  # Tail the logs. If cron stops or the script wants to exit, tail will keep running.
  # Using `wait` on cron's PID isn't standard for this kind of multi-process container management.
  # Tailing logs is a common way to keep the container alive.
  tail -F "${APP_LOG_FILE}" "${CRON_OUTPUT_LOG_FILE}" &
  TAIL_PID=$!

  # Wait for either cron or tail to exit.
  # If cron exits (e.g. crashes), the container should probably stop.
  # If tail exits (shouldn't happen with -F unless files are removed), it's less critical but indicates an issue.
  wait -n $CRON_PID $TAIL_PID
  echo "Entrypoint: A monitored process (cron or tail) has exited. Container will now exit."
fi
