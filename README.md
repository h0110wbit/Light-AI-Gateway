# Light AI Gateway

A personal, lightweight AI API Gateway for proxying requests to multiple LLM providers with an easy-to-use graphical interface.

## Features

- **Multi-Format API Support** — Supports both OpenAI and Anthropic API formats natively
- **OpenAI-Compatible API** — All clients that work with OpenAI's API work with AI Gateway
- **Claude Code Support** — Works with Claude Code CLI and other Anthropic-native clients
- **Multiple Providers** — OpenAI, Anthropic, Gemini, Ollama, and any custom OpenAI-compatible endpoint
- **Streaming Support** — Full SSE streaming proxy, including Anthropic ↔ OpenAI format conversion
- **Channel Fallback** — Automatically tries the next channel if one fails
- **Token Authentication** — Protect your gateway with API tokens
- **GUI Interface** — No config file editing needed; manage everything from the UI
- **Lightweight** — Single EXE on Windows, no Docker, no database

## Quick Start

### Run from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py
```

### Build Windows EXE

On Windows:

```
build.bat
```

The EXE will be at `dist/AIGateway.exe`.

## Usage

### 1. Add Channels

Go to **Channels** tab → **+ Add Channel**:

| Field    | Description                                   |
| -------- | --------------------------------------------- |
| Name     | Friendly name (e.g. "OpenAI GPT-4")           |
| Type     | openai / anthropic / gemini / ollama / custom |
| Base URL | Provider API base URL                         |
| API Key  | Your provider API key                         |
| Models   | Comma-separated list (leave empty = all)      |
| Priority | Lower number = higher priority for routing    |

**Default URLs:**

- OpenAI: `https://api.openai.com`
- Anthropic: `https://api.anthropic.com`
- Gemini: `https://generativelanguage.googleapis.com`
- Ollama (local): `http://localhost:11434`

### 2. Create Access Tokens

Go to **Tokens** tab → **+ Create Token**

Your gateway token is what clients use in the `Authorization: Bearer <token>` header.

### 3. Start the Gateway

Go to **Dashboard** → click **▶ Start Gateway**

The gateway runs on `http://localhost:3000` by default.

### 4. Connect Your Client

Set your OpenAI client's base URL to point to the gateway:

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

### cURL Example

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

## API Endpoints

### OpenAI-Compatible Endpoints

These endpoints accept OpenAI-format requests and work with any OpenAI-compatible client:

| Method | Path                       | Description                            |
| ------ | -------------------------- | -------------------------------------- |
| GET    | `/health`                  | Health check                           |
| GET    | `/v1/models`               | List available models                  |
| POST   | `/v1/chat/completions`     | Chat completions (streaming supported) |
| POST   | `/v1/completions`          | Text completions                       |
| POST   | `/v1/embeddings`           | Embeddings                             |
| POST   | `/v1/images/generations`   | Image generation                       |
| POST   | `/v1/audio/speech`         | Text-to-speech                         |
| POST   | `/v1/audio/transcriptions` | Speech-to-text                         |

### Anthropic-Compatible Endpoints

These endpoints accept Anthropic-format requests and work with Claude Code, Cursor, and other Anthropic-native clients:

| Method | Path           | Description                                  |
| ------ | -------------- | -------------------------------------------- |
| POST   | `/v1/messages` | Anthropic Messages API (streaming supported) |

## Multi-Format Support

AI Gateway supports both **OpenAI** and **Anthropic** API formats, allowing you to use various clients with any upstream provider.

### Using with OpenAI Clients

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

### Using with Claude Code

```bash
export ANTHROPIC_BASE_URL=http://localhost:3000
export ANTHROPIC_API_KEY=your-gateway-token

claude
```

### Using with Anthropic SDK

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

### Format Conversion

When using OpenAI-format endpoints with Anthropic channels (or vice versa), the gateway automatically converts:

| Direction                          | Conversion                                   |
| ---------------------------------- | -------------------------------------------- |
| OpenAI → Anthropic Channel         | Request body transformed to Anthropic format |
| Anthropic → OpenAI Channel         | Request body transformed to OpenAI format    |
| Anthropic Response → OpenAI Client | Response converted to OpenAI format          |
| OpenAI Response → Anthropic Client | Response converted to Anthropic format       |

Streaming responses are also converted in real-time (SSE format transformation).

## Provider Notes

### Anthropic

- Requests to `/v1/chat/completions` are automatically translated from OpenAI format to Anthropic's Messages API format
- Requests to `/v1/messages` are passed through directly to Anthropic channels
- Responses are translated back to match the client's expected format
- Streaming is fully supported with real-time SSE conversion

### OpenAI

- All endpoints work natively with OpenAI-format requests
- When accessed via `/v1/messages` (Anthropic format), requests are converted to OpenAI format

### Gemini

- API key is passed as query parameter (`?key=...`)
- Works with OpenAI-format endpoints

### Ollama

Set base URL to `http://localhost:11434` (or your Ollama host). No API key needed.

### Custom/OpenAI-Compatible

Any provider with an OpenAI-compatible API (e.g., LM Studio, vLLM, Groq, Together AI) can be added as a `custom` type channel.

## Configuration

Configuration is stored in `config.json` in the same directory as the executable. You can also edit it manually:

```json
{
  "settings": {
    "host": "0.0.0.0",
    "port": 3000,
    "require_auth": true,
    "enable_fallback": true,
    "enable_cors": true
  },
  "channels": [
    {
      "id": 1,
      "name": "OpenAI",
      "type": "openai",
      "base_url": "https://api.openai.com",
      "api_key": "sk-...",
      "models": ["gpt-4o", "gpt-4o-mini"],
      "enabled": true,
      "priority": 1,
      "timeout": 60
    }
  ],
  "tokens": [
    {
      "id": 1,
      "name": "My Token",
      "key": "sk-gw-...",
      "enabled": true,
      "allowed_models": [],
      "allowed_channels": []
    }
  ]
}
```

## Architecture

```
AI Gateway
├── main.py                 # Entry point
├── src/
│   ├── core/
│   │   ├── server.py       # FastAPI server + uvicorn lifecycle
│   │   └── proxy.py        # Request routing + provider adapters
│   ├── models/
│   │   └── config.py       # Pydantic config models + JSON persistence
│   └── gui/
│       ├── app.py          # wxPython App
│       ├── main_frame.py   # Main window + sidebar
│       ├── controller.py   # Business logic controller
│       ├── theme.py        # Color scheme + styling
│       ├── widgets.py      # Reusable UI components
│       └── panels/
│           ├── dashboard.py
│           ├── channels.py
│           ├── tokens.py
│           └── settings.py
└── config.json             # Runtime configuration (auto-created)
```

## Tech Stack

- **Python 3.10+**
- **FastAPI** — async HTTP server
- **uvicorn** — ASGI server
- **httpx** — async HTTP client for upstream requests
- **wxPython** — cross-platform GUI
- **PyInstaller** — Windows EXE packaging
- **Pydantic** — configuration validation
