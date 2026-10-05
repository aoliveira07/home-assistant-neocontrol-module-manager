"""Async UDP transport and bounded packet capture buffer."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import socket
from collections import deque
from datetime import UTC, datetime
from typing import Any, Callable

from app.core.protocol import ProtocolValidationError, validate_broadcast_address
from app.settings import Settings

LOGGER = logging.getLogger("neocontrol.udp")


def packet_record(
    *,
    direction: str,
    source_ip: str,
    source_port: int,
    destination_port: int,
    payload: bytes,
    interpretation: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "direction": direction,
        "source_ip": source_ip,
        "source_port": source_port,
        "destination_port": destination_port,
        "length": len(payload),
        "payload_hex": payload.hex(" ").upper(),
        "interpretation": interpretation,
    }


def interpret_payload(payload: bytes) -> str | None:
    """Return only interpretations supported by confirmed frame structure."""

    if len(payload) == 4 and payload[0] == 0x02 and payload[3] == 0xFF:
        scene_number = payload[1] * 240 + payload[2]
        return f"confirmed scene frame (scene={scene_number})"
    if len(payload) == 13 and payload[0:2] == b"\x14\x00" and payload[-1] == 0xFF:
        return f"individual frame envelope (function={payload[10]}, subfunction={payload[11]})"
    return None


class _ListenerProtocol(asyncio.DatagramProtocol):
    def __init__(self, service: "UdpService"):
        self.service = service

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.service.transport = transport
        self.service.active = True
        LOGGER.info("[UDP] listener active on 0.0.0.0:%s", self.service.settings.udp_port)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.service.record_rx(data, addr)

    def error_received(self, exc: Exception) -> None:
        self.service.last_error = str(exc)
        LOGGER.warning("[UDP] socket error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        self.service.active = False
        self.service.transport = None
        if exc:
            self.service.last_error = str(exc)
            LOGGER.warning("[UDP] listener stopped: %s", exc)


class UdpService:
    def __init__(self, settings: Settings, on_packet: Callable[[dict[str, Any]], None] | None = None):
        self.settings = settings
        self.on_packet = on_packet
        self.packets: deque[dict[str, Any]] = deque(maxlen=settings.capture_buffer_size)
        self.transport: asyncio.DatagramTransport | None = None
        self.active = False
        self.last_error: str | None = None
        self.rx_packets = 0
        self.tx_packets = 0
        self.last_received: dict[str, Any] | None = None
        self.last_transmitted: dict[str, Any] | None = None

    async def start(self) -> None:
        try:
            broadcast = validate_broadcast_address(self.settings.broadcast_address)
            loop = asyncio.get_running_loop()
            await loop.create_datagram_endpoint(
                lambda: _ListenerProtocol(self),
                local_addr=("0.0.0.0", self.settings.udp_port),
                family=socket.AF_INET,
                allow_broadcast=True,
            )
            self.settings = self.settings.__class__(**{**self.settings.__dict__, "broadcast_address": broadcast})
        except (OSError, ProtocolValidationError) as exc:
            self.last_error = str(exc)
            LOGGER.exception("[UDP] unable to start listener")

    async def stop(self) -> None:
        if self.transport:
            self.transport.close()
        self.active = False

    def record_rx(self, payload: bytes, source: tuple[str, int]) -> None:
        record = packet_record(
            direction="rx",
            source_ip=source[0],
            source_port=source[1],
            destination_port=self.settings.udp_port,
            payload=payload,
            interpretation=interpret_payload(payload),
        )
        self.rx_packets += 1
        self.last_received = record
        self.packets.append(record)
        LOGGER.debug("[UDP RX] %s:%s len=%s %s", source[0], source[1], len(payload), record["payload_hex"])
        if self.on_packet:
            self.on_packet(record)

    async def send(self, payload: bytes, destination: str | None = None) -> dict[str, Any]:
        if not self.transport:
            raise RuntimeError("UDP listener is not active")
        target = destination or self.settings.broadcast_address
        validate_broadcast_address(target)
        self.transport.sendto(payload, (target, self.settings.udp_port))
        record = packet_record(
            direction="tx",
            source_ip="0.0.0.0",
            source_port=self.settings.udp_port,
            destination_port=self.settings.udp_port,
            payload=payload,
            interpretation=interpret_payload(payload),
        )
        record["destination_ip"] = target
        self.tx_packets += 1
        self.last_transmitted = record
        self.packets.append(record)
        LOGGER.info("[UDP TX] %s:%s len=%s %s", target, self.settings.udp_port, len(payload), record["payload_hex"])
        if self.on_packet:
            self.on_packet(record)
        return record

    def list_packets(
        self,
        *,
        source_ip: str | None = None,
        length: int | None = None,
        prefix_hex: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        normalized_prefix = (prefix_hex or "").replace(" ", "").replace(":", "").upper()
        result = list(reversed(self.packets))
        if source_ip:
            result = [item for item in result if item.get("source_ip") == source_ip]
        if length is not None:
            result = [item for item in result if item.get("length") == length]
        if normalized_prefix:
            result = [
                item for item in result if item.get("payload_hex", "").replace(" ", "").upper().startswith(normalized_prefix)
            ]
        return result[: max(1, min(limit, self.settings.capture_buffer_size))]

    def clear(self) -> None:
        self.packets.clear()
        self.last_received = None
        self.last_transmitted = None

    def export_csv(self, records: list[dict[str, Any]]) -> str:
        stream = io.StringIO()
        fields = [
            "timestamp",
            "direction",
            "source_ip",
            "source_port",
            "destination_ip",
            "destination_port",
            "length",
            "payload_hex",
            "interpretation",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
        return stream.getvalue()

