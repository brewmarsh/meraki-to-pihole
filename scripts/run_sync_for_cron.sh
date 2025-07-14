#!/bin/bash
CRON_LOG_FILE="/app/logs/cron_output.log" # Define where this wrapper logs

echo "-----------------------------------------------------" >> "${CRON_LOG_FILE}"
echo "Cron wrapper script started at $(date)" >> "${CRON_LOG_FILE}"

export PATH="/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin"
echo "PATH for cron execution is: $PATH" >> "${CRON_LOG_FILE}"
echo "User for cron execution is: $(whoami)" >> "${CRON_LOG_FILE}"
echo "Current working directory is: $(pwd)" >> "${CRON_LOG_FILE}"
echo "Python3 location: $(which python3 || echo 'python3 not found in PATH')" >> "${CRON_LOG_FILE}"
echo "Script location: /app/meraki_pihole_sync.py" >> "${CRON_LOG_FILE}"
ls -l /app/meraki_pihole_sync.py >> "${CRON_LOG_FILE}" 2>&1

echo "Running command: /home/jules/.pyenv/shims/python3 /app/meraki_pihole_sync.py" >> "${CRON_LOG_FILE}"
# Execute the python script, ensuring its output also goes to the main cron log file
/home/jules/.pyenv/shims/python3 /app/meraki_pihole_sync.py >> "${CRON_LOG_FILE}" 2>&1
PY_EXIT_CODE=$?

echo "Python script finished with exit code: ${PY_EXIT_CODE}" >> "${CRON_LOG_FILE}"
echo "Cron wrapper script finished at $(date)" >> "${CRON_LOG_FILE}"
echo "-----------------------------------------------------" >> "${CRON_LOG_FILE}"

exit ${PY_EXIT_CODE}
