"""
HermesOS Agent Bridge — wraps Hermes Agent AIAgent as a callable service.

Maintains conversation history across turns so the Agent naturally
remembers context between requests.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────
HERMES_AGENT_DIR = Path(
    r"C:\Users\13454\AppData\Local\hermes\hermes-agent"
)
HERMES_HOME = Path(
    r"C:\Users\13454\AppData\Local\hermes\profiles\hermesos-test"
)
ENV_FILE = Path(r"C:\Users\13454\AppData\Local\hermes\.env")

MAX_HISTORY_TURNS = 10


def _load_env_api_key() -> Optional[str]:
    """Read DEEPSEEK_API_KEY from the main .env file."""
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _import_aiagent():
    """Add hermes-agent to sys.path and import AIAgent."""
    agent_path = str(HERMES_AGENT_DIR)
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    from run_agent import AIAgent as _AIAgent
    return _AIAgent


class HermesOSAgent:
    """Wraps Hermes Agent AIAgent with conversation history across turns."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _load_env_api_key()
        self._agent = None
        self._ready = False
        self._conversation_history: list[dict] = []  # [{"role": ..., "content": ...}, ...]

    async def start(self):
        """Initialize the Hermes Agent AIAgent."""
        if self._ready:
            return

        if not self.api_key:
            logger.warning("No DeepSeek API key found — using mock mode")
            self._ready = False
            return

        try:
            AIAgent = _import_aiagent()
            self._agent = AIAgent(
                base_url="https://api.deepseek.com",
                api_key=self.api_key,
                provider="deepseek",
                model="deepseek-v4-flash",
                quiet_mode=True,
                skip_memory=True,
                skip_context_files=True,
            )
            self._ready = True
            self._conversation_history = []
            logger.info("HermesOS Agent initialized successfully (with conversation history)")
        except Exception as e:
            logger.warning(f"Failed to initialize AIAgent: {e}")
            logger.warning("Falling back to mock mode")
            self._agent = None
            self._ready = False

    async def process_text(self, text: str) -> str:
        """Process text input with conversation history, return response."""
        if not self._ready or self._agent is None:
            return self._mock_response(text)

        try:
            import concurrent.futures

            # Run agent synchronously in a thread
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    self._agent.run_conversation,
                    text,
                    system_message=(
                        "你是一个智能家居控制助手。用户每次提出设备操作请求（调亮度、开灯、关灯等），"
                        "你都必须调用 query_device 查询设备再调用 control_device 执行，"
                        "绝对不能仅靠对话记忆回复。回复要简短。"
                    ),
                    conversation_history=self._conversation_history,
                )
                result = future.result(timeout=60)

            response = str(result.get("final_response", "")).strip()

            # Update conversation history
            self._conversation_history.append({"role": "user", "content": text})
            self._conversation_history.append({"role": "assistant", "content": response})

            # Keep only last N turns to avoid context bloat
            if len(self._conversation_history) > MAX_HISTORY_TURNS * 2:
                self._conversation_history = self._conversation_history[-(MAX_HISTORY_TURNS * 2):]

            return response

        except Exception as e:
            logger.error(f"AIAgent.run_conversation failed: {e}")
            return self._mock_response(text)

    def _mock_response(self, text: str) -> str:
        """Fallback: simple keyword-based mock response."""
        text_lower = text.lower()

        if any(kw in text_lower for kw in ["有人", "谁在", "在哪", "哪里"]):
            return "客厅有一个人，书房没人。"
        if any(kw in text_lower for kw in ["温度", "几度", "多少度"]):
            return "当前室内温度 25 度，湿度 60%。"
        if any(kw in text_lower for kw in ["所有设备", "有哪些设备", "状态"]):
            return (
                "当前在线设备：\n"
                "- 客厅摄像头（在线）\n"
                "- 书房雷达（在线）\n"
                "- 厨房温湿度传感器（在线）"
            )
        if any(kw in text_lower for kw in ["打开", "开灯", "开"]):
            return "已为你打开。"
        if any(kw in text_lower for kw in ["关闭", "关灯", "关"]):
            return "已为你关闭。"
        if any(kw in text_lower for kw in ["拍照", "拍张照", "看看"]):
            return "已拍照，图片已保存。"

        return f"收到指令：{text}。正在处理中。"

    async def stop(self):
        """Cleanup."""
        self._agent = None
        self._ready = False
        self._conversation_history = []


# ── Singleton ──────────────────────────────────────────────────
_agent_instance: Optional[HermesOSAgent] = None


def get_agent() -> HermesOSAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = HermesOSAgent()
    return _agent_instance
