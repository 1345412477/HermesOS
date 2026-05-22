"""HermesOS Server Data Models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Voice / Text ──────────────────────────────────────────────

class VoiceRequest(BaseModel):
    """Incoming voice request with base64-encoded audio."""
    audio: str = Field(..., description="Base64-encoded audio data")


class VoiceResponse(BaseModel):
    """Voice response containing base64 audio and transcribed text."""
    audio: str = Field(..., description="Base64-encoded response audio data")
    text: str = Field(..., description="Agent response text")
    transcribed: str = Field("", description="Original transcribed text from ASR")


class TextRequest(BaseModel):
    """Incoming text request."""
    text: str = Field(..., min_length=1, description="Text input from user")


class TextResponse(BaseModel):
    """Plain text response."""
    text: str = Field(..., description="Response text from the agent")


# ── Device ────────────────────────────────────────────────────

class DeviceStatus(BaseModel):
    """Current status of a registered device."""
    device_id: str
    name: str
    device_type: str
    location: str
    online: bool = False
    last_seen: Optional[datetime] = None
    status: str = "unknown"


class DeviceRegisterRequest(BaseModel):
    """Payload for device registration."""
    device_id: str
    name: str
    device_type: str
    location: str = "unknown"


class DeviceCommandRequest(BaseModel):
    """Command to send to a device."""
    command: str
    params: Optional[dict] = None


# ── Event ─────────────────────────────────────────────────────

class EventSummary(BaseModel):
    """Summarised event record."""
    event_id: str
    timestamp: datetime
    device_id: str
    device_type: str
    location: str
    event_type: str
    result: Optional[dict] = None
    source: str = "unknown"


# ── Health ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health-check response."""
    status: str = "ok"
    version: str = "0.1.0"
    devices_online: int = 0
    devices_total: int = 0
