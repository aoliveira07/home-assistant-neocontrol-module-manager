#!/usr/bin/with-contenv bashio
set -e

export APP_DATA_DIR="/data"
export APP_VERSION="${BUILD_VERSION:-0.1.0-alpha.2}"
export APP_HOST="0.0.0.0"
export APP_PORT="8099"

# The Services API is exposed through Bashio. Keep MQTT optional: a missing
# broker must not prevent UDP capture or the Ingress UI from starting.
if MQTT_HOST_VALUE="$(bashio::services mqtt "host" 2>/dev/null)" && [ -n "${MQTT_HOST_VALUE}" ]; then
  export MQTT_HOST="${MQTT_HOST_VALUE}"
  export MQTT_PORT="$(bashio::services mqtt "port" 2>/dev/null || echo 1883)"
  export MQTT_USER="$(bashio::services mqtt "username" 2>/dev/null || true)"
  export MQTT_PASSWORD="$(bashio::services mqtt "password" 2>/dev/null || true)"
fi

exec python3 -m app.main

