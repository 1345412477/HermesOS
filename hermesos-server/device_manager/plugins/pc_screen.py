# -*- coding: utf-8 -*-
"""
HermesOS Gateway - PC 屏幕亮度适配器
通过 screen_brightness_control 控制 Windows 显示器的亮度。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from .base import DeviceAdapter
except ImportError:
    from device_manager.plugins.base import DeviceAdapter  # type: ignore[no-redef]

import screen_brightness_control as sbc

logger = logging.getLogger(__name__)


class PCScreenAdapter(DeviceAdapter):
    """PC 屏幕亮度适配器，控制 Windows 显示器的亮度。"""

    vendor = "pc"
    model = "windows-screen"
    device_type = "screen"

    def __init__(self):
        self._connected = False
        self._device_id = ""
        self._config: Dict[str, Any] = {}
        self._monitor_count = 0
        self._monitor_index = 0  # 0 = 主显示器，-1 = 所有显示器

    async def connect(self, config: Dict[str, Any] = None) -> bool:
        """连接到本地屏幕。"""
        self._config = config or {}
        self._device_id = self._config.get("device_id", "pc_screen")

        try:
            monitors = sbc.list_monitors()
            self._monitor_count = len(monitors)
            # 如果配置了 monitor_index，使用指定的显示器
            self._monitor_index = self._config.get("monitor_index", -1)
            if self._monitor_index >= self._monitor_count:
                self._monitor_index = -1  # 回退到所有显示器

            self._connected = True
            logger.info(
                f"PC屏幕适配器已连接: {self._device_id} "
                f"[{self._monitor_count} 台显示器, index={self._monitor_index}]"
            )
            return True
        except Exception as e:
            logger.error(f"PC屏幕适配器连接失败: {e}")
            return False

    async def disconnect(self) -> None:
        self._connected = False
        logger.info(f"PC屏幕适配器已断开: {self._device_id}")

    async def get_status(self) -> Dict[str, Any]:
        """获取屏幕当前状态。"""
        brightness = self._get_brightness()
        return {
            "online": self._connected,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "device_id": self._device_id,
            "brightness": brightness,
            "monitor_count": self._monitor_count,
        }

    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行屏幕操作。"""
        params = params or {}

        if action == "get_brightness":
            brightness = self._get_brightness()
            return {"success": True, "data": {"brightness": brightness}}

        if action == "set_brightness":
            level = params.get("level") or params.get("brightness")
            if level is None:
                return {"success": False, "error": "缺少亮度参数 level/brightness"}
            try:
                level = int(level)
                level = max(0, min(100, level))  # 限制在 0-100
                sbc.set_brightness(level, display=self._monitor_index)
                actual = self._get_brightness()
                logger.info(f"亮度已调整: target={level}, actual={actual}")
                return {
                    "success": True,
                    "data": {
                        "target": level,
                        "actual": actual,
                        "message": f"屏幕亮度已调整为 {level}%",
                    },
                }
            except Exception as e:
                logger.error(f"设置亮度失败: {e}")
                return {"success": False, "error": f"设置亮度失败: {e}"}

        if action == "get_status":
            return await self.get_status()

        return {"success": False, "error": f"屏幕不支持操作: {action}"}

    async def get_capabilities(self) -> List[str]:
        return ["get_brightness", "set_brightness", "get_status"]

    def _get_brightness(self) -> Optional[int]:
        """获取当前屏幕亮度。"""
        try:
            brightness_list = sbc.get_brightness(display=self._monitor_index)
            if brightness_list:
                return int(brightness_list[0])
            return None
        except Exception:
            return None
