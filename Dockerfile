# Dockerfile for Meraki Pi-hole Sync

# Build-time arguments for versioning
ARG APP_VERSION=unknown
ARG COMMIT_SHA=unknown

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV APP_VERSION=${APP_VERSION}
ENV COMMIT_SHA=${COMMIT_SHA}
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
# - cron for scheduled tasks
# - libffi-dev and other build dependencies for certain Python packages if needed (though not for requests/configparser)
RUN apt-get update && apt-get install -y cron libffi-dev procps && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for the application code
WORKDIR /app
COPY ./app /app
RUN chmod +x /app/meraki_pihole_sync.py # Make python script executable

# Copy the entrypoint script and make it executable
COPY ./scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create a directory for log files if needed by the script (config dir no longer needed)
RUN mkdir -p /app/logs

# Default cron schedule (can be overridden by CRON_SCHEDULE env var)
# Runs daily at 2:30 AM by default
ENV CRON_SCHEDULE "30 2 * * *"

# Expose any ports if your application listens on them (not typical for a cron job script)
# EXPOSE 8080

# Set the entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command for the entrypoint (e.g. the script to run)
# This will be passed to the entrypoint script
# Changed to python3 and removed obsolete --config argument
CMD ["python3", "meraki_pihole_sync.py"]
