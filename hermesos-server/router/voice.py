"""Voice API router — handles speech-to-text, text-to-speech, and agent interaction."""

import base64
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

try:
    from ..models.schemas import (
        EventSummary,
        TextRequest,
        TextResponse,
        VoiceRequest,
        VoiceResponse,
    )
except ImportError:
    from models.schemas import (  # type: ignore[no-redef]
        EventSummary,
        TextRequest,
        TextResponse,
        VoiceRequest,
        VoiceResponse,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


# ── helpers ───────────────────────────────────────────────────

def _get_agent_bridge(request: Request):
    """Retrieve the AgentBridge from app state."""
    bridge = request.app.state.agent_bridge
    if bridge is None:
        raise HTTPException(status_code=503, detail="Agent bridge not available")
    return bridge


def _get_asr(request: Request):
    return request.app.state.asr_engine


def _get_tts(request: Request):
    return request.app.state.tts_engine


def _get_event_store(request: Request):
    return request.app.state.event_store


# ── routes ────────────────────────────────────────────────────


@router.post("/api/voice", response_model=VoiceResponse)
async def voice_endpoint(request: Request, body: VoiceRequest):
    """Accept base64-encoded audio, transcribe → agent → TTS → return audio response."""
    # Decode audio
    try:
        audio_bytes = base64.b64decode(body.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    # ASR: speech → text
    asr = _get_asr(request)
    text = asr.transcribe(audio_bytes)
    if not text:
        text = "（未识别到语音内容）"

    # Agent bridge: process text
    bridge = _get_agent_bridge(request)
    try:
        agent_response = await bridge.process_text(text)
    except Exception as e:
        logger.exception("Agent bridge processing failed")
        raise HTTPException(status_code=500, detail=f"Agent processing error: {e}")

    # TTS: text → speech
    tts = _get_tts(request)
    response_audio = await tts.synthesize(agent_response)
    response_b64 = base64.b64encode(response_audio).decode("utf-8")

    # Store event
    try:
        store = _get_event_store(request)
        store.store_event(
            EventSummary(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                device_id="voice",
                device_type="voice_channel",
                location="server",
                event_type="voice_conversation",
                result={"input": text[:200], "output": agent_response[:200]},
                source="voice_api",
            )
        )
    except Exception:
        logger.exception("Failed to store event")

    return VoiceResponse(audio=response_b64, text=agent_response, transcribed=text)


@router.post("/api/voice/text", response_model=TextResponse)
async def voice_text_endpoint(request: Request, body: TextRequest):
    """Accept text input, process through agent, return text response."""
    bridge = _get_agent_bridge(request)

    try:
        agent_response = await bridge.process_text(body.text)
    except Exception as e:
        logger.exception("Agent bridge processing failed")
        raise HTTPException(status_code=500, detail=f"Agent processing error: {e}")

    # Store event
    try:
        store = _get_event_store(request)
        store.store_event(
            EventSummary(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                device_id="voice",
                device_type="voice_channel",
                location="server",
                event_type="text_conversation",
                result={"input": body.text[:200], "output": agent_response[:200]},
                source="text_api",
            )
        )
    except Exception:
        logger.exception("Failed to store event")

    return TextResponse(text=agent_response)
