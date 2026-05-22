"""Device & system API router — device management, events, and health checks.

Now backed by the real DeviceManager (merged from Gateway) instead of
the old in-memory _devices dict.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

try:
    from ..models.schemas import (
        DeviceCommandRequest,
        DeviceRegisterRequest,
        DeviceStatus,
        EventSummary,
        HealthResponse,
    )
except ImportError:
    from models.schemas import (  # type: ignore[no-redef]
        DeviceCommandRequest,
        DeviceRegisterRequest,
        DeviceStatus,
        EventSummary,
        HealthResponse,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["device"])


# ── helpers ───────────────────────────────────────────────────


def _get_device_manager(request: Request):
    dm = request.app.state.device_manager
    if dm is None:
        raise HTTPException(status_code=503, detail="Device manager not available")
    return dm


def _get_event_store(request: Request):
    return request.app.state.event_store


# ── Device Routes ─────────────────────────────────────────────


@router.get("/api/devices", response_model=list[DeviceStatus])
async def list_devices(request: Request, device_type: Optional[str] = Query(None)):
    """Return all registered device statuses."""
    dm = _get_device_manager(request)
    devices = dm.list_devices(device_type=device_type)
    return [
        DeviceStatus(
            device_id=d.get("device_id", ""),
            name=d.get("name", ""),
            device_type=d.get("device_type", ""),
            location=d.get("location", ""),
            online=d.get("online", False),
            last_seen=None,
            status=d.get("status", "unknown"),
        )
        for d in devices
    ]


@router.get("/api/devices/{device_id}", response_model=DeviceStatus)
async def get_device(device_id: str, request: Request):
    """Get detailed status for a single device."""
    dm = _get_device_manager(request)
    device = dm.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    return DeviceStatus(
        device_id=device.get("device_id", ""),
        name=device.get("name", ""),
        device_type=device.get("device_type", ""),
        location=device.get("location", ""),
        online=device.get("online", False),
        last_seen=device.get("last_seen", ""),
        status=device.get("status", "unknown"),
    )


@router.post("/api/devices/{device_id}/command")
async def send_device_command(device_id: str, cmd: DeviceCommandRequest, request: Request):
    """Send a command to a specific device."""
    dm = _get_device_manager(request)
    result = await dm.send_command(device_id, cmd.command, cmd.params or {})

    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])

    # Store command event
    device = dm.get_device(device_id)
    try:
        store = _get_event_store(request)
        if store:
            store.store_event(
                EventSummary(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    device_id=device_id,
                    device_type=(device or {}).get("device_type", ""),
                    location=(device or {}).get("location", ""),
                    event_type="command",
                    result={"command": cmd.command, "params": cmd.params, "response": result},
                    source="api",
                )
            )
    except Exception:
        logger.exception("Failed to store command event")

    return {"status": "ok", "device_id": device_id, "command": cmd.command, "result": result}


@router.post("/api/devices/register")
async def register_device(body: DeviceRegisterRequest, request: Request):
    """Register a new device or update an existing one."""
    dm = _get_device_manager(request)
    device = dm.register_device(body.model_dump())

    # Store registration event
    try:
        store = _get_event_store(request)
        if store:
            store.store_event(
                EventSummary(
                    event_id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    device_id=body.device_id,
                    device_type=body.device_type or "unknown",
                    location=body.location or "未指定",
                    event_type="device_registered",
                    result={"name": body.name},
                    source="api",
                )
            )
    except Exception:
        logger.exception("Failed to store registration event")

    logger.info("Device registered: %s (%s)", body.device_id, body.name)
    return {"success": True, "device": device}


# ── Additional DeviceManager-exposed endpoints ───────────────


@router.get("/api/devices/{device_id}/status")
async def get_device_status(device_id: str, request: Request):
    """Get real-time device status from its adapter."""
    dm = _get_device_manager(request)
    status = await dm.get_device_status(device_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.get("/api/devices/{device_id}/capabilities")
async def get_device_capabilities(device_id: str, request: Request):
    """Get device capability list."""
    dm = _get_device_manager(request)
    caps = await dm.get_device_capabilities(device_id)
    if "error" in caps:
        raise HTTPException(status_code=404, detail=caps["error"])
    return caps


@router.get("/api/devices/{device_id}/pending")
async def poll_device_tasks(device_id: str, request: Request):
    """Remote device polls for pending commands (phone etc.)."""
    dm = _get_device_manager(request)
    tasks = dm.poll_tasks(device_id)
    return {"device_id": device_id, "tasks": tasks}


@router.post("/api/devices/{device_id}/result")
async def report_device_result(device_id: str, body: dict, request: Request):
    """Remote device reports command execution result."""
    dm = _get_device_manager(request)
    dm.report_result(
        device_id,
        body.get("task_id", ""),
        body.get("success", False),
        body.get("data"),
    )
    return {"status": "ok"}


# ── Event Routes ──────────────────────────────────────────────


@router.get("/api/events", response_model=list[EventSummary])
async def query_events(
    request: Request,
    device_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
):
    """Query events with optional filters."""
    store = _get_event_store(request)
    if store is None:
        raise HTTPException(status_code=503, detail="Event store not available")

    time_range: Optional[tuple[datetime, datetime]] = None
    if hours > 0:
        now = datetime.now(timezone.utc)
        time_range = (now - timedelta(hours=hours), now)

    try:
        return store.query_events(
            time_range=time_range,
            device_id=device_id,
            event_type=event_type,
            limit=limit,
        )
    except Exception as e:
        logger.exception("Event query failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Health ────────────────────────────────────────────────────


@router.get("/api/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Return system health status."""
    dm = _get_device_manager(request)
    devices = dm.list_devices()
    online_count = sum(1 for d in devices if d.get("online"))
    return HealthResponse(
        status="ok",
        version="0.1.0",
        devices_online=online_count,
        devices_total=len(devices),
    )
