# -*- coding: utf-8 -*-
"""
HermesOS Gateway - 配置管理模块
从 YAML 文件加载配置，提供 get() 方法访问。
"""

import os
import yaml


class Config:
    """配置管理器，从 YAML 文件加载配置并提供 get() 访问方法。"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.environ.get(
                "HERMES_GATEWAY_CONFIG",
                os.path.join(os.path.dirname(__file__), "config.yaml")
            )
        self._config_path = os.path.abspath(config_path)
        self._data = {}
        if os.path.isfile(self._config_path):
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的嵌套 key (如 'mqtt.host')。"""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def reload(self):
        """重新加载配置文件。"""
        self.__init__(self._config_path)
