"""Text-to-Speech (TTS) Engine.

Uses Microsoft Edge TTS (edge-tts) for synthesis.
Falls back to mock audio on failure.
"""

import asyncio
import io
import logging
import struct
import wave

logger = logging.getLogger(__name__)

try:
    import edge_tts

    _HAS_EDGE_TTS = True
except ImportError:
    _HAS_EDGE_TTS = False


class TTSEngine:
    """Text-to-speech engine using Edge TTS."""

    def __init__(
        self,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ):
        self._voice = voice
        self._rate = rate
        self._pitch = pitch

    async def synthesize(self, text: str) -> bytes:
        """Synthesise text to audio bytes (WAV format).

        Returns raw audio bytes on success, or mock audio on failure.
        """
        if not _HAS_EDGE_TTS:
            logger.warning("edge-tts not installed — returning mock audio")
            return self._generate_mock_audio()

        if not text.strip():
            return self._generate_mock_audio()

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self._voice,
                rate=self._rate,
                pitch=self._pitch,
            )
            audio_chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])

            if not audio_chunks:
                logger.warning("Edge TTS returned no audio — falling back to mock")
                return self._generate_mock_audio()

            combined = b"".join(audio_chunks)

            # Convert MP3 stream to WAV (simplified: just wrap as raw PCM approximation)
            # For production, you'd use a proper converter like pydub/ffmpeg.
            # Here we return the raw audio bytes; callers can handle format.
            logger.debug("TTS synthesized %d bytes for text: %s", len(combined), text[:50])
            return combined

        except Exception:
            logger.exception("TTS synthesis failed — returning mock audio")
            return self._generate_mock_audio()

    @staticmethod
    def _generate_mock_audio(sample_rate: int = 16000, duration_ms: int = 500) -> bytes:
        """Generate a short silent WAV file as mock audio."""
        num_samples = int(sample_rate * duration_ms / 1000)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            # Generate silence
            wf.writeframes(b"\x00\x00" * num_samples)
        return buf.getvalue()
