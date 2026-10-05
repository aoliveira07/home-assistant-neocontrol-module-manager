"""Runtime configuration from Home Assistant options and local environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.protocol import ProtocolValidationError, validate_broadcast_address


DEFAULTS: dict[str, Any] = {
    "broadcast_address": "255.255.255.255",
    "udp_port": 8760,
    "capture_buffer_size": 500,
    "enable_protocol_lab": False,
    "debug_protocol": False,
    "discovery_prefix": "homeassistant",
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    app_version: str
    app_host: str
    app_port: int
    broadcast_address: str
    udp_port: int
    capture_buffer_size: int
    enable_protocol_lab: bool
    debug_protocol: bool
    discovery_prefix: str
    mqtt_host: str | None
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None


def _load_options(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_settings() -> Settings:
    options_path = Path(os.getenv("OPTIONS_PATH", "/data/options.json"))
    options = {**DEFAULTS, **_load_options(options_path)}
    try:
        broadcast_address = validate_broadcast_address(str(options["broadcast_address"]))
    except ProtocolValidationError:
        broadcast_address = DEFAULTS["broadcast_address"]
    try:
        udp_port = int(options["udp_port"])
    except (TypeError, ValueError):
        udp_port = 8760
    if not 1 <= udp_port <= 65535:
        udp_port = 8760
    try:
        capture_buffer_size = max(1, min(5000, int(options["capture_buffer_size"])))
    except (TypeError, ValueError):
        capture_buffer_size = 500
    try:
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    except ValueError:
        mqtt_port = 1883
    return Settings(
        data_dir=Path(os.getenv("APP_DATA_DIR", "./data")),
        app_version=os.getenv("APP_VERSION", "0.1.0-alpha.1"),
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=int(os.getenv("APP_PORT", "8099")),
        broadcast_address=broadcast_address,
        udp_port=udp_port,
        capture_buffer_size=capture_buffer_size,
        enable_protocol_lab=bool(options["enable_protocol_lab"]),
        debug_protocol=bool(options["debug_protocol"]),
        discovery_prefix=str(options["discovery_prefix"] or "homeassistant").strip("/") or "homeassistant",
        mqtt_host=os.getenv("MQTT_HOST") or None,
        mqtt_port=mqtt_port,
        mqtt_username=os.getenv("MQTT_USER") or None,
        mqtt_password=os.getenv("MQTT_PASSWORD") or None,
    )

