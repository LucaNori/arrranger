#!/bin/bash
set -e
echo "==================== ARRRANGER CONTAINER STARTUP ===================="
if [ -z "$TZ" ]; then
  export TZ="Europe/Rome"
  echo "TZ not set, using default: Europe/Rome"
else
  echo "Using timezone: $TZ"
fi
if [ -f /usr/share/zoneinfo/$TZ ]; then
  ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
  echo "$TZ" > /etc/timezone
  echo "Timezone configured successfully"
else
  echo "Warning: Timezone $TZ not found, using system default"
fi
echo "Container started at: $(date '+%Y-%m-%d %H:%M:%S %Z')"
PUID=${PUID:-1000}
PGID=${PGID:-1000}
echo "Using PUID: $PUID and PGID: $PGID"
if ! getent group $PGID > /dev/null; then
  groupadd -g $PGID arrranger
  echo "Created group with ID $PGID"
else
  echo "Group with ID $PGID already exists"
fi
if ! getent passwd $PUID > /dev/null; then
  useradd -u $PUID -g $PGID -d /config -s /bin/sh arrranger
  echo "Created user with ID $PUID"
else
  echo "User with ID $PUID already exists"
fi
if [ ! -f "$DB_NAME" ]; then
  echo "Database file not found at $DB_NAME, creating it now"
  touch "$DB_NAME"
  chown $PUID:$PGID "$DB_NAME"
  chmod 666 "$DB_NAME"
  echo "Created empty database file"
else
  echo "Using existing database file: $DB_NAME"
  chown $PUID:$PGID "$DB_NAME"
  chmod 666 "$DB_NAME"
fi

echo "Database file status: $(ls -la $DB_NAME)"
if [ -f "$CONFIG_FILE" ]; then
  echo "Using configuration file from $CONFIG_FILE"
else
  echo "No configuration file found at $CONFIG_FILE. Using example configuration."
  cp /app/arrranger_instances.json.example "$CONFIG_FILE"
  chown $PUID:$PGID "$CONFIG_FILE"
fi
chown -R $PUID:$PGID /app /data
chmod -R 755 /app /data
echo "Running as user: uid=$PUID, gid=$PGID"
echo "Starting application with command: $@"
echo "=================================================================="
exec gosu $PUID:$PGID "$@"