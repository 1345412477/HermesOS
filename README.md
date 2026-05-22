# HermesOS — 基于 Hermes Agent 的智能中控系统

> 一句话控制万物：用户只说要什么，不说怎么做。

## 架构

```
用户 → QQ/微信/语音（统一端口 8765）
        │
HermesOS Server
  ├── FastAPI（REST API）
  ├── DeviceManager（设备注册 + 适配器引擎）
  │   └── plugins/（PC屏幕、Mock设备等）
  ├── Agent Bridge（Hermes Agent 桥接层）
  └── 语音引擎（ASR + TTS）
```

## 核心特性

- **Agent Client 范式**：设备只声明能力，不自带业务逻辑
- **统一端口 8765**：设备管理 + Agent + 语音全在一个进程
- **远程设备轮询**：手机等远端设备通过 HTTP 轮询取指令
- **插件式适配器**：新设备写一个类接入，零改现有代码
- **语音控制**：浏览器麦克风 → 离线 ASR → Agent → TTS 播报
- **对话记忆**：Agent 记忆上下文，多轮对话自然

## 快速开始

```bash
cd hermesos-server
pip install -r requirements.txt
python main.py
```

打开 `http://localhost:8765/console/` 使用控制台。

## 支持的设备

| 设备 | 适配器 | 状态 |
|------|--------|------|
| PC 屏幕亮度 | `pc_screen.py` | ✅ |
| Mock 设备（测试用） | `mock.py` | ✅ |

新设备：在 `device_manager/plugins/` 下写适配器，在 `config.yaml` 添加配置即可。

## 技术栈

- **后端**：Python FastAPI + aiohttp
- **AI 引擎**：Hermes Agent (DeepSeek v4)
- **语音**：browser SpeechRecognition + pocketsphinx (ASR) / SpeechSynthesis (TTS)
- **设备控制**：screen_brightness_control, python-miio 等
