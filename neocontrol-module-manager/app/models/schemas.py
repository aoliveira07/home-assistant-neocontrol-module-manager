from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.protocol import MAX_SCENE_NUMBER, ProtocolValidationError, parse_hex_payload


class Scene(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scene_number: int
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SceneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scene_number: int = Field(ge=0, le=MAX_SCENE_NUMBER)
    enabled: bool = True


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    scene_number: int | None = Field(default=None, ge=0, le=MAX_SCENE_NUMBER)
    enabled: bool | None = None


ModuleType = Literal["unknown", "relay", "dimmer", "switch", "task"]


class Module(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    logical_name: str
    raw_hex: str | None = None
    module_type: ModuleType = "unknown"
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    logical_name: str = Field(min_length=1, max_length=120)
    raw_hex: str | None = Field(default=None, max_length=32)
    module_type: ModuleType = "unknown"
    notes: str = Field(default="", max_length=2000)

    @field_validator("raw_hex")
    @classmethod
    def validate_raw_hex(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        try:
            raw = parse_hex_payload(value)
        except ProtocolValidationError as exc:
            raise ValueError(str(exc)) from exc
        if len(raw) != 8:
            raise ValueError("raw_hex must contain exactly 8 bytes")
        return raw.hex(" ").upper()


class ModuleUpdate(ModuleCreate):
    pass


class SendSceneRequest(BaseModel):
    scene_number: int = Field(ge=0, le=MAX_SCENE_NUMBER)


class SendIndividualRequest(BaseModel):
    module_name: str = ""
    module_raw_hex: str | None = None
    function: int = Field(ge=0, le=255)
    subfunction: int = Field(ge=0, le=255)
    padding_mode: Literal["nul", "space", "raw_hex"] = "nul"


class SendRawRequest(BaseModel):
    hex_payload: str = Field(min_length=1, max_length=4096)


class ProtocolLabSetting(BaseModel):
    enabled: bool
    confirmed: bool = False

