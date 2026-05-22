"""HermesOS 专属 Tools — device query and control via direct DeviceManager calls.

代替原 HTTP Gateway 客户端，直接在进程内调用 DeviceManager。
"""

import asyncio
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 位置名称映射：英文 → 中文 ──
LOCATION_MAP = {
    "living_room": "客厅",
    "bedroom": "卧室",
    "kitchen": "厨房",
    "bathroom": "浴室",
    "study": "书房",
    "corridor": "走廊",
    "balcony": "阳台",
    "dining_room": "餐厅",
    "lobby": "大堂",
    "hall": "大厅",
    "meeting_room": "会议室",
    "garage": "车库",
    "garden": "花园",
    "entrance": "门口",
    "staircase": "楼梯",
}

# ── 设备类型名称映射：英文简称 → Gateway 存储的完整类型名 ──
DEVICE_TYPE_MAP = {
    "light": "smart_light",
    "lamp": "smart_light",
    "sensor": "sensor",
    "motion_sensor": "ld2410_radar",
    "radar": "ld2410_radar",
    "presence": "ld2410_radar",
    "camera": "hikvision_camera",
    "ip_camera": "hikvision_camera",
    "switch": "switch",
    "curtain": "curtain",
    "thermostat": "thermostat",
    "lock": "lock",
    "door_lock": "lock",
    "screen": "screen",
    "display": "screen",
    "monitor": "screen",
}

# Reverse mapping for description display
_LOCATION_NAMES = ", ".join(f"{k}（{v}）" for k, v in LOCATION_MAP.items())
_DEVICE_NAMES = ", ".join(k for k in DEVICE_TYPE_MAP if k not in ("lamp", "motion_sensor", "ip_camera", "radar", "presence", "display", "monitor"))


def _map_location(english: str) -> str:
    """将英文位置名映射为中文。如果未找到映射则返回原值。"""
    return LOCATION_MAP.get(english, english)


def _map_device_type(english: str) -> str:
    """将英文设备类型简称映射为 Gateway 存储类型。如果未找到映射则返回原值。"""
    return DEVICE_TYPE_MAP.get(english, english)


# Lazy import to avoid circular dependencies at module load time
_device_manager = None


def _get_dm():
    """Lazy-load the DeviceManager singleton."""
    global _device_manager
    if _device_manager is None:
        from device_manager import get_device_manager
        _device_manager = get_device_manager()
    return _device_manager


# ═══════════════════════════════════════════════════════════════════
# Tool: QueryDeviceTool
# ═══════════════════════════════════════════════════════════════════

QUERY_DEVICE_SCHEMA = {
    "name": "query_device",
    "description": (
        "查询 HermesOS 智能家居设备状态。根据可选的 location（位置）和 device_type"
        "（设备类型）筛选设备。返回每个设备的基本信息、在线状态、最后活跃时间等。\n\n"
        "使用英文名传入参数，工具会自动翻译为系统内部名称。\n\n"
        "支持的 device_type: light, screen, sensor, camera, switch, curtain, thermostat, lock。\n"
        "支持的 location: living_room, bedroom, kitchen, bathroom, study, corridor, "
        "balcony, dining_room, lobby, meeting_room, garage, garden, entrance, staircase。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "按位置筛选设备（可选）。例如 'living_room', 'bedroom'。不填则返回所有位置。",
            },
            "device_type": {
                "type": "string",
                "description": "按设备类型筛选（可选）。例如 'light', 'sensor', 'switch'。不填则返回所有类型。",
            },
        },
        "required": [],
    },
}


def _query_device_handler(args: dict, **kwargs) -> str:
    """Handler for the query_device tool — calls Gateway API."""
    raw_location = args.get("location")
    raw_device_type = args.get("device_type")

    # Translate: English → Chinese / machine name
    location = _map_location(raw_location) if raw_location else None
    device_type = _map_device_type(raw_device_type) if raw_device_type else None

    dm = _get_dm()
    devices = dm.list_devices(device_type=device_type)

    # Filter by location (applied here since registry only filters by type)
    if location:
        devices = [d for d in devices if d.get("location", "").lower() == location.lower()]

    if not devices:
        filters = []
        if raw_location:
            filters.append(f"位置={location}")
        if device_type:
            filters.append(f"类型={device_type}")
        filter_text = "、".join(filters) if filters else "全部"
        return json.dumps(
            {"message": f"没有找到符合条件的设备（{filter_text}）", "devices": []},
            ensure_ascii=False,
        )

    # Build a human-readable summary
    device_list = []
    for d in devices:
        status_icon = "🟢" if d.get("online") else "🔴"
        device_list.append(
            f"{status_icon} {d.get('name', d.get('device_id', 'unknown'))}"
            f" [{d.get('device_type', '?')}] @ {d.get('location', '?')}"
            f" — {d.get('status', 'unknown')}"
        )

    result = {
        "message": f"找到 {len(devices)} 个设备",
        "count": len(devices),
        "devices": devices,
        "summary": device_list,
    }
    return json.dumps(result, ensure_ascii=False, default=str)


class QueryDeviceTool:
    """查询设备状态工具 — 调用 Gateway HTTP API 获取设备信息。"""

    name: str = "query_device"
    description: str = QUERY_DEVICE_SCHEMA["description"]
    parameters: dict = QUERY_DEVICE_SCHEMA["parameters"]

    def execute(self, location: Optional[str] = None, device_type: Optional[str] = None) -> str:
        """查询设备状态并返回描述性结果。

        Args:
            location: 按位置筛选（可选）。
            device_type: 按设备类型筛选（可选）。

        Returns:
            描述性 JSON 字符串，包含设备列表和状态摘要。
        """
        return _query_device_handler(
            {"location": location, "device_type": device_type}
        )


# ═══════════════════════════════════════════════════════════════════
# Tool: ControlDeviceTool
# ═══════════════════════════════════════════════════════════════════

CONTROL_DEVICE_SCHEMA = {
    "name": "control_device",
    "description": (
        "控制 HermesOS 智能家居设备。向指定设备发送操作指令。\n\n"
        "支持的 action 示例：\n"
        "- light: turn_on, turn_off, set_brightness, set_color\n"
        "- screen: set_brightness, get_brightness\n"
        "- switch: turn_on, turn_off, toggle\n"
        "- curtain: open, close, stop, set_position\n"
        "- thermostat: set_temperature, set_mode\n"
        "- lock: lock, unlock\n"
        "- camera: start_recording, stop_recording, take_snapshot\n\n"
        "params 根据 action 提供额外参数，例如 {\"brightness\": 80} 或 {\"level\": 80} 或 {\"temperature\": 26}。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "目标设备的唯一标识符。可通过 query_device 获取。",
            },
            "action": {
                "type": "string",
                "description": "要执行的操作。例如 'turn_on', 'turn_off', 'set_brightness' 等。",
            },
            "params": {
                "type": "object",
                "description": "操作的附加参数（可选）。例如 {\"brightness\": 80}。",
            },
        },
        "required": ["device_id", "action"],
    },
}


def _control_device_handler(args: dict, **kwargs) -> str:
    """Handler for the control_device tool — calls Gateway API."""
    device_id = args.get("device_id", "")
    action = args.get("action", "")
    params = args.get("params")

    if not device_id:
        return json.dumps({"error": "device_id 不能为空"}, ensure_ascii=False)
    if not action:
        return json.dumps({"error": "action 不能为空"}, ensure_ascii=False)

    dm = _get_dm()
    result = asyncio.run(dm.send_command(device_id, action, params))

    if "error" in result:
        return json.dumps(result, ensure_ascii=False)

    params_text = f"，参数: {json.dumps(params, ensure_ascii=False)}" if params else ""
    return json.dumps(
        {
            "message": f"已向设备 {device_id} 发送指令: {action}{params_text}",
            "device_id": device_id,
            "action": action,
            "result": result,
        },
        ensure_ascii=False,
        default=str,
    )


class ControlDeviceTool:
    """控制设备工具 — 通过 Gateway HTTP API 发送设备控制指令。"""

    name: str = "control_device"
    description: str = CONTROL_DEVICE_SCHEMA["description"]
    parameters: dict = CONTROL_DEVICE_SCHEMA["parameters"]

    def execute(self, device_id: str, action: str, params: Optional[dict] = None) -> str:
        """向设备发送控制指令并返回结果。

        Args:
            device_id: 目标设备 ID。
            action: 操作名称（如 'turn_on', 'turn_off'）。
            params: 操作参数（可选）。

        Returns:
            描述性 JSON 字符串，包含操作结果。
        """
        return _control_device_handler(
            {"device_id": device_id, "action": action, "params": params}
        )


# ═══════════════════════════════════════════════════════════════════
# Registry registration — makes tools discoverable by AIAgent
# ═══════════════════════════════════════════════════════════════════

def _check_hermesos_requirements() -> bool:
    """HermesOS tools are always available (no external API keys needed)."""
    return True


def _register_tools() -> None:
    """Register HermesOS tools with the Hermes Agent tool registry.

    Safe to call multiple times — duplicate registrations are harmless
    (registry.register with override=False skips on name collision).
    """
    try:
        from tools.registry import registry

        registry.register(
            name="query_device",
            toolset="hermesos",
            schema=QUERY_DEVICE_SCHEMA,
            handler=_query_device_handler,
            check_fn=_check_hermesos_requirements,
            emoji="🔍",
            override=True,
        )

        registry.register(
            name="control_device",
            toolset="hermesos",
            schema=CONTROL_DEVICE_SCHEMA,
            handler=_control_device_handler,
            check_fn=_check_hermesos_requirements,
            emoji="🎮",
            override=True,
        )

        logger.info("HermesOS tools registered: query_device, control_device")
    except Exception:
        logger.exception("Failed to register HermesOS tools in registry")


# Auto-register on import if we're in a Hermes Agent environment
try:
    _register_tools()
except Exception:
    # Not running inside the Hermes Agent venv — tools will be injected
    # directly by agent_adapter.py instead
    logger.debug("Skipping registry registration (not in Hermes Agent environment)")


# ═══════════════════════════════════════════════════════════════════
# Convenience: list of available HermesOS tool instances
# ═══════════════════════════════════════════════════════════════════

HERMESOS_TOOLS = [
    QueryDeviceTool(),
    ControlDeviceTool(),
]


def get_hermesos_tool_schemas() -> list[dict]:
    """Return OpenAI-format tool schemas for HermesOS tools.

    These can be appended to ``agent.tools`` after AIAgent initialization.
    """
    return [
        {"type": "function", "function": QUERY_DEVICE_SCHEMA},
        {"type": "function", "function": CONTROL_DEVICE_SCHEMA},
    ]
