#!/bin/bash
#shellcheck disable=SC2086

if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
  ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
  echo "$TZ" > /etc/timezone
fi

if [ ! -f "$CONFIG_FILE" ]; then
  cp /app/arrranger_instances.json.example "$CONFIG_FILE"
fi

exec uv run arrranger_sync.py "$@"