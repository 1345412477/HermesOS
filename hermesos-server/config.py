"""HermesOS Server Configuration Management.

Loads configuration from a YAML file and provides a simple get() accessor.
"""

from pathlib import Path
from typing import Any, Optional

import yaml


class Config:
    """Application configuration loaded from YAML."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        self._config_path = Path(config_path)
        self._data: dict[str, Any] = {}
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-separated key.

        Example: config.get("voice_engine.tts.voice") -> "zh-CN-XiaoxiaoNeural"
        """
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def reload(self) -> None:
        """Reload configuration from the YAML file."""
        self.__init__(str(self._config_path))


# Global config singleton
config = Config()


def get_config() -> Config:
    return config
