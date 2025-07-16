#!/bin/bash
echo "-----------------------------------------------------"
echo "Cron wrapper script started at $(date)"

export PATH="/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin"
echo "PATH for cron execution is: $PATH"
echo "User for cron execution is: $(whoami)"
echo "Current working directory is: $(pwd)"
echo "Python3 location: $(which python3 || echo 'python3 not found in PATH')"
echo "Script location: /app/meraki_pihole_sync.py"
ls -l /app/meraki_pihole_sync.py

echo "Running command: /usr/local/bin/python3 /app/meraki_pihole_sync.py"
# Execute the python script
/usr/local/bin/python3 /app/meraki_pihole_sync.py
PY_EXIT_CODE=$?

echo "Python script finished with exit code: ${PY_EXIT_CODE}"
echo "Cron wrapper script finished at $(date)"
echo "-----------------------------------------------------"

exit ${PY_EXIT_CODE}
