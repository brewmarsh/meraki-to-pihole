#!/bin/bash
set -e

# Load environment variables from .env file
if [ -f /app/.env ]; then
  set -o allexport
  source /app/.env
  set +o allexport
fi

LOG_DIR="/app/logs"
APP_LOG_FILE="${LOG_DIR}/sync.log"

# Ensure log directory and initial log files exist
mkdir -p "${LOG_DIR}"
touch "${APP_LOG_FILE}"
chmod 0666 "${APP_LOG_FILE}"

# Start the web server in the background
echo "Entrypoint: Starting web server..."
cd /app && gunicorn --bind 0.0.0.0:24653 app:app &
WEB_SERVER_PID=$!

# Start the sync runner script in the foreground
echo "Entrypoint: Starting sync runner..."
python3 /app/sync_runner.py &
SYNC_RUNNER_PID=$!

# Tail the logs
echo "Entrypoint: Tailing application log (${APP_LOG_FILE})..."
tail -f "${APP_LOG_FILE}"
