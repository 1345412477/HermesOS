# -*- coding: utf-8 -*-
"""
HermesOS Gateway - 设备注册表
管理所有已注册设备的生命周期，支持内存 + JSON 持久化。
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DeviceRegistry:
    """设备注册表，管理所有已注册的设备信息。"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
        self._data_dir = data_dir
        os.makedirs(self._data_dir, exist_ok=True)
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._storage_path = os.path.join(self._data_dir, "devices.json")
        self._load_from_disk()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _load_from_disk(self) -> None:
        """从 JSON 文件加载已注册设备数据。"""
        if os.path.isfile(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    self._devices = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._devices = {}

    def _save_to_disk(self) -> None:
        """将当前设备数据保存到 JSON 文件。"""
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(self._devices, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 设备管理
    # ------------------------------------------------------------------
    def register(self, device_id: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """注册或更新设备。

        Args:
            device_id: 设备唯一标识
            info: 设备信息，至少包含 vendor, model, device_type

        Returns:
            注册后的设备完整信息
        """
        now = datetime.now(timezone.utc).isoformat()
        if device_id in self._devices:
            # 更新已有设备
            self._devices[device_id].update(info)
        else:
            self._devices[device_id] = {
                "device_id": device_id,
                "registered_at": now,
                **info,
            }
        self._devices[device_id]["gateway_received_at"] = now
        self._devices[device_id]["online"] = True
        self._devices[device_id]["status"] = "online"
        self._save_to_disk()
        return self._devices[device_id]

    def unregister(self, device_id: str) -> bool:
        """注销设备。

        Returns:
            成功注销返回 True，设备不存在返回 False
        """
        if device_id in self._devices:
            del self._devices[device_id]
            self._save_to_disk()
            return True
        return False

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取单个设备信息。"""
        return self._devices.get(device_id)

    def list_devices(self, device_type: str = None, online_only: bool = False) -> List[Dict[str, Any]]:
        """列出设备。

        Args:
            device_type: 按设备类型过滤，None 表示全部
            online_only: 仅返回在线设备
        """
        result = list(self._devices.values())
        if device_type:
            result = [d for d in result if d.get("device_type") == device_type]
        if online_only:
            result = [d for d in result if d.get("online", False)]
        return result

    def heartbeat(self, device_id: str) -> Optional[Dict[str, Any]]:
        """更新设备心跳时间。

        Returns:
            更新后的设备信息，设备不存在返回 None
        """
        if device_id not in self._devices:
            return None
        now = datetime.now(timezone.utc).isoformat()
        self._devices[device_id]["last_heartbeat"] = now
        self._devices[device_id]["gateway_received_at"] = now
        self._devices[device_id]["online"] = True
        self._devices[device_id]["status"] = "online"
        self._save_to_disk()
        return self._devices[device_id]


    def check_timeouts(self, timeout_seconds: int = 60) -> List[str]:
        """检查并标记超时离线设备。

        Args:
            timeout_seconds: 心跳超时秒数

        Returns:
            本次被标记为离线的设备 ID 列表
        """
        now = time.time()
        offline_ids = []
        for device_id, dev in self._devices.items():
            last_hb = dev.get("last_heartbeat")
            if last_hb:
                try:
                    last_time = datetime.fromisoformat(last_hb).timestamp()
                except (ValueError, OSError):
                    # 无法解析时间戳，使用 gateway_received_at
                    last_time = datetime.fromisoformat(
                        dev.get("gateway_received_at", "2000-01-01T00:00:00+00:00")
                    ).timestamp()
                if (now - last_time) > timeout_seconds:
                    dev["online"] = False
                    dev["status"] = "offline"
                    offline_ids.append(device_id)
        if offline_ids:
            self._save_to_disk()
        return offline_ids
