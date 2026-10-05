"""Optional MQTT Discovery bridge using Home Assistant's MQTT service."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

try:
    from aiomqtt import Client, MqttError
except ImportError:  # pragma: no cover - local protocol tests do not need MQTT
    Client = None  # type: ignore[assignment,misc]

    class MqttError(Exception):
        pass

from app.core.discovery import (
    BASE_TOPIC,
    STATUS_TOPIC,
    build_scene_discovery,
    scene_discovery_topic,
)
from app.settings import Settings

LOGGER = logging.getLogger("neocontrol.mqtt")


PublishItem = tuple[str, str, int, bool]


class MqttBridge:
    def __init__(
        self,
        settings: Settings,
        list_scenes: Callable[[], Awaitable[list[dict[str, Any]]]],
        on_scene_command: Callable[[int], Awaitable[None]],
    ):
        self.settings = settings
        self.list_scenes = list_scenes
        self.on_scene_command = on_scene_command
        self.queue: asyncio.Queue[PublishItem] = asyncio.Queue()
        self.task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()
        self.connected = False
        self.available = bool(settings.mqtt_host and Client)
        self.last_error: str | None = None
        self.last_connected: str | None = None
        self.published_discovery = 0

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run(), name="mqtt-bridge")

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def publish(self, topic: str, payload: str, *, qos: int = 1, retain: bool = True) -> None:
        if not self.available:
            return
        await self.queue.put((topic, payload, qos, retain))

    async def sync_discovery(self) -> None:
        if not self.available:
            return
        scenes = await self.list_scenes()
        for scene in scenes:
            topic = scene_discovery_topic(self.settings.discovery_prefix, int(scene["id"]))
            payload = build_scene_discovery(scene, self.settings.discovery_prefix) if scene["enabled"] else {}
            await self.publish(topic, json.dumps(payload, separators=(",", ":")))
        # Deletions are explicitly cleared by remove_scene_discovery().

    async def remove_scene_discovery(self, scene_id: int) -> None:
        if not self.available:
            return
        await self.publish(scene_discovery_topic(self.settings.discovery_prefix, scene_id), "")

    async def _run(self) -> None:
        if not self.settings.mqtt_host or Client is None:
            self.available = False
            return
        while not self.stop_event.is_set():
            try:
                async with Client(
                    hostname=self.settings.mqtt_host,
                    port=self.settings.mqtt_port,
                    username=self.settings.mqtt_username,
                    password=self.settings.mqtt_password,
                    identifier="neocontrol-module-manager",
                ) as client:
                    self.connected = True
                    self.last_connected = datetime.now(UTC).isoformat()
                    self.last_error = None
                    await client.subscribe(f"{BASE_TOPIC}/scene/+/set", qos=1)
                    await client.publish(STATUS_TOPIC, "online", qos=1, retain=True)
                    await self._queue_current_discovery(client)
                    LOGGER.info("[MQTT] connected")
                    receiver = asyncio.create_task(self._receive(client), name="mqtt-receiver")
                    publisher = asyncio.create_task(self._publish_queued(client), name="mqtt-publisher")
                    done, pending = await asyncio.wait(
                        {receiver, publisher}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    for task in done:
                        task.result()
                    try:
                        await client.publish(STATUS_TOPIC, "offline", qos=1, retain=True)
                    except (MqttError, OSError):
                        pass
            except (MqttError, OSError, asyncio.CancelledError) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                self.last_error = str(exc)
                LOGGER.warning("[MQTT] disconnected: %s", exc)
            finally:
                self.connected = False
            if not self.stop_event.is_set():
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

    async def _queue_current_discovery(self, client: Any) -> None:
        scenes = await self.list_scenes()
        for scene in scenes:
            topic = scene_discovery_topic(self.settings.discovery_prefix, int(scene["id"]))
            payload = build_scene_discovery(scene, self.settings.discovery_prefix) if scene["enabled"] else {}
            await client.publish(topic, json.dumps(payload, separators=(",", ":")), qos=1, retain=True)
            self.published_discovery += 1

    async def _publish_queued(self, client: Any) -> None:
        while True:
            topic, payload, qos, retain = await self.queue.get()
            await client.publish(topic, payload, qos=qos, retain=retain)
            if topic.endswith("/config"):
                self.published_discovery += 1
                LOGGER.info("[MQTT] discovery published: %s", topic)

    async def _receive(self, client: Any) -> None:
        async for message in client.messages:
            topic = str(message.topic)
            parts = topic.split("/")
            if len(parts) != 4 or parts[:2] != [BASE_TOPIC, "scene"] or parts[3] != "set":
                continue
            payload = message.payload.decode("utf-8", errors="replace") if isinstance(message.payload, bytes) else str(message.payload)
            if payload.strip().upper() != "PRESS":
                continue
            try:
                scene_id = int(parts[2])
            except ValueError:
                continue
            await self.on_scene_command(scene_id)

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "connected": self.connected,
            "host_configured": bool(self.settings.mqtt_host),
            "last_connected": self.last_connected,
            "last_error": self.last_error,
            "published_discovery": self.published_discovery,
        }

