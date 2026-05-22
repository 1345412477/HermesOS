# HermesOS — 基于 Hermes Agent 的智能中控系统

> ⚠️ **开发阶段** — 核心链路已验证，功能持续迭代中。

**一句话控制万物：用户只说要什么，不说怎么做。**

HermesOS 是一个基于 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的语音控制 IoT 平台。它把自然语言理解、设备管理、语音交互整合到一个统一的进程中，让用户通过自然语言即可控制各种智能设备。

---

## 目录

- [架构](#架构)
- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [配置](#配置)
- [API 文档](#api-文档)
- [开发设备适配器](#开发设备适配器)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [许可证](#许可证)

---

## 架构

```
用户输入（文本/语音）
       │
       ▼
┌──────────────────────────────────────────┐
│            HermesOS Server               │
│          （单进程，端口 8765）              │
│                                          │
│  ┌─────────┐  ┌─────────────────────┐    │
│  │ FastAPI  │  │   Agent Bridge      │    │
│  │ REST API │◄─┤  (Hermes Agent 封装) │    │
│  └────┬────┘  └─────────┬───────────┘    │
│       │                 │                │
│  ┌────▼─────────────────▼───────────┐    │
│  │        DeviceManager             │    │
│  │  ┌────────────────────────────┐  │    │
│  │  │      Plugin Engine         │  │    │
│  │  │  ┌──────┐ ┌──────┐ ┌────┐ │  │    │
│  │  │  │ Mock  │ │Screen│ │... │ │  │    │
│  │  │  │Adapter│ │Adapt.│ │    │ │  │    │
│  │  │  └──────┘ └──────┘ └────┘ │  │    │
│  │  └────────────────────────────┘  │    │
│  │  ┌────────────────────────────┐  │    │
│  │  │      Device Registry       │  │    │
│  │  │   (内存 + JSON 持久化)      │  │    │
│  │  └────────────────────────────┘  │    │
│  └──────────────────────────────────┘    │
│                                          │
│  ┌──────────┐  ┌──────────────────┐      │
│  │ ASR      │  │ TTS              │      │
│  │(pocketsph)│  │ (Edge-TTS)       │      │
│  └──────────┘  └──────────────────┘      │
│                                          │
│  ┌──────────────────────────────────┐    │
│  │        Event Store (SQLite)      │    │
│  └──────────────────────────────────┘    │
└──────────────────────────────────────────┘
       │
       ▼
  Web 控制台（localhost:8765/console/）
```

### 流程示例

```
用户说："屏幕亮度调到 60"

1. ASR 识别文本 → "屏幕亮度调到 60"
2. Agent Bridge 接收文本
3. Hermes Agent 调用 query_device 查询可用设备
4. Agent 调用 control_device(screen_main, set_brightness, {level: 60})
5. DeviceManager 路由到 PCScreenAdapter 执行
6. Agent 返回响应 → TTS 播报 → 用户收到回复
```

---

## 核心特性

### 🎯 Agent Client 范式
设备只声明能力（Capabilities），不自带业务逻辑。所有策略决策由 Hermes Agent 的 LLM 大脑动态推理。**新设备插电 = 自动注册，零配置。**

### 🔌 统一端口 8765
设备管理、Agent 推理、语音引擎全在一个进程中，消除双端口混乱，降低延迟。

### 📡 插件式设备适配器
新设备只需写一个 Python 类继承 `DeviceAdapter`，放在 `plugins/` 目录下即可接入，零改动现有代码。

### 🎤 离线语音控制
- **ASR**：pocketsphinx（离线语音识别，无需网络）
- **TTS**：Edge-TTS（微软语音合成）
- 浏览器麦克风录音 → 服务端识别 → Agent 处理 → TTS 播报

### 📋 事件存储
所有设备操作和对话记录持久化到 SQLite，支持历史查询和统计分析。

### 💬 对话记忆
Agent 保持最近 10 轮对话历史，多轮交互自然流畅。

### 🌐 远程设备轮询
为手机等无法长连接的设备预留 HTTP 轮询接口（`pending` / `result`）。

---

## 快速开始

### 环境要求

- Python 3.11+
- Windows 10+（屏幕亮度控制需要 Windows）

### 安装

```bash
# 克隆项目
git clone https://github.com/1345412477/HermesOS.git
cd HermesOS/hermesos-server

# 安装依赖
pip install -r requirements.txt

# 额外依赖（语音识别）
pip install pocketsphinx SpeechRecognition

# 额外依赖（屏幕亮度控制，仅 Windows）
pip install screen-brightness-control
```

### 运行

```bash
python main.py
```

启动后访问控制台：
- **Web 控制台**：http://localhost:8765/console/
- **健康检查**：http://localhost:8765/api/health

### 快速测试

```bash
# 文本指令
curl -X POST http://localhost:8765/api/voice/text \
  -H "Content-Type: application/json" \
  -d '{"text":"有哪些设备在线？"}'

# 设备列表
curl http://localhost:8765/api/devices

# 发送设备指令
curl -X POST http://localhost:8765/api/devices/screen_main/command \
  -H "Content-Type: application/json" \
  -d '{"command":"set_brightness","params":{"level":80}}'
```

---

## 配置

配置文件：`hermesos-server/config.yaml`

```yaml
server:
  host: "0.0.0.0"       # 监听地址
  port: 8765             # 服务端口

voice_engine:
  asr:
    model: "base"        # ASR 模型
    mock: false          # 是否使用 mock 模式（开发用）
  tts:
    voice: "zh-CN-XiaoxiaoNeural"  # TTS 音色
    rate: "+0%"
    pitch: "+0Hz"

event_store:
  db_path: null          # 事件数据库路径（null = data/events.db）

agent_bridge:
  mock: true             # Agent mock 模式（无 API Key 时使用）

device_manager:
  log_level: "INFO"
  data_dir: "data"       # 设备数据持久化目录
  heartbeat_timeout: 86400
```

### 设备注册

在 `config.yaml` 的 `devices` 列表中添加设备：

```yaml
devices:
  - vendor: "mock"
    model: "mock-device"
    device_type: "mock_adapter"
    device_id: "light_living"
    name: "客厅灯"
    location: "客厅"
    config: {}
```

---

## API 文档

### 健康检查

```
GET /api/health
```

返回服务状态、设备在线数、引擎信息。

### 设备管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/devices` | 获取所有设备列表 |
| GET | `/api/devices/{id}` | 获取指定设备详情 |
| POST | `/api/devices/register` | 注册新设备 |
| POST | `/api/devices/{id}/command` | 发送设备指令 |
| GET | `/api/devices/{id}/status` | 获取设备实时状态 |
| GET | `/api/devices/{id}/capabilities` | 获取设备能力列表 |

### 语音/文本

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/voice` | 语音输入（base64 音频）→ 文本回复 + 音频 |
| POST | `/api/voice/text` | 文本输入 → 文本回复 |

### 事件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/events` | 查询事件历史（支持筛选） |
| GET | `/api/events/recent` | 获取最近事件 |
| GET | `/api/events/stats` | 事件统计（今日/总计） |

### 远程设备轮询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/devices/{id}/pending` | 远程设备拉取待执行任务 |
| POST | `/api/devices/{id}/result` | 远程设备上报执行结果 |

---

## 开发设备适配器

### 适配器基类

所有设备适配器必须继承 `DeviceAdapter`（位于 `device_manager/plugins/base.py`）：

```python
from device_manager.plugins.base import DeviceAdapter

class MyDeviceAdapter(DeviceAdapter):
    vendor = "my_brand"        # 厂商
    model = "my_model"         # 型号
    device_type = "my_type"    # 设备类型

    async def connect(self, config: dict) -> bool:
        # 连接到物理设备
        return True

    async def disconnect(self) -> None:
        # 断开连接
        pass

    async def get_status(self) -> dict:
        # 返回设备状态
        return {"online": True}

    async def execute(self, action: str, params: dict = None) -> dict:
        # 执行操作
        return {"success": True, "data": {}}

    async def get_capabilities(self) -> list:
        # 返回支持的操作列表
        return ["turn_on", "turn_off", "get_status"]
```

### 适配器注册

1. 在 `device_manager/plugins/` 下创建 Python 文件
2. 实现 `DeviceAdapter` 子类（设置 `vendor`、`model`、`device_type`）
3. 在 `config.yaml` 的 `devices` 列表中添加配置
4. **无需修改其他代码**，插件引擎会自动扫描加载

### 现有适配器

| 适配器 | 文件 | 说明 |
|--------|------|------|
| MockAdapter | `plugins/mock.py` | 模拟设备，支持 6 种设备类型 |
| PCScreenAdapter | `plugins/pc_screen.py` | Windows 屏幕亮度控制 |

---

## 项目结构

```
HermesOS/
├── README.md                          # 本说明文档
├── .gitignore
└── hermesos-server/                   # 主服务目录
    ├── main.py                        # FastAPI 入口
    ├── config.py                      # 配置加载
    ├── config.yaml                    # 配置文件
    ├── requirements.txt               # Python 依赖
    │
    ├── router/
    │   ├── device.py                  # 设备管理 + 事件 API
    │   └── voice.py                   # 语音/文本 API
    │
    ├── agent_bridge/
    │   ├── agent_adapter.py           # Hermes Agent 封装
    │   └── hermesos_tools.py          # query/control 工具注册
    │
    ├── device_manager/
    │   ├── plugin_engine.py           # 插件引擎（扫描+加载+生命周期）
    │   ├── registry.py                # 设备注册表（内存+JSON持久化）
    │   ├── config.py                  # 设备配置管理
    │   ├── config.yaml                # 设备默认配置
    │   ├── data/
    │   │   └── devices.json           # 设备数据持久化文件
    │   └── plugins/
    │       ├── base.py                # DeviceAdapter 抽象基类
    │       ├── mock.py                # 模拟设备适配器
    │       ├── pc_screen.py           # PC 屏幕亮度适配器
    │       ├── hikvision.py           # 海康摄像头适配器（预留）
    │       └── ld2410.py              # LD2410 雷达适配器（预留）
    │
    ├── voice_engine/
    │   ├── asr.py                     # 语音识别（pocketsphinx）
    │   └── tts.py                     # 语音合成（Edge-TTS）
    │
    ├── event_store/
    │   └── storage.py                 # SQLite 事件存储
    │
    ├── models/
    │   └── schemas.py                 # Pydantic 数据模型
    │
    ├── static/
    │   └── index.html                 # Web 控制台页面
    │
    └── data/
        └── events.db                  # 事件数据库（自动创建）
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | Python FastAPI + uvicorn |
| **AI 引擎** | Hermes Agent（DeepSeek v4） |
| **语音识别** | pocketsphinx（离线） |
| **语音合成** | Edge-TTS（微软） |
| **设备控制** | screen-brightness-control（屏幕）、python-miio（小米） |
| **数据存储** | SQLite（事件）、JSON（设备注册） |
| **序列化** | Pydantic v2 |
| **配置管理** | PyYAML |

---

## 开发计划

- [x] 核心链路：文本 → Agent → 设备 → 回复
- [x] 语音：浏览器录音 → 服务端 ASR → TTS 播报
- [x] Web 控制台
- [x] 事件存储与查询
- [x] 插件式设备适配器
- [x] Agent 对话记忆
- [ ] 手机端 Termux 客户端
- [ ] 更多真实设备适配器（小米灯、智能锁等）
- [ ] Docker 一键部署
- [ ] 自定义场景/自动化规则

---

## 许可证

MIT License

---

*HermesOS — 让智能家居真正「智能」起来。*
