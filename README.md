<div align="center">

# 🚀 AI Gateway

**A Personal, Lightweight LLM API Gateway with GUI**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[English](#) · [简体中文](README_CN.md)

</div>

---

## ✨ Why AI Gateway?

Managing multiple LLM providers can be frustrating:

- 🔴 Different API formats (OpenAI vs Anthropic vs Gemini)
- 🔴 Scattered API keys across projects
- 🔴 No fallback when a provider fails
- 🔴 Complex configuration files

**AI Gateway solves this with a simple GUI and unified API:**

- ✅ **One API endpoint** for all your LLM needs
- ✅ **Multi-format support** — OpenAI, Anthropic, and Gemini formats
- ✅ **Automatic conversion** between different provider formats
- ✅ **Channel fallback** when providers fail
- ✅ **Token management** with a visual interface
- ✅ **No Docker, no database** — just run and go

---

## 📸 Screenshots

|                Dashboard                |               Channels                |
| :-------------------------------------: | :-----------------------------------: |
| ![Dashboard](screenshots/dashboard.png) | ![Channels](screenshots/channels.png) |

|              Tokens               |               Settings                |
| :-------------------------------: | :-----------------------------------: |
| ![Tokens](screenshots/tokens.png) | ![Settings](screenshots/settings.png) |

---

## 🎯 Features

- **Multi-Format API Support** — OpenAI, Anthropic, and Gemini API formats natively
- **Bidirectional Format Conversion** — Automatic conversion between all supported formats
- **Multiple Providers** — OpenAI, Anthropic, Gemini, Ollama, and custom endpoints
- **Streaming Support** — Full SSE streaming with real-time format conversion
- **Channel Fallback** — Automatic failover to next available channel
- **High Availability Mode** — Route to any available channel regardless of model
- **Token Authentication** — Secure your gateway with access tokens
- **Proxy Support** — Configure HTTP/SOCKS5 proxy per channel
- **GUI Interface** — No config file editing required
- **Lightweight** — Single EXE on Windows, no dependencies

---

## 🚀 Quick Start

### Run from Source

```bash
# Clone the repository
git clone https://github.com/h0110wbit/ai-gateway.git
cd ai-gateway

# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py
```

### Build Windows EXE

```bash
build.bat
```

The executable will be at `dist/AIGateway.exe`.

---

## 📖 Usage

### 1. Add Channels

Navigate to **Channels** → **+ Add Channel**:

| Field    | Description                                   |
| -------- | --------------------------------------------- |
| Name     | Friendly name (e.g., "OpenAI GPT-4")          |
| Type     | openai / anthropic / gemini / ollama / custom |
| Base URL | Provider API endpoint                         |
| API Key  | Your provider API key                         |
| Models   | Comma-separated list (empty = all models)     |
| Priority | Lower number = higher priority                |

**Default Base URLs:**

| Provider  | Base URL                                    |
| --------- | ------------------------------------------- |
| OpenAI    | `https://api.openai.com/v1`                 |
| Anthropic | `https://api.anthropic.com`                 |
| Gemini    | `https://generativelanguage.googleapis.com` |
| Ollama    | `http://localhost:11434`                    |

### 2. Create Access Tokens

Navigate to **Tokens** → **+ Create Token**

Use this token in your client's `Authorization: Bearer <token>` header.

### 3. Start the Gateway

Navigate to **Dashboard** → Click **▶ Start Gateway**

Default endpoint: `http://localhost:3000`

### 4. Connect Your Client

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="your-gateway-token",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## 🔌 API Endpoints

### OpenAI-Compatible Endpoints

| Method | Path                   | Description                            |
| ------ | ---------------------- | -------------------------------------- |
| GET    | `/health`              | Health check                           |
| GET    | `/v1/models`           | List available models                  |
| POST   | `/v1/chat/completions` | Chat completions (streaming supported) |

### Anthropic-Compatible Endpoints

| Method | Path           | Description                                  |
| ------ | -------------- | -------------------------------------------- |
| POST   | `/v1/messages` | Anthropic Messages API (streaming supported) |

### Gemini-Compatible Endpoints

| Method | Path                                     | Description                                  |
| ------ | ---------------------------------------- | -------------------------------------------- |
| POST   | `/v1beta/models/{model}:generateContent` | Gemini generateContent (streaming supported) |

---

## 🔄 Format Conversion

AI Gateway supports bidirectional conversion between **OpenAI**, **Anthropic**, and **Gemini** formats:

| Client Format | Channel Type | Conversion                 |
| ------------- | ------------ | -------------------------- |
| OpenAI        | Anthropic    | Request/Response converted |
| OpenAI        | Gemini       | Request/Response converted |
| Anthropic     | OpenAI       | Request/Response converted |
| Anthropic     | Gemini       | Request/Response converted |
| Gemini        | OpenAI       | Request/Response converted |
| Gemini        | Anthropic    | Request/Response converted |

Streaming responses are converted in real-time via SSE.

---

## 🛠️ Integration Examples

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="your-gateway-token",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
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
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Google Gemini SDK

```python
import httpx

response = httpx.post(
    "http://localhost:3000/v1beta/models/gemini-pro:generateContent",
    headers={"x-goog-api-key": "your-gateway-token"},
    json={
        "contents": [{"parts": [{"text": "Hello!"}]}]
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

### cURL (OpenAI Format)

```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### cURL (Anthropic Format)

```bash
curl http://localhost:3000/v1/messages \
  -H "x-api-key: your-token" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### cURL (Gemini Format)

```bash
curl "http://localhost:3000/v1beta/models/gemini-pro:generateContent" \
  -H "x-goog-api-key: your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "Hello!"}]}]
  }'
```

---

## ⚡ High Availability Mode

Enable **High Availability Mode** from the Dashboard to route requests to any available channel, ignoring the model parameter. This is useful when you want maximum availability and don't care which specific model responds.

When enabled:

- The gateway ignores the `model` parameter in requests
- Routes to the first available channel based on priority
- Uses the first model configured in that channel

---

## ⚙️ Configuration

Configuration is stored in `config.json`:

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

## 🏗️ Architecture

```
ai-gateway/
├── main.py                    # Entry point
├── src/
│   ├── core/
│   │   ├── server.py          # FastAPI server + endpoints
│   │   ├── proxy.py           # Request routing + upstream proxy
│   │   └── converter.py       # Format conversion (OpenAI/Anthropic/Gemini)
│   ├── models/
│   │   └── config.py          # Pydantic config models
│   └── gui/
│       ├── app.py             # wxPython application
│       ├── main_frame.py      # Main window + sidebar
│       ├── controller.py      # Business logic controller
│       ├── theme.py           # Color scheme + styling
│       ├── widgets.py         # Reusable UI components
│       └── panels/
│           ├── dashboard.py
│           ├── channels.py
│           ├── tokens.py
│           └── settings.py
└── config.json                # Runtime configuration
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern async web framework
- [wxPython](https://www.wxpython.org/) - Cross-platform GUI toolkit
- [httpx](https://www.python-httpx.org/) - Modern async HTTP client

---

<div align="center">

**[⬆ Back to Top](#-ai-gateway)**

Made with ❤️ by [h0110wbit](https://github.com/h0110wbit)

</div>
