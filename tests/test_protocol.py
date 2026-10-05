import pytest

from app.core.protocol import (
    MAX_SCENE_NUMBER,
    ProtocolValidationError,
    build_individual_packet,
    build_scene_packet,
    encode_module_name,
    parse_hex_payload,
    validate_broadcast_address,
)


@pytest.mark.parametrize(
    ("scene", "expected"),
    [
        (0, "02 00 00 FF"),
        (1, "02 00 01 FF"),
        (10, "02 00 0A FF"),
        (239, "02 00 EF FF"),
        (240, "02 01 00 FF"),
    ],
)
def test_scene_frames(scene, expected):
    assert build_scene_packet(scene).hex(" ").upper() == expected


def test_scene_range_keeps_byte_one_valid():
    assert build_scene_packet(MAX_SCENE_NUMBER) == bytes((0x02, 0xFF, 0xEF, 0xFF))
    with pytest.raises(ProtocolValidationError):
        build_scene_packet(MAX_SCENE_NUMBER + 1)


def test_individual_frame():
    assert build_individual_packet(bytes.fromhex("41 42 43 44 45 46 47 48"), 1, 2).hex(" ").upper() == (
        "14 00 41 42 43 44 45 46 47 48 01 02 FF"
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: build_individual_packet(b"short", 1, 2),
        lambda: build_individual_packet(b"12345678", 256, 2),
        lambda: build_individual_packet(b"12345678", 1, -1),
        lambda: encode_module_name("TOO-LONG9"),
        lambda: encode_module_name("ação"),
        lambda: parse_hex_payload(""),
        lambda: parse_hex_payload("GG"),
        lambda: encode_module_name("41 42 43", "raw_hex"),
    ],
)
def test_invalid_protocol_inputs(call):
    with pytest.raises(ProtocolValidationError):
        call()


def test_name_padding_and_raw_hex():
    assert encode_module_name("ABC", "nul") == b"ABC\x00\x00\x00\x00\x00"
    assert encode_module_name("ABC", "space") == b"ABC     "
    assert encode_module_name("41 42 43 44 45 46 47 48", "raw_hex") == b"ABCDEFGH"


@pytest.mark.parametrize("address", ["not-an-ip", "::1", "0.0.0.0", "224.0.0.1"])
def test_invalid_broadcast(address):
    with pytest.raises(ProtocolValidationError):
        validate_broadcast_address(address)


def test_valid_broadcasts():
    assert validate_broadcast_address("255.255.255.255") == "255.255.255.255"
    assert validate_broadcast_address("192.168.1.255") == "192.168.1.255"

