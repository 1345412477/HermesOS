"""Automatic Speech Recognition (ASR) Engine.

Supports two modes:
  - pocketsphinx: offline speech recognition (no downloads needed)
  - mock mode: returns preset text for development/testing
"""

import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import pocketsphinx
try:
    import speech_recognition as sr

    _HAS_SPEECH_REC = True
except ImportError:
    _HAS_SPEECH_REC = False


class ASREngine:
    """Speech recognition engine powered by pocketsphinx (offline) or mock."""

    def __init__(
        self,
        model_name: str = "base",
        use_mock: bool = False,
        mock_text: str = "你好，请问有什么可以帮助你的？",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self._model_name = model_name
        self._use_mock = use_mock
        self._mock_text = mock_text
        self._recognizer = sr.Recognizer() if _HAS_SPEECH_REC else None

        if self._use_mock:
            logger.info("ASR engine in mock mode")
        elif _HAS_SPEECH_REC:
            # Test pocketsphinx is functional
            try:
                import pocketsphinx
                logger.info("ASR engine initialised with pocketsphinx (offline, Chinese)")
            except ImportError:
                logger.warning("pocketsphinx not available, falling back to mock")
                self._use_mock = True
        else:
            logger.warning("speech_recognition not installed, falling back to mock")
            self._use_mock = True

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw audio bytes to text.

        Args:
            audio_bytes: WAV audio data in bytes.

        Returns:
            Transcribed text string.
        """
        if self._use_mock or self._recognizer is None:
            logger.debug("ASR mock mode — returning preset text")
            return self._mock_text

        # Write audio bytes to a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with sr.AudioFile(tmp_path) as source:
                audio = self._recognizer.record(source)

            text = self._recognizer.recognize_sphinx(audio, language="zh-CN")
            logger.debug("ASR transcribed: %s", text)
            return text
        except sr.UnknownValueError:
            logger.warning("ASR could not understand audio")
            return ""
        except sr.RequestError as e:
            logger.warning("ASR error: %s", e)
            return self._mock_text
        except Exception:
            logger.exception("ASR transcription failed — falling back to mock text")
            return self._mock_text
        finally:
            Path(tmp_path).unlink(missing_ok=True)
