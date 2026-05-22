# -*- coding: utf-8 -*-
"""
HermesOS Gateway - HLK-LD2410 毫米波雷达适配器
实现 DeviceAdapter，支持 detect_presence, count_people 能力。
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


class LD2410RadarAdapter(DeviceAdapter):
    """HLK-LD2410 毫米波雷达适配器（模拟）。"""

    vendor = "HI-LINK"
    model = "LD2410"
    device_type = "radar"

    def __init__(self):
        self._connected = False
        self._config: Dict[str, Any] = {}

    async def connect(self, config: Dict[str, Any]) -> bool:
        """连接到 LD2410 雷达（模拟）。

        Args:
            config: 包含 port (串口) 或 host (TCP)
        """
        self._config = config
        port = config.get("port", "/dev/ttyUSB0")
        baudrate = config.get("baudrate", 115200)

        # 模拟连接延迟
        time.sleep(0.05)

        self._connected = True
        print(f"[LD2410] 已连接到 {port}@{baudrate} (模拟)")
        return True

    async def disconnect(self) -> None:
        """断开连接。"""
        self._connected = False
        print("[LD2410] 已断开连接 (模拟)")

    async def get_status(self) -> Dict[str, Any]:
        """获取雷达状态。"""
        return {
            "online": self._connected,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "firmware": "v2.4.1",
            "sensitivity": self._config.get("sensitivity", 7),
        }

    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行雷达操作。

        支持的动作:
            - detect_presence: 检测人员存在
            - count_people: 统计人数
        """
        if not self._connected:
            return {"success": False, "error": "设备未连接"}

        params = params or {}

        if action == "detect_presence":
            # 模拟人员存在检测
            threshold = params.get("threshold", 0.5)
            # 70% 概率检测到有人
            presence = random.choice([True, True, True, True, True, True, True, False, False, False])
            moving = presence and random.choice([True, True, False])
            stationary = presence and (not moving) if presence else False

            return {
                "success": True,
                "data": {
                    "action": "detect_presence",
                    "presence_detected": presence,
                    "moving": moving,
                    "stationary": stationary,
                    "distance_cm": random.randint(50, 600) if presence else 0,
                    "confidence": round(random.uniform(0.70, 0.99), 2) if presence else 0.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        elif action == "count_people":
            # 模拟人数统计
            min_people = params.get("min", 0)
            max_people = params.get("max", 5)
            count = random.randint(min_people, max_people)

            return {
                "success": True,
                "data": {
                    "action": "count_people",
                    "count": count,
                    "zone": params.get("zone", "default"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }

        else:
            return {"success": False, "error": f"不支持的操作: {action}"}

    async def get_capabilities(self) -> List[str]:
        """获取雷达能力列表。"""
        return [
            "detect_presence",
            "count_people",
            "fall_detection",
            "sleep_monitor",
        ]
