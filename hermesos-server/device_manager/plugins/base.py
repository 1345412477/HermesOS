# -*- coding: utf-8 -*-
"""
HermesOS Gateway - 设备适配器插件基类
定义所有设备适配器必须实现的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DeviceAdapter(ABC):
    """设备适配器抽象基类。所有设备适配器插件必须继承此类。"""

    # 子类必须覆盖这些属性
    vendor: str = ""
    model: str = ""
    device_type: str = ""

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> bool:
        """连接到物理设备。

        Args:
            config: 设备配置字典，包含连接参数 (host, port, username, password 等)

        Returns:
            连接成功返回 True，失败返回 False
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开与设备的连接。"""
        ...

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """获取设备当前状态。

        Returns:
            状态字典，至少包含:
                - online: bool 是否在线
                - last_seen: str 最后一次通信时间
        """
        ...

    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行设备操作。

        Args:
            action: 操作名称 (如 capture_frame, detect_motion 等)
            params: 操作参数

        Returns:
            操作结果字典，至少包含:
                - success: bool
                - data: Any 返回数据
                - error: str 错误信息 (仅失败时)
        """
        ...

    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """获取设备支持的能力列表。

        Returns:
            能力名称列表，如 ['capture_frame', 'detect_motion']
        """
        ...
