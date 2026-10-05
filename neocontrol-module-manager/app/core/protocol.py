"""Confirmed and experimental Neocontrol Module Classic frame helpers."""

from __future__ import annotations

import ipaddress
import re


class ProtocolValidationError(ValueError):
    """Raised when a frame or address cannot be safely encoded."""


MAX_SCENE_NUMBER = (0xFF * 240) + 239


def _require_byte(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ProtocolValidationError(f"{field} must be an integer from 0 to 255")
    return value


def build_scene_packet(scene_number: int) -> bytes:
    """Build the confirmed four-byte scene frame."""

    if isinstance(scene_number, bool) or not isinstance(scene_number, int):
        raise ProtocolValidationError("scene_number must be an integer")
    if scene_number < 0 or scene_number > MAX_SCENE_NUMBER:
        raise ProtocolValidationError(f"scene_number must be between 0 and {MAX_SCENE_NUMBER}")
    return bytes((0x02, scene_number // 240, scene_number % 240, 0xFF))


def build_individual_packet(
    module_name_bytes: bytes,
    function: int,
    subfunction: int,
) -> bytes:
    """Build the confirmed individual-frame envelope.

    The meaning of ``function`` and ``subfunction`` is intentionally not
    inferred here; both remain experimental until physical captures exist.
    """

    if not isinstance(module_name_bytes, bytes) or len(module_name_bytes) != 8:
        raise ProtocolValidationError("module_name_bytes must contain exactly 8 bytes")
    _require_byte(function, "function")
    _require_byte(subfunction, "subfunction")
    return bytes((0x14, 0x00)) + module_name_bytes + bytes((function, subfunction, 0xFF))


def parse_hex_payload(value: str, *, allow_empty: bool = False) -> bytes:
    """Parse human-entered HEX, accepting spaces and separators."""

    if not isinstance(value, str):
        raise ProtocolValidationError("HEX payload must be text")
    normalized = re.sub(r"[\s:_-]", "", value)
    if not normalized and allow_empty:
        return b""
    if not normalized:
        raise ProtocolValidationError("HEX payload cannot be empty")
    if len(normalized) % 2:
        raise ProtocolValidationError("HEX payload must contain complete bytes")
    if re.fullmatch(r"[0-9a-fA-F]+", normalized) is None:
        raise ProtocolValidationError("HEX payload contains invalid characters")
    try:
        return bytes.fromhex(normalized)
    except ValueError as exc:
        raise ProtocolValidationError("HEX payload is invalid") from exc


def encode_module_name(name: str, padding_mode: str = "nul") -> bytes:
    """Encode the experimental eight-byte module-name field.

    ``nul`` and ``space`` use strict ASCII because the actual encoding has not
    been confirmed. ``raw``/``raw_hex`` interpret *name* as eight HEX bytes.
    """

    if not isinstance(name, str):
        raise ProtocolValidationError("module name must be text")
    mode = padding_mode.strip().lower().replace("-", "_")
    if mode in {"raw", "raw_hex", "hex"}:
        raw = parse_hex_payload(name)
        if len(raw) != 8:
            raise ProtocolValidationError("raw module name must contain exactly 8 bytes")
        return raw
    if mode not in {"nul", "space"}:
        raise ProtocolValidationError("padding_mode must be nul, space or raw_hex")
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ProtocolValidationError("module name must be ASCII until encoding is confirmed") from exc
    if len(encoded) > 8:
        raise ProtocolValidationError("module name cannot exceed 8 ASCII bytes")
    fill = b"\x00" if mode == "nul" else b" "
    return encoded.ljust(8, fill)


def validate_broadcast_address(value: str) -> str:
    """Validate a usable IPv4 broadcast destination."""

    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ProtocolValidationError("broadcast_address must be a valid IPv4 address") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise ProtocolValidationError("broadcast_address must be IPv4")
    if address.is_unspecified or address.is_loopback or address.is_multicast:
        raise ProtocolValidationError("broadcast_address cannot be unspecified, loopback or multicast")
    return str(address)

