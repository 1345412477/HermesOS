"""HermesOS Server — FastAPI Application Entry Point.

Factory function create_app() builds the FastAPI application,
registers routes, and manages component lifecycles.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Support both relative (package) and absolute (standalone) imports
try:
    from .agent_bridge import HermesOSAgent
    from .config import get_config
    from .device_manager import DeviceManager, get_device_manager
    from .event_store import EventStore
    from .router.device import router as device_router
    from .router.voice import router as voice_router
    from .voice_engine import ASREngine, TTSEngine
except ImportError:
    from agent_bridge import HermesOSAgent  # type: ignore[no-redef]
    from config import get_config  # type: ignore[no-redef]
    from device_manager import DeviceManager, get_device_manager  # type: ignore[no-redef]
    from event_store import EventStore  # type: ignore[no-redef]
    from router.device import router as device_router  # type: ignore[no-redef]
    from router.voice import router as voice_router  # type: ignore[no-redef]
    from voice_engine import ASREngine, TTSEngine  # type: ignore[no-redef]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── lifespan (startup / shutdown) ─────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the FastAPI application."""
    # Startup
    logger.info("HermesOS Server starting up ...")
    cfg = get_config()

    # 设备管理层（原 Gateway 核心逻辑，整合进统一进程）
    # 使用 server 的 config.yaml（含设备配置）
    config_path = str(cfg._config_path) if hasattr(cfg, '_config_path') else None
    dm = get_device_manager(config_path=config_path)
    await dm.start()
    app.state.device_manager = dm

    app.state.agent_bridge = HermesOSAgent()
    app.state.asr_engine = ASREngine(
        model_name=cfg.get("voice_engine.asr.model", "base"),
        use_mock=cfg.get("voice_engine.asr.mock", True),
        mock_text=cfg.get("voice_engine.asr.mock_text", "你好，请问有什么可以帮助你的？"),
    )
    app.state.tts_engine = TTSEngine(
        voice=cfg.get("voice_engine.tts.voice", "zh-CN-XiaoxiaoNeural"),
        rate=cfg.get("voice_engine.tts.rate", "+0%"),
        pitch=cfg.get("voice_engine.tts.pitch", "+0Hz"),
    )
    app.state.event_store = EventStore(
        db_path=cfg.get("event_store.db_path", None),
    )

    await app.state.agent_bridge.start()

    logger.info("HermesOS Server ready — port 8765")

    yield  # Application runs here

    # Shutdown
    logger.info("HermesOS Server shutting down ...")
    if app.state.device_manager:
        await app.state.device_manager.stop()
    if app.state.agent_bridge:
        await app.state.agent_bridge.stop()
    if app.state.event_store:
        app.state.event_store.close()
    logger.info("HermesOS Server stopped")


# ── application factory ──────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="HermesOS Server",
        description="Voice-enabled smart home AI assistant server",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow all origins for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(voice_router)
    app.include_router(device_router)

    # Serve static files (test page at /console/)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/console", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


# ── direct runner ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:create_app",
        host="0.0.0.0",
        port=8765,
        reload=False,
        factory=True,
    )
