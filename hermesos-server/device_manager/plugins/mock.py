# -*- coding: utf-8 -*-
"""
HermesOS Gateway - Mock Device Adapter
模拟设备适配器，用于测试环境。按设备类型返回对应能力。"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    from .base import DeviceAdapter
except ImportError:
    from device_manager.plugins.base import DeviceAdapter

logger = logging.getLogger(__name__)

# ── 各设备类型的能力配置 ─────────────────────────────────
CAPABILITY_PROFILES = {
    "smart_light": {
        "actions": ["turn_on", "turn_off", "toggle", "set_brightness", "set_color", "get_status"],
        "state_keys": ["power", "brightness"],
        "responses": {
            "turn_on": {"success": True, "data": {"state": "on", "message": "灯已开启"}},
            "turn_off": {"success": True, "data": {"state": "off", "message": "灯已关闭"}},
            "toggle": {"success": True, "data": {"state": "toggled", "message": "灯已切换"}},
            "set_brightness": {"success": True, "data": {"brightness": None, "message": "亮度已调节"}},
            "set_color": {"success": True, "data": {"color": None, "message": "颜色已设置"}},
            "get_status": {"success": True, "data": {"status": "normal"}},
        },
    },
    "camera": {
        "actions": ["detect_face", "capture_frame", "start_recording", "stop_recording", "get_status"],
        "state_keys": ["recording"],
        "responses": {
            "detect_face": {"success": True, "data": {"faces": [], "count": 0}},
            "capture_frame": {"success": True, "data": {"image": "mock_frame", "resolution": "1920x1080"}},
            "start_recording": {"success": True, "data": {"recording": True, "message": "录像已开始"}},
            "stop_recording": {"success": True, "data": {"recording": False, "message": "录像已停止"}},
            "get_status": {"success": True, "data": {"status": "normal", "uptime": 3600}},
        },
    },
    "radar": {
        "actions": ["detect_presence", "get_distance", "get_status"],
        "state_keys": ["present"],
        "responses": {
            "detect_presence": {"success": True, "data": {"present": False, "distance": None}},
            "get_distance": {"success": True, "data": {"distance": 0.0, "unit": "meters"}},
            "get_status": {"success": True, "data": {"status": "normal", "uptime": 3600}},
        },
    },
    "lock": {
        "actions": ["lock", "unlock", "get_status"],
        "state_keys": ["locked"],
        "responses": {
            "lock": {"success": True, "data": {"state": "locked", "message": "已上锁"}},
            "unlock": {"success": True, "data": {"state": "unlocked", "message": "已解锁"}},
            "get_status": {"success": True, "data": {"status": "normal"}},
        },
    },
    "curtain": {
        "actions": ["open", "close", "set_position", "get_status"],
        "state_keys": ["position"],
        "responses": {
            "open": {"success": True, "data": {"state": "open", "message": "窗帘已打开"}},
            "close": {"success": True, "data": {"state": "closed", "message": "窗帘已关闭"}},
            "set_position": {"success": True, "data": {"position": None, "message": "位置已调整"}},
            "get_status": {"success": True, "data": {"status": "normal"}},
        },
    },
    "thermostat": {
        "actions": ["set_temperature", "set_mode", "get_status"],
        "state_keys": ["temperature", "mode"],
        "responses": {
            "set_temperature": {"success": True, "data": {"temperature": None, "message": "温度已设置"}},
            "set_mode": {"success": True, "data": {"mode": None, "message": "模式已切换"}},
            "get_status": {"success": True, "data": {"status": "normal", "temperature": 25}},
        },
    },
}

DEFAULT_RESPONSE = {"success": False, "error": "该设备不支持此操作"}

# ── 从 device_id 推断设备类型的启发式规则 ──
DEVICE_ID_TYPE_HINTS = {
    "light_": "smart_light",
    "_light": "smart_light",
    "lamp": "smart_light",
    "cam": "camera",
    "camera": "camera",
    "radar": "radar",
    "sensor": "radar",
    "lock": "lock",
    "door": "lock",
    "curtain": "curtain",
    "thermo": "thermostat",
}


def _infer_mock_type(device_id: str, name: str = "") -> str:
    """通过 device_id 或 name 推断模拟的设备类型。"""
    text = (device_id + " " + name).lower()
    for hint, mock_type in DEVICE_ID_TYPE_HINTS.items():
        if hint in text:
            return mock_type
    return "smart_light"  # 默认


class MockAdapter(DeviceAdapter):
    """模拟设备适配器，根据 mock_type 返回对应的能力和响应。"""

    vendor = "mock"
    model = "mock-device"
    device_type = "mock_adapter"

    def __init__(self):
        self._connected = False
        self._device_id = ""
        self._mock_type = "smart_light"
        self._config = {}
        self._state = {}

    async def connect(self, config: Dict[str, Any] = None) -> bool:
        self._config = config or {}
        self._device_id = self._config.get("device_id", "mock_device")
        # 从配置或 device_id 推断设备类型
        self._mock_type = self._config.get("mock_type", "")
        if not self._mock_type:
            dev_name = self._config.get("name", "")
            self._mock_type = _infer_mock_type(self._device_id, dev_name)

        profile = CAPABILITY_PROFILES.get(self._mock_type, CAPABILITY_PROFILES["smart_light"])
        # 初始化状态
        self._state = {k: None for k in profile["state_keys"]}
        if "power" in profile["state_keys"]:
            self._state["power"] = "off"
        if "brightness" in profile["state_keys"]:
            self._state["brightness"] = 50
        if "temperature" in profile["state_keys"]:
            self._state["temperature"] = 25
        if "position" in profile["state_keys"]:
            self._state["position"] = 0
        if "present" in profile["state_keys"]:
            self._state["present"] = False

        await asyncio.sleep(0.1)
        self._connected = True
        logger.info(f"Mock适配器已连接: {self._device_id} [type={self._mock_type}]")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info(f"Mock适配器已断开: {self._device_id}")

    async def get_status(self) -> Dict[str, Any]:
        return {
            "online": self._connected,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "state": self._state,
            "device_id": self._device_id,
            "mock_type": self._mock_type,
        }

    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        params = params or {}
        profile = CAPABILITY_PROFILES.get(self._mock_type, CAPABILITY_PROFILES["smart_light"])

        # 检查动作是否在当前设备类型的能力范围内
        if action not in profile["actions"]:
            logger.warning(f"{self._device_id}({self._mock_type}) 不支持操作: {action}")
            return {"success": False, "error": f"设备 {self._device_id} 不支持操作: {action}"}

        logger.info(f"Mock执行: {self._device_id}({self._mock_type}) -> {action}({params})")

        # 更新内部状态
        if action == "turn_on":
            self._state["power"] = "on"
        elif action == "turn_off":
            self._state["power"] = "off"
        elif action == "toggle":
            self._state["power"] = "off" if self._state.get("power") == "on" else "on"
        elif action == "set_brightness":
            self._state["brightness"] = params.get("level", params.get("brightness", 50))
        elif action == "set_temperature":
            self._state["temperature"] = params.get("temperature", 25)
        elif action == "lock":
            self._state["locked"] = True
        elif action == "unlock":
            self._state["locked"] = False
        elif action == "detect_presence":
            self._state["present"] = params.get("present", False)
        elif action == "set_position":
            self._state["position"] = params.get("position", 50)

        response = dict(profile["responses"].get(action, DEFAULT_RESPONSE))
        # 注入当前状态到回复中
        if action == "set_brightness":
            response["data"]["brightness"] = self._state.get("brightness", 50)
        elif action == "set_temperature":
            response["data"]["temperature"] = self._state.get("temperature", 25)
        elif action == "set_position":
            response["data"]["position"] = self._state.get("position", 50)
        elif action == "detect_presence":
            response["data"]["present"] = self._state.get("present", False)
            response["data"]["distance"] = params.get("distance", 0.0)

        await asyncio.sleep(0.05)
        return response

    async def get_capabilities(self) -> List[str]:
        profile = CAPABILITY_PROFILES.get(self._mock_type, CAPABILITY_PROFILES["smart_light"])
        return list(profile["actions"])
