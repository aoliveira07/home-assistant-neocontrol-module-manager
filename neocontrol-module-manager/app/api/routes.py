from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.protocol import ProtocolValidationError
from app.models.schemas import (
    ModuleCreate,
    ModuleUpdate,
    ProtocolLabSetting,
    SceneCreate,
    SceneUpdate,
    SendIndividualRequest,
    SendRawRequest,
    SendSceneRequest,
)
from app.runtime import Runtime

router = APIRouter(prefix="/api")


def runtime_from(request: Request) -> Runtime:
    return request.app.state.runtime


def protocol_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/status")
async def status(request: Request):
    return runtime_from(request).status()


@router.get("/scenes")
async def list_scenes(request: Request):
    return await runtime_from(request).list_scenes()


@router.post("/scenes", status_code=201)
async def create_scene(payload: SceneCreate, request: Request):
    runtime = runtime_from(request)
    scene = await runtime.database.create_scene(payload.name.strip(), payload.scene_number, payload.enabled)
    await runtime.mqtt.sync_discovery()
    return {**scene, "enabled": bool(scene["enabled"])}


@router.put("/scenes/{scene_id}")
async def update_scene(scene_id: int, payload: SceneUpdate, request: Request):
    runtime = runtime_from(request)
    values = payload.model_dump(exclude_none=True)
    if "name" in values:
        values["name"] = values["name"].strip()
    scene = await runtime.database.update_scene(scene_id, values)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    await runtime.mqtt.sync_discovery()
    return {**scene, "enabled": bool(scene["enabled"])}


@router.delete("/scenes/{scene_id}", status_code=204)
async def delete_scene(scene_id: int, request: Request):
    runtime = runtime_from(request)
    if not await runtime.database.delete_scene(scene_id):
        raise HTTPException(status_code=404, detail="Scene not found")
    await runtime.mqtt.remove_scene_discovery(scene_id)
    await runtime.mqtt.sync_discovery()
    return Response(status_code=204)


@router.post("/scenes/{scene_id}/test")
async def test_scene(scene_id: int, request: Request):
    runtime = runtime_from(request)
    scene = await runtime.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    try:
        record = await runtime.send_scene(int(scene["scene_number"]))
    except (ProtocolValidationError, RuntimeError, OSError) as exc:
        raise protocol_error(exc) from exc
    return {"scene": scene, "packet": record}


@router.get("/modules")
async def list_modules(request: Request):
    return await runtime_from(request).list_modules()


@router.post("/modules", status_code=201)
async def create_module(payload: ModuleCreate, request: Request):
    values = payload.model_dump()
    values["name"] = values["name"].strip()
    values["logical_name"] = values["logical_name"].strip()
    return await runtime_from(request).database.create_module(values)


@router.put("/modules/{module_id}")
async def update_module(module_id: int, payload: ModuleUpdate, request: Request):
    values = payload.model_dump()
    module = await runtime_from(request).database.update_module(module_id, values)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.delete("/modules/{module_id}", status_code=204)
async def delete_module(module_id: int, request: Request):
    if not await runtime_from(request).database.delete_module(module_id):
        raise HTTPException(status_code=404, detail="Module not found")
    return Response(status_code=204)


@router.get("/packets")
async def list_packets(
    request: Request,
    source_ip: str | None = None,
    length: Annotated[int | None, Query(ge=0, le=65535)] = None,
    prefix_hex: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
):
    return runtime_from(request).udp.list_packets(
        source_ip=source_ip, length=length, prefix_hex=prefix_hex, limit=limit
    )


@router.delete("/packets", status_code=204)
async def clear_packets(request: Request):
    runtime_from(request).udp.clear()
    return Response(status_code=204)


@router.get("/packets/export")
async def export_packets(
    request: Request,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    source_ip: str | None = None,
    length: Annotated[int | None, Query(ge=0, le=65535)] = None,
    prefix_hex: str | None = None,
):
    runtime = runtime_from(request)
    records = runtime.udp.list_packets(source_ip=source_ip, length=length, prefix_hex=prefix_hex, limit=5000)
    if format == "csv":
        return PlainTextResponse(runtime.udp.export_csv(records), media_type="text/csv")
    return Response(
        content=json.dumps(records, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=neocontrol-capture.json"},
    )


@router.post("/protocol/send-scene")
async def send_scene(payload: SendSceneRequest, request: Request):
    try:
        return await runtime_from(request).send_scene(payload.scene_number)
    except (ProtocolValidationError, RuntimeError, OSError) as exc:
        raise protocol_error(exc) from exc


@router.post("/protocol/send-individual")
async def send_individual(payload: SendIndividualRequest, request: Request):
    try:
        return await runtime_from(request).send_individual(**payload.model_dump())
    except (ProtocolValidationError, PermissionError, RuntimeError, OSError) as exc:
        raise protocol_error(exc) from exc


@router.post("/protocol/send-raw")
async def send_raw(payload: SendRawRequest, request: Request):
    try:
        return await runtime_from(request).send_raw(payload.hex_payload)
    except (ProtocolValidationError, PermissionError, RuntimeError, OSError) as exc:
        raise protocol_error(exc) from exc


@router.post("/settings/protocol-lab")
async def set_protocol_lab(payload: ProtocolLabSetting, request: Request):
    try:
        await runtime_from(request).set_protocol_lab(payload.enabled, payload.confirmed)
    except PermissionError as exc:
        raise protocol_error(exc) from exc
    return {"enabled": runtime_from(request).protocol_lab_enabled}


@router.get("/diagnostics")
async def diagnostics(request: Request):
    runtime = runtime_from(request)
    return {
        "status": runtime.status(),
        "settings": {
            "broadcast_address": runtime.settings.broadcast_address,
            "udp_port": runtime.settings.udp_port,
            "capture_buffer_size": runtime.settings.capture_buffer_size,
            "discovery_prefix": runtime.settings.discovery_prefix,
            "mqtt_host_configured": bool(runtime.settings.mqtt_host),
            "mqtt_port": runtime.settings.mqtt_port,
        },
        "scenes": await runtime.list_scenes(),
        "modules": await runtime.list_modules(),
        "protocol_note": "function/subfunction mappings are experimental and intentionally not inferred",
    }

