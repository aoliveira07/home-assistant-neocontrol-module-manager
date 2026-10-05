"""Small SQLite persistence layer kept independent from the HTTP framework."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "neocontrol.db"

    async def initialize(self, protocol_lab_default: bool = False) -> None:
        await self._run(self._initialize_sync, protocol_lab_default)

    def _connect(self) -> sqlite3.Connection:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize_sync(self, protocol_lab_default: bool) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    scene_number INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS modules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    logical_name TEXT NOT NULL,
                    raw_hex TEXT,
                    module_type TEXT NOT NULL DEFAULT 'unknown',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experimental_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_id INTEGER,
                    label TEXT NOT NULL,
                    function INTEGER NOT NULL,
                    subfunction INTEGER NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS known_packet_signatures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    payload_prefix TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT ''
                );
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                ("protocol_lab_enabled", json.dumps(bool(protocol_lab_default))),
            )

    async def _run(self, function: Callable[..., T], *args: Any) -> T:
        return await asyncio.to_thread(function, *args)

    @staticmethod
    def _decode_bool(value: str | None) -> bool:
        try:
            return bool(json.loads(value or "false"))
        except json.JSONDecodeError:
            return value == "true"

    async def get_setting(self, key: str, default: Any = None) -> Any:
        def operation() -> Any:
            with self._connect() as db:
                row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                if row is None:
                    return default
                value = row["value"]
                if isinstance(default, bool):
                    return self._decode_bool(value)
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value

        return await self._run(operation)

    async def set_setting(self, key: str, value: Any) -> None:
        await self._run(self._set_setting_sync, key, value)

    def _set_setting_sync(self, key: str, value: Any) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    async def list_scenes(self) -> list[dict[str, Any]]:
        return await self._run(self._list_rows, "scenes")

    async def get_scene(self, scene_id: int) -> dict[str, Any] | None:
        return await self._run(self._get_row_sync, "scenes", scene_id)

    async def create_scene(self, name: str, scene_number: int, enabled: bool) -> dict[str, Any]:
        return await self._run(self._create_scene_sync, name, scene_number, enabled)

    def _create_scene_sync(self, name: str, scene_number: int, enabled: bool) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO scenes(name, scene_number, enabled, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                (name, scene_number, int(enabled), now, now),
            )
            return dict(db.execute("SELECT * FROM scenes WHERE id = ?", (cursor.lastrowid,)).fetchone())

    async def update_scene(self, scene_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return await self._run(self._update_row_sync, "scenes", scene_id, values)

    async def delete_scene(self, scene_id: int) -> bool:
        return await self._run(self._delete_row_sync, "scenes", scene_id)

    async def list_modules(self) -> list[dict[str, Any]]:
        return await self._run(self._list_rows, "modules")

    async def get_module(self, module_id: int) -> dict[str, Any] | None:
        return await self._run(self._get_row_sync, "modules", module_id)

    async def create_module(self, values: dict[str, Any]) -> dict[str, Any]:
        return await self._run(self._create_module_sync, values)

    def _create_module_sync(self, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO modules(name, logical_name, raw_hex, module_type, notes, created_at, updated_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?)""",
                (
                    values["name"],
                    values["logical_name"],
                    values.get("raw_hex"),
                    values.get("module_type", "unknown"),
                    values.get("notes", ""),
                    now,
                    now,
                ),
            )
            return dict(db.execute("SELECT * FROM modules WHERE id = ?", (cursor.lastrowid,)).fetchone())

    async def update_module(self, module_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        return await self._run(self._update_row_sync, "modules", module_id, values)

    async def delete_module(self, module_id: int) -> bool:
        return await self._run(self._delete_row_sync, "modules", module_id)

    def _list_rows(self, table: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()]

    def _get_row_sync(self, table: str, row_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
            return dict(row) if row else None

    def _update_row_sync(self, table: str, row_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "scenes": {"name", "scene_number", "enabled"},
            "modules": {"name", "logical_name", "raw_hex", "module_type", "notes"},
        }[table]
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return self._get_row_sync(table, row_id)
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        parameters = [int(value) if key == "enabled" else value for key, value in updates.items()]
        parameters.append(row_id)
        with self._connect() as db:
            cursor = db.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", parameters)
            if cursor.rowcount == 0:
                return None
            row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
            return dict(row) if row else None

    def _delete_row_sync(self, table: str, row_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            return cursor.rowcount > 0

