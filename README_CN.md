<div align="center">

# 🚀 AI Gateway

**个人轻量级 LLM API 网关，带图形界面**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[English](README.md) · [简体中文](#)

</div>

---

## ✨ 为什么选择 AI Gateway？

管理多个 LLM 提供商可能让人头疼：

- 🔴 不同的 API 格式（OpenAI vs Anthropic vs Gemini）
- 🔴 API 密钥分散在各个项目中
- 🔴 提供商故障时没有备用方案
- 🔴 配置文件复杂难懂

**AI Gateway 用简洁的图形界面和统一的 API 解决这些问题：**

- ✅ **一个 API 端点** 满足所有 LLM 需求
- ✅ **多格式支持** — OpenAI、Anthropic、Gemini 三种格式
- ✅ **自动格式转换** — 不同提供商格式之间无缝切换
- ✅ **通道故障转移** — 提供商失败时自动切换
- ✅ **令牌管理** — 可视化界面管理访问令牌
- ✅ **无需 Docker、无需数据库** — 开箱即用

---

## 📸 截图预览

|                仪表盘                |               通道管理                |
| :----------------------------------: | :-----------------------------------: |
| ![仪表盘](screenshots/dashboard.png) | ![通道管理](screenshots/channels.png) |

|              令牌管理               |               设置                |
| :---------------------------------: | :-------------------------------: |
| ![令牌管理](screenshots/tokens.png) | ![设置](screenshots/settings.png) |

---

## 🎯 功能特性

- **多格式 API 支持** — 原生支持 OpenAI、Anthropic、Gemini API 格式
- **双向格式转换** — 所有支持格式之间自动转换
- **多提供商支持** — OpenAI、Anthropic、Gemini 三种格式
- **流式响应支持** — 完整 SSE 流式传输，支持实时格式转换
- **通道故障转移** — 自动切换到下一个可用通道
- **高可用模式** — 忽略模型参数，路由到任意可用通道
- **令牌认证** — 保护你的网关安全
- **代理支持** — 每个通道可配置 HTTP/SOCKS5 代理
- **图形界面** — 无需编辑配置文件
- **轻量级** — Windows 单文件 EXE，无依赖

---

## 🚀 快速开始

### 从源码运行

```bash
# 克隆仓库
git clone https://github.com/h0110wbit/ai-gateway.git
cd ai-gateway

# 安装依赖
pip install -r requirements.txt

# 启动图形界面
python main.py
```

### 构建 Windows EXE

```bash
build.bat
```

可执行文件将生成在 `dist/AIGateway.exe`。

---

## 📖 使用指南

### 1. 添加通道

导航至 **通道** → **+ 添加通道**：

| 字段     | 说明                                          |
| -------- | --------------------------------------------- |
| 名称     | 友好名称（如 "OpenAI GPT-4"）                 |
| 类型     | openai / anthropic / gemini / ollama / custom |
| 基础 URL | 提供商 API 端点                               |
| API 密钥 | 你的提供商 API 密钥                           |
| 模型     | 逗号分隔列表（留空 = 所有模型）               |
| 优先级   | 数字越小优先级越高                            |

**默认基础 URL：**

| 提供商    | 基础 URL                                    |
| --------- | ------------------------------------------- |
| OpenAI    | `https://api.openai.com/v1`                 |
| Anthropic | `https://api.anthropic.com`                 |
| Gemini    | `https://generativelanguage.googleapis.com` |
| Ollama    | `http://localhost:11434`                    |

### 2. 创建访问令牌

导航至 **令牌** → **+ 创建令牌**

在客户端的 `Authorization: Bearer <token>` 请求头中使用此令牌。

### 3. 启动网关

导航至 **仪表盘** → 点击 **▶ 启动网关**

默认端点：`http://localhost:3000`

### 4. 连接你的客户端

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="your-gateway-token",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "你好！"}]
)
```

---

## 🔌 API 端点

### OpenAI 兼容端点

| 方法 | 路径                   | 说明                 |
| ---- | ---------------------- | -------------------- |
| GET  | `/health`              | 健康检查             |
| GET  | `/v1/models`           | 列出可用模型         |
| POST | `/v1/chat/completions` | 聊天补全（支持流式） |

### Anthropic 兼容端点

| 方法 | 路径           | 说明                               |
| ---- | -------------- | ---------------------------------- |
| POST | `/v1/messages` | Anthropic Messages API（支持流式） |

### Gemini 兼容端点

| 方法 | 路径                                     | 说明                               |
| ---- | ---------------------------------------- | ---------------------------------- |
| POST | `/v1beta/models/{model}:generateContent` | Gemini generateContent（支持流式） |

---

## 🔄 格式转换

AI Gateway 支持 **OpenAI**、**Anthropic** 和 **Gemini** 格式之间的双向转换：

| 客户端格式 | 通道类型  | 转换方式      |
| ---------- | --------- | ------------- |
| OpenAI     | Anthropic | 请求/响应转换 |
| OpenAI     | Gemini    | 请求/响应转换 |
| Anthropic  | OpenAI    | 请求/响应转换 |
| Anthropic  | Gemini    | 请求/响应转换 |
| Gemini     | OpenAI    | 请求/响应转换 |
| Gemini     | Anthropic | 请求/响应转换 |

流式响应通过 SSE 实时转换。

---

## 🛠️ 集成示例

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="your-gateway-token",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "你好！"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")
```

### Anthropic SDK

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:3000",
    api_key="your-gateway-token",
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "你好！"}]
)
```

### Google Gemini SDK

```python
import httpx

response = httpx.post(
    "http://localhost:3000/v1beta/models/gemini-pro:generateContent",
    headers={"x-goog-api-key": "your-gateway-token"},
    json={
        "contents": [{"parts": [{"text": "你好！"}]}]
    }
)
print(response.json())
```

### Claude Code CLI

```bash
export ANTHROPIC_BASE_URL=http://localhost:3000
export ANTHROPIC_API_KEY=your-gateway-token

claude
```

### cURL（OpenAI 格式）

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": true
  }'
```

### cURL（Anthropic 格式）

```bash
curl http://localhost:3000/v1/messages \
  -H "x-api-key: your-token" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": true
  }'
```

### cURL（Gemini 格式）

```bash
curl "http://localhost:3000/v1beta/models/gemini-pro:generateContent" \
  -H "x-goog-api-key: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "你好！"}]}]
  }'
```

---

## ⚡ 高可用模式

在仪表盘启用 **高可用模式**，可将请求路由到任意可用通道，忽略模型参数。当你需要最大可用性且不关心具体哪个模型响应时非常有用。

启用后：

- 网关忽略请求中的 `model` 参数
- 根据优先级路由到第一个可用通道
- 使用该通道配置的第一个模型

---

## ⚙️ 配置说明

配置存储在 `config.json` 中：

```json
{
  "settings": {
    "host": "0.0.0.0",
    "port": 3000,
    "require_auth": true,
    "enable_fallback": true,
    "enable_cors": true,
    "high_availability_mode": false
  },
  "channels": [
    {
      "id": 1,
      "name": "OpenAI",
      "type": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-...",
      "models": ["gpt-4o", "gpt-4o-mini"],
      "enabled": true,
      "priority": 1,
      "timeout": 60,
      "proxy_enabled": false,
      "proxy_url": ""
    }
  ],
  "tokens": [
    {
      "id": 1,
      "name": "My Token",
      "key": "sk-gw-...",
      "enabled": true,
      "allowed_channels": [],
      "allowed_models": []
    }
  ]
}
```

---

## 🏗️ 项目结构

```
ai-gateway/
├── main.py                    # 入口文件
├── src/
│   ├── core/
│   │   ├── server.py          # FastAPI 服务器 + 端点定义
│   │   ├── proxy.py           # 请求路由 + 上游代理
│   │   └── converter.py       # 格式转换（OpenAI/Anthropic/Gemini）
│   ├── models/
│   │   └── config.py          # Pydantic 配置模型
│   └── gui/
│       ├── app.py             # wxPython 应用
│       ├── main_frame.py      # 主窗口 + 侧边栏
│       ├── controller.py      # 业务逻辑控制器
│       ├── theme.py           # 配色方案 + 样式
│       ├── widgets.py         # 可复用 UI 组件
│       └── panels/
│           ├── dashboard.py
│           ├── channels.py
│           ├── tokens.py
│           └── settings.py
└── config.json                # 运行时配置
```

---

## 🤝 参与贡献

欢迎贡献代码！请随时提交 Pull Request。

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代异步 Web 框架
- [wxPython](https://www.wxpython.org/) - 跨平台 GUI 工具包
- [httpx](https://www.python-httpx.org/) - 现代异步 HTTP 客户端

---

<div align="center">

**[⬆ 返回顶部](#-ai-gateway)**

Made with ❤️ by [h0110wbit](https://github.com/h0110wbit)

</div>
