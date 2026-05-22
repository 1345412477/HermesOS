try:
    from .voice import router as voice_router
    from .device import router as device_router
except ImportError:
    from router.voice import router as voice_router  # type: ignore[no-redef]
    from router.device import router as device_router  # type: ignore[no-redef]

__all__ = ["voice_router", "device_router"]
