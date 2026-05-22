# -*- coding: utf-8 -*-
"""
HermesOS Gateway - 海康威视摄像头适配器
实现 DeviceAdapter，支持 capture_frame, detect_motion 能力。
返回模拟数据，不需要实际连接 SDK。
"""

import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    from .base import DeviceAdapter
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from device_manager.plugins.base import DeviceAdapter


class HikvisionCameraAdapter(DeviceAdapter):
    """海康威视摄像头适配器（模拟）。"""

    vendor = "海康威视"
    model = "DS-2CD2T47G2-L"
    device_type = "camera"

    def __init__(self):
        self._connected = False
        self._config: Dict[str, Any] = {}

    async def connect(self, config: Dict[str, Any]) -> bool:
        """连接到海康摄像头（模拟）。

        Args:
            config: 包含 host, port, username, password
        """
        self._config = config
        host = config.get("host", "192.168.1.64")
        port = config.get("port", 554)

        # 模拟连接延迟
        time.sleep(0.05)

        self._connected = True
        print(f"[Hikvision] 已连接到 {host}:{port} (模拟)")
        return True

    async def disconnect(self) -> None:
        """断开连接。"""
        self._connected = False
        print("[Hikvision] 已断开连接 (模拟)")

    async def get_status(self) -> Dict[str, Any]:
        """获取摄像头状态。"""
        return {
            "online": self._connected,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "streaming": self._connected,
            "resolution": "2688x1520",
            "fps": 25,
            "bitrate": "4096 Kbps",
        }

    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行摄像头操作。

        支持的动作:
            - capture_frame: 抓拍一帧
            - detect_motion: 检测移动
        """
        if not self._connected:
            return {"success": False, "error": "设备未连接"}

        params = params or {}

        if action == "capture_frame":
            # 模拟抓拍
            channel = params.get("channel", 1)
            return {
                "success": True,
                "data": {
                    "action": "capture_frame",
                    "channel": channel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "image_url": f"http://{self._config.get('host', '192.168.1.64')}:8080/snap-{channel}-{int(time.time())}.jpg",
                    "resolution": "2688x1520",
                    "size_bytes": random.randint(120000, 380000),
                },
            }

        elif action == "detect_motion":
            # 模拟移动检测
            regions = params.get("regions", ["全屏"])
            motion_detected = random.choice([True, False, False, False])  # 25% 概率检测到
            return {
                "success": True,
                "data": {
                    "action": "detect_motion",
                    "regions": regions,
                    "motion_detected": motion_detected,
                    "confidence": round(random.uniform(0.85, 0.99), 2) if motion_detected else 0.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        else:
            return {"success": False, "error": f"不支持的操作: {action}"}

    async def get_capabilities(self) -> List[str]:
        """获取摄像头能力列表。"""
        return [
            "capture_frame",
            "detect_motion",
            "ptz_control",
            "stream_video",
            "set_osd",
        ]
