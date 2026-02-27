<div align="center">

# 🚀 AI Gateway

**个人轻量级 LLM API 网关，带图形界面**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[简体中文](README.md) · [English](README_EN.md)

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
- ✅ **内置客户端** — 提供 GLM、Kimi、DeepSeek、Qwen、MiniMax 的接口逆向
- ✅ **自适应限流** — 根据响应时间动态调整并发
- ✅ **令牌管理** — 可视化界面管理访问令牌
- ✅ **系统托盘** — 最小化到托盘，静默运行
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

### API 与协议支持

- **多格式 API 支持** — 原生支持 OpenAI、Anthropic、Gemini API 格式
- **双向格式转换** — 所有支持格式之间自动转换
- **流式响应支持** — 完整 SSE 流式传输，支持实时格式转换

### 提供商支持

- **HTTP 通道** — OpenAI、Anthropic、Gemini、Ollama、内置通道
- **内置客户端** — 支持以下国内大模型的接口逆向 Python 客户端，token 获取方式可以参考致谢部分列出的原项目：
  - 🟢 **GLM** (智谱清言)
  - 🔵 **Kimi** (Moonshot)
  - 🟣 **DeepSeek**
  - 🟠 **Qwen** (通义千问)
  - 🟡 **MiniMax**

### 高级功能

- **通道故障转移** — 自动切换到下一个可用通道
- **高可用模式** — 忽略模型参数，路由到任意可用通道
- **自适应限流** — 根据响应时间和错误率动态调整并发
- **负载均衡** — 轮询算法分配请求到多个通道
- **代理支持** — 每个通道可配置 HTTP/SOCKS5 代理，内置通道除外
- **令牌认证** — 细粒度的访问控制，支持通道和模型限制

### 用户体验

- **图形界面** — 无需编辑配置文件
- **系统托盘** — 最小化到系统托盘，支持静默启动
- **开机自启** — 可配置 Windows 开机自动启动
- **单实例运行** — 防止重复启动多个实例
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

### 命令行参数

```bash
# 静默启动（最小化到系统托盘）
python main.py --silent

# 启动时自动启动网关服务
python main.py --start

# 组合使用
python main.py --silent --start
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

#### HTTP 通道类型

| 字段     | 说明                                           |
| -------- | ---------------------------------------------- |
| 名称     | 友好名称（如 "OpenAI GPT-4"）                  |
| 类型     | openai / anthropic / gemini / ollama / builtin |
| 基础 URL | 提供商 API 端点                                |
| API 密钥 | 你的提供商 API 密钥                            |
| 模型     | 逗号分隔列表（留空 = 所有模型）                |
| 优先级   | 数字越小优先级越高                             |
| 代理     | 可选的 HTTP/SOCKS5 代理配置                    |

**默认基础 URL：**

| 提供商    | 基础 URL                                    |
| --------- | ------------------------------------------- |
| OpenAI    | `https://api.openai.com/v1`                 |
| Anthropic | `https://api.anthropic.com`                 |
| Gemini    | `https://generativelanguage.googleapis.com` |

#### 内置客户端类型

| 字段     | 说明                          |
| -------- | ----------------------------- |
| 名称     | 友好名称（如 "智谱 GLM-4"）   |
| 类型     | builtin:glm / builtin:kimi 等 |
| API 密钥 | 对应平台的刷新令牌或 API 密钥 |
| 模型     | 自动填充，无需手动配置        |

### 2. 创建访问令牌

导航至 **令牌** → **+ 创建令牌**

- 设置令牌名称和密钥
- 可选：限制可访问的通道
- 可选：限制可访问的模型

在客户端的 `Authorization: Bearer <token>` 请求头中使用此令牌。

### 3. 启动网关

导航至 **仪表盘** → 点击 **▶ 启动网关**

默认端点：`http://localhost:3000`

**仪表盘功能：**

- 查看网关运行状态
- 实时请求统计
- 启用/禁用高可用模式
- 快速启动/停止服务

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

## 🎛️ 自适应限流

每个通道支持自适应限流，根据实时性能动态调整并发数：

### 限流模式

- **固定模式** — 设置固定的最大并发数
- **自适应模式** — 根据响应时间和错误率自动调整

### 自适应算法

- 响应时间短且错误率低 → 增加并发
- 响应时间长 → 逐步降低并发
- 错误率高 → 快速降低并发

### 配置参数

| 参数                  | 说明                          | 默认值 |
| --------------------- | ----------------------------- | ------ |
| 最大并发数            | 固定模式上限 / 自适应模式禁用 | 自适应 |
| 最小并发数            | 自适应模式起始值              | 1      |
| 最大自适应并发        | 自适应模式上限                | 10     |
| 响应时间阈值（低/高） | 判断性能好坏的阈值            | 1s/5s  |
| 错误率阈值            | 触发降速的错误率              | 10%    |

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
    "high_availability_mode": false,
    "auto_start": false
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
      "max_retries": 3,
      "proxy_enabled": false,
      "proxy_url": "",
      "max_concurrency": null,
      "min_concurrency": 1,
      "max_adaptive_concurrency": 100,
      "response_time_low": 1.0,
      "response_time_high": 5.0,
      "error_rate_threshold": 0.1,
      "increase_step": 2,
      "decrease_factor": 0.8,
      "stats_window_size": 100,
      "cooldown_seconds": 5.0
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

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

本项目接口逆向 Python 客户端基于 [xiaoY233](https://github.com/xiaoY233) 的以下项目：

- [GLM-Free-API](https://github.com/xiaoY233/GLM-Free-API.git) - 智谱清言接口逆向
- [DeepSeek-Free-API](https://github.com/xiaoY233/DeepSeek-Free-API.git) - DeepSeek 接口逆向
- [MiniMax-Free-API](https://github.com/xiaoY233/MiniMax-Free-API.git) - MiniMax 接口逆向
- [Qwen-Free-API](https://github.com/xiaoY233/Qwen-Free-API.git) - Qwen 接口逆向
- [Kimi-Free-API](https://github.com/xiaoY233/Kimi-Free-API.git) - Kimi 接口逆向

---

<div align="center">

**用 ❤️ 和 Python 构建**

</div>
