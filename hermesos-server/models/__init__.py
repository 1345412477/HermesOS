try:
    from .schemas import (
        VoiceRequest,
        VoiceResponse,
        TextRequest,
        TextResponse,
        DeviceStatus,
        EventSummary,
        HealthResponse,
    )
except ImportError:
    from models.schemas import (  # type: ignore[no-redef]
        VoiceRequest,
        VoiceResponse,
        TextRequest,
        TextResponse,
        DeviceStatus,
        EventSummary,
        HealthResponse,
    )

__all__ = [
    "VoiceRequest",
    "VoiceResponse",
    "TextRequest",
    "TextResponse",
    "DeviceStatus",
    "EventSummary",
    "HealthResponse",
]
