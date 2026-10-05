"""MQTT Discovery payloads for stable Home Assistant scene buttons."""

from __future__ import annotations

from typing import Any


BASE_TOPIC = "neocontrol_module_manager"
STATUS_TOPIC = f"{BASE_TOPIC}/status"
DEVICE = {
    "identifiers": ["neocontrol_module_manager"],
    "name": "Neocontrol Module Manager",
    "manufacturer": "Neocontrol",
    "model": "Module Classic bridge",
}


def scene_unique_id(scene_id: int) -> str:
    return f"neocontrol_module_scene_{scene_id}"


def scene_command_topic(scene_id: int) -> str:
    return f"{BASE_TOPIC}/scene/{scene_id}/set"


def scene_discovery_topic(discovery_prefix: str, scene_id: int) -> str:
    return f"{discovery_prefix}/button/{scene_unique_id(scene_id)}/config"


def build_scene_discovery(scene: dict[str, Any], discovery_prefix: str) -> dict[str, Any]:
    scene_id = int(scene["id"])
    return {
        "name": str(scene["name"]),
        "unique_id": scene_unique_id(scene_id),
        "command_topic": scene_command_topic(scene_id),
        "payload_press": "PRESS",
        "availability_topic": STATUS_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": DEVICE,
    }

