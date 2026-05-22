# -*- coding: utf-8 -*-
"""
HermesOS Device Manager — 统一的设备管理层
封装 PluginEngine + DeviceRegistry，提供设备查询、指令下发、注册等接口。
替代原 Gateway（aiohttp 进程）的全部业务逻辑。
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from .config import Config
    from .plugin_engine import PluginEngine
    from .registry import DeviceRegistry
except ImportError:
    from device_manager.config import Config
    from device_manager.plugin_engine import PluginEngine
    from device_manager.registry import DeviceRegistry

logger = logging.getLogger(__name__)


class DeviceManager:
    """统一的设备管理层，替代原 Gateway 的 HTTP 层。"""

    def __init__(self, config_path: Optional[str] = None):
        self._config = Config(config_path)
        self._registry = DeviceRegistry(
            data_dir=self._config.get("gateway.data_dir", str(Path(__file__).parent / "data"))
        )
        self._plugin_engine = PluginEngine(config=self._config, registry=self._registry)
        self._heartbeat_timeout = self._config.get("gateway.heartbeat_timeout", 60)
        self._running = False
        self._bg_tasks: list = []
        self._ready = False
        # 远程设备命令队列（手机等轮询设备）
        self._remote_tasks: dict[str, list[dict]] = {}
        self._remote_results: dict[str, list[dict]] = {}

    # ── 生命周期 ─────────────────────────────────────────────

    async def start(self) -> None:
        """启动设备管理层：扫描插件、实例化适配器、启动设备。"""
        logger.info("DeviceManager 启动中 ...")
        self._running = True

        self._plugin_engine.scan_plugins()
        self._plugin_engine.instantiate_adapters()
        results = await self._plugin_engine.start_all()

        online_count = sum(1 for v in results.values() if v)
        logger.info(f"设备适配器启动完成: {online_count}/{len(results)} 个在线")

        # 后台心跳检查
        self._bg_tasks.append(asyncio.create_task(self._heartbeat_check_loop()))
        self._ready = True
        logger.info("DeviceManager 就绪")

    async def stop(self) -> None:
        """停止设备管理层。"""
        self._running = False
        self._ready = False
        for task in self._bg_tasks:
            task.cancel()
        self._bg_tasks.clear()
        await self._plugin_engine.stop_all()
        logger.info("DeviceManager 已停止")

    @property
    def ready(self) -> bool:
        return self._ready

    # ── 设备查询 ─────────────────────────────────────────────

    def list_devices(self, device_type: str = None, online_only: bool = False) -> list[dict]:
        """列出所有设备，支持按类型和在线状态筛选。"""
        return self._registry.list_devices(device_type=device_type, online_only=online_only)

    def get_device(self, device_id: str) -> Optional[dict]:
        """获取单个设备信息。"""
        return self._registry.get_device(device_id)

    # ── 设备注册（远程设备用） ────────────────────────────────

    def register_device(self, device_data: dict) -> dict:
        """注册一个远程设备（如手机 Agent Client）。"""
        device_id = device_data.get("device_id") or device_data.get("id")
        if not device_id:
            raise ValueError("缺少 device_id")

        device = {
            "device_id": device_id,
            "device_type": device_data.get("device_type", device_data.get("type", "unknown")),
            "location": device_data.get("location", "未指定"),
            "name": device_data.get("name", device_id),
            "capabilities": device_data.get("capabilities", []),
            "status": "online",
            "online": True,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        self._registry.register(device_id, device)
        return device

    # ── 设备指令 ─────────────────────────────────────────────

    async def send_command(self, device_id: str, action: str, params: dict = None) -> dict:
        """向设备发送指令。"""
        adapter = self._plugin_engine.get_adapter(device_id)
        if adapter is None:
            device = self._registry.get_device(device_id)
            if device:
                logger.info(f"Mock command: {action} -> {device_id}")
                return {
                    "success": True,
                    "mock": True,
                    "device_id": device_id,
                    "action": action,
                    "message": f"（模拟）已向 {device.get('name', device_id)} 发送指令: {action}",
                }
            return {"success": False, "error": f"设备适配器未找到: {device_id}"}

        try:
            result = await adapter.execute(action, params or {})
            return result
        except Exception as e:
            logger.error(f"执行设备命令失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_device_status(self, device_id: str) -> dict:
        """获取设备实时状态。"""
        adapter = self._plugin_engine.get_adapter(device_id)
        if adapter is None:
            return {"error": f"设备适配器未找到: {device_id}"}
        return await adapter.get_status()

    async def get_device_capabilities(self, device_id: str) -> dict:
        """获取设备能力列表。"""
        adapter = self._plugin_engine.get_adapter(device_id)
        if adapter is None:
            return {"error": f"设备适配器未找到: {device_id}"}
        caps = await adapter.get_capabilities()
        return {"device_id": device_id, "capabilities": caps}

    # ── 远程设备命令队列 ─────────────────────────────────────
    # 用于手机等远端设备：DeviceManager 存指令，设备轮询取

    def enqueue_command(self, device_id: str, action: str, params: dict = None) -> str:
        """为远程设备暂存一条待执行指令，返回 task_id。"""
        import uuid
        task = {
            "id": str(uuid.uuid4()),
            "action": action,
            "params": params or {},
        }
        if device_id not in self._remote_tasks:
            self._remote_tasks[device_id] = []
        self._remote_tasks[device_id].append(task)
        return task["id"]

    def poll_tasks(self, device_id: str) -> list[dict]:
        """远程设备轮询待办指令（取走即删除）。"""
        return self._remote_tasks.pop(device_id, [])

    def report_result(self, device_id: str, task_id: str, success: bool, data: dict = None):
        """远程设备回报执行结果。"""
        if device_id not in self._remote_results:
            self._remote_results[device_id] = []
        self._remote_results[device_id].append({
            "task_id": task_id,
            "success": success,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── 后台任务 ─────────────────────────────────────────────

    async def _heartbeat_check_loop(self) -> None:
        """定期检查设备超时。"""
        while self._running:
            try:
                offline_ids = self._registry.check_timeouts(self._heartbeat_timeout)
                if offline_ids:
                    logger.warning(f"设备心跳超时: {offline_ids}")
            except Exception as e:
                logger.error(f"心跳检查异常: {e}")
            await asyncio.sleep(10)


# ── Singleton ────────────────────────────────────────────
_device_manager: Optional[DeviceManager] = None


def get_device_manager(config_path: Optional[str] = None) -> DeviceManager:
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager(config_path=config_path)
    return _device_manager
