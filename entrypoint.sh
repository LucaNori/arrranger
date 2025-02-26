#!/bin/bash
set -e

# Check database file
if [ ! -f "$DB_NAME" ]; then
  echo "Database file not found at $DB_NAME, creating it now"
  touch "$DB_NAME"
  chmod 666 "$DB_NAME"
  echo "Created empty database file"
fi

echo "Database file status: $(ls -la $DB_NAME)"

# Handle configuration file
if [ -f "$CONFIG_FILE" ]; then
  echo "Using configuration file from $CONFIG_FILE"
else
  echo "No configuration file found at $CONFIG_FILE. Using example configuration."
  cp /app/arrranger_instances.json.example "$CONFIG_FILE"
  # We're running as non-root, so we're expecting the mounted volumes to have
  # proper permissions already
fi

echo "Running as user: $(id)"
echo "Starting application with command: $@"
# Execute the command
exec "$@"