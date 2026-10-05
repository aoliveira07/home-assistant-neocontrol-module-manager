"""Application composition and safe protocol operations."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.core.mqtt_bridge import MqttBridge
from app.core.protocol import (
    ProtocolValidationError,
    build_individual_packet,
    build_scene_packet,
    encode_module_name,
    parse_hex_payload,
)
from app.core.storage import Database
from app.core.udp_client import UdpService
from app.settings import Settings

LOGGER = logging.getLogger("neocontrol.runtime")


def _as_scene(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "enabled": bool(row.get("enabled"))}


def _as_module(row: dict[str, Any]) -> dict[str, Any]:
    return row


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.data_dir)
        self.udp = UdpService(settings)
        self.mqtt = MqttBridge(settings, self.list_scenes, self.press_scene)
        self.started_at = time.monotonic()
        self.errors: deque[dict[str, str]] = deque(maxlen=100)
        self.protocol_lab_enabled = settings.enable_protocol_lab

    async def start(self) -> None:
        await self.database.initialize(protocol_lab_default=self.settings.enable_protocol_lab)
        self.protocol_lab_enabled = bool(
            await self.database.get_setting("protocol_lab_enabled", self.settings.enable_protocol_lab)
        )
        await self.udp.start()
        await self.mqtt.start()
        if not self.udp.active:
            self.record_error(self.udp.last_error or "UDP listener did not start")

    async def stop(self) -> None:
        await self.mqtt.stop()
        await self.udp.stop()

    def record_error(self, message: str) -> None:
        LOGGER.error(message)
        self.errors.append({"timestamp": datetime.now(UTC).isoformat(), "message": message})

    async def list_scenes(self) -> list[dict[str, Any]]:
        return [_as_scene(row) for row in await self.database.list_scenes()]

    async def get_scene(self, scene_id: int) -> dict[str, Any] | None:
        row = await self.database.get_scene(scene_id)
        return _as_scene(row) if row else None

    async def list_modules(self) -> list[dict[str, Any]]:
        return [_as_module(row) for row in await self.database.list_modules()]

    def require_protocol_lab(self) -> None:
        if not self.protocol_lab_enabled:
            raise PermissionError("Protocol Lab is disabled")

    async def set_protocol_lab(self, enabled: bool, confirmed: bool) -> None:
        if enabled and not confirmed:
            raise PermissionError("Protocol Lab requires explicit confirmation")
        self.protocol_lab_enabled = enabled
        await self.database.set_setting("protocol_lab_enabled", enabled)

    async def send_scene(self, scene_number: int) -> dict[str, Any]:
        try:
            return await self.udp.send(build_scene_packet(scene_number))
        except (ProtocolValidationError, RuntimeError, OSError) as exc:
            self.record_error(f"scene send failed: {exc}")
            raise

    async def press_scene(self, scene_id: int) -> None:
        scene = await self.get_scene(scene_id)
        if not scene:
            self.record_error(f"MQTT requested unknown scene id={scene_id}")
            return
        if not scene["enabled"]:
            self.record_error(f"MQTT requested disabled scene id={scene_id}")
            return
        await self.send_scene(int(scene["scene_number"]))

    async def send_individual(
        self,
        *,
        module_name: str,
        module_raw_hex: str | None,
        function: int,
        subfunction: int,
        padding_mode: str,
    ) -> dict[str, Any]:
        self.require_protocol_lab()
        if module_raw_hex:
            module_bytes = parse_hex_payload(module_raw_hex)
            if len(module_bytes) != 8:
                raise ProtocolValidationError("module_raw_hex must contain exactly 8 bytes")
        else:
            module_bytes = encode_module_name(module_name, padding_mode)
        return await self.udp.send(build_individual_packet(module_bytes, function, subfunction))

    async def send_raw(self, hex_payload: str) -> dict[str, Any]:
        self.require_protocol_lab()
        payload = parse_hex_payload(hex_payload)
        return await self.udp.send(payload)

    def status(self) -> dict[str, Any]:
        return {
            "app_version": self.settings.app_version,
            "uptime_seconds": round(time.monotonic() - self.started_at, 1),
            "protocol_lab_enabled": self.protocol_lab_enabled,
            "udp": {
                "active": self.udp.active,
                "port": self.settings.udp_port,
                "broadcast_address": self.settings.broadcast_address,
                "rx_packets": self.udp.rx_packets,
                "tx_packets": self.udp.tx_packets,
                "last_received": self.udp.last_received,
                "last_transmitted": self.udp.last_transmitted,
                "last_error": self.udp.last_error,
            },
            "mqtt": self.mqtt.status(),
            "capture_buffer_size": len(self.udp.packets),
            "errors": list(self.errors)[-20:],
        }

