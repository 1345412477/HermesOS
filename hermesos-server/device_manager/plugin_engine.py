# -*- coding: utf-8 -*-
"""
HermesOS Gateway - 插件引擎
扫描 plugins/ 目录加载设备适配器，管理适配器生命周期。
"""

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Any, Dict, Optional

try:
    from .plugins.base import DeviceAdapter
except ImportError:
    from plugins.base import DeviceAdapter

logger = logging.getLogger(__name__)


class PluginEngine:
    """插件引擎，负责扫描、加载和管理设备适配器插件。"""

    def __init__(self, config=None, registry=None):
        self._config = config
        self._registry = registry
        self._adapters: Dict[str, DeviceAdapter] = {}       # adapter_key -> adapter 实例
        self._device_adapter_map: Dict[str, str] = {}       # device_id -> adapter_key
        self._adapter_classes: Dict[str, type] = {}          # adapter_key -> adapter 类

    # ------------------------------------------------------------------
    # 插件扫描
    # ------------------------------------------------------------------
    def scan_plugins(self) -> Dict[str, type]:
        """扫描 plugins/ 目录，发现所有 DeviceAdapter 子类。

        Returns:
            {adapter_key: adapter_class} 字典
        """
        plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
        found = {}

        for _, module_name, is_pkg in pkgutil.iter_modules([plugins_dir]):
            if is_pkg or module_name in ("base", "__init__"):
                continue
            try:
                # Use file-based import to avoid package dependency issues
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    os.path.join(plugins_dir, f"{module_name}.py")
                )
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, DeviceAdapter)
                        and obj is not DeviceAdapter
                        and not inspect.isabstract(obj)
                    ):
                        adapter_key = f"{obj.vendor}:{obj.model}:{obj.device_type}".lower()
                        found[adapter_key] = obj
                        logger.info(f"发现设备适配器: {adapter_key} -> {obj.__name__}")
            except Exception as e:
                logger.error(f"加载插件模块 {module_name} 失败: {e}")

        self._adapter_classes.update(found)
        return found

    # ------------------------------------------------------------------
    # 实例化与生命周期
    # ------------------------------------------------------------------
    def instantiate_adapters(self, devices_config: list = None) -> Dict[str, DeviceAdapter]:
        """根据配置实例化设备适配器。

        Args:
            devices_config: 设备配置列表，每项包含 vendor, model, device_type, device_id, config

        Returns:
            {device_id: adapter_instance} 字典
        """
        if devices_config is None:
            # 从 Config 读取设备列表
            if self._config:
                devices_config = self._config.get("devices", [])
            else:
                devices_config = []

        self._adapters.clear()
        self._device_adapter_map.clear()

        for dev_cfg in devices_config:
            vendor = dev_cfg.get("vendor", "")
            model = dev_cfg.get("model", "")
            device_type = dev_cfg.get("device_type", "")
            device_id = dev_cfg.get("device_id", "")
            adapter_config = dev_cfg.get("config", {})

            adapter_key = f"{vendor}:{model}:{device_type}".lower()
            adapter_cls = self._adapter_classes.get(adapter_key)

            if adapter_cls is None:
                # 尝试只按 device_type 匹配
                for key, cls in self._adapter_classes.items():
                    if cls.device_type == device_type and cls.vendor == vendor:
                        adapter_cls = cls
                        adapter_key = key
                        break

            if adapter_cls is None:
                logger.warning(f"未找到适配器: {adapter_key}，设备 {device_id} 将无法连接")
                continue

            # 每个设备独立实例（防止同类设备共享同一 key 导致覆盖）
            adapter = adapter_cls()
            adapter_key = f"{vendor}:{model}:{device_type}:{device_id}".lower()
            self._adapters[adapter_key] = adapter
            self._device_adapter_map[device_id] = adapter_key
            logger.info(f"适配器已实例化: {device_id} -> {adapter_key}")

        return {did: self._adapters[key] for did, key in self._device_adapter_map.items()}

    async def start_all(self) -> Dict[str, bool]:
        """启动所有适配器（执行 connect）。

        Returns:
            {device_id: success} 字典
        """
        results = {}
        for device_id, adapter_key in self._device_adapter_map.items():
            adapter = self._adapters.get(adapter_key)
            if adapter is None:
                results[device_id] = False
                continue

            # 获取该设备的配置
            config = {}
            dev_name = device_id
            dev_location = "unknown"
            if self._config:
                devices_cfg = self._config.get("devices", [])
                for dc in devices_cfg:
                    if dc.get("device_id") == device_id:
                        config = dc.get("config", {})
                        # 注入设备基本信息到 config，方便适配器获取
                        config["device_id"] = device_id
                        config["name"] = dc.get("name", device_id)
                        config["location"] = dc.get("location", "unknown")
                        dev_name = config["name"]
                        dev_location = config["location"]
                        break

            try:
                success = await adapter.connect(config)
                results[device_id] = success
                logger.info(f"设备 {device_id} 连接{'成功' if success else '失败'}")

                # 注册设备
                if success and self._registry:
                    dev_info = {
                        "vendor": adapter.vendor,
                        "model": adapter.model,
                        "device_type": adapter.device_type,
                        "name": dev_name,
                        "location": dev_location,
                        "capabilities": await adapter.get_capabilities() if hasattr(adapter, 'get_capabilities') else [],
                    }
                    self._registry.register(device_id, dev_info)
            except Exception as e:
                logger.error(f"设备 {device_id} 启动异常: {e}")
                results[device_id] = False

        return results

    async def stop_all(self) -> None:
        """停止所有适配器（执行 disconnect）。"""
        for device_id, adapter_key in self._device_adapter_map.items():
            adapter = self._adapters.get(adapter_key)
            if adapter:
                try:
                    await adapter.disconnect()
                    logger.info(f"设备 {device_id} 已断开")
                except Exception as e:
                    logger.error(f"设备 {device_id} 断开异常: {e}")

    # ------------------------------------------------------------------
    # 适配器访问
    # ------------------------------------------------------------------
    def get_adapter(self, device_id: str) -> Optional[DeviceAdapter]:
        """根据设备 ID 获取适配器实例。"""
        adapter_key = self._device_adapter_map.get(device_id)
        if adapter_key:
            return self._adapters.get(adapter_key)
        return None

    def list_adapters(self) -> Dict[str, str]:
        """列出所有已加载的设备和适配器映射。"""
        return dict(self._device_adapter_map)
