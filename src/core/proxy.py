"""
Core proxy logic for AI Gateway
Handles request forwarding to upstream AI providers with streaming support
"""
from __future__ import annotations

import httpx
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional, Tuple, Union
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from src.models.config import AppConfig, ChannelConfig

logger = logging.getLogger("ai-gateway.proxy")

# Mapping of provider types to their API paths
PROVIDER_PATHS = {
    "openai": {
        "chat": "/v1/chat/completions",
        "completions": "/v1/completions",
        "embeddings": "/v1/embeddings",
        "models": "/v1/models",
        "images": "/v1/images/generations",
        "audio_speech": "/v1/audio/speech",
        "audio_transcriptions": "/v1/audio/transcriptions",
    },
    "anthropic": {
        "chat": "/v1/messages",
        "models": "/v1/models",
    },
    "gemini": {
        "chat": "/v1beta/models/{model}:generateContent",
        "models": "/v1beta/models",
    },
    "ollama": {
        "chat": "/api/chat",
        "completions": "/api/generate",
        "models": "/api/tags",
        "embeddings": "/api/embeddings",
    },
    "custom": {
        "chat": "/v1/chat/completions",
        "completions": "/v1/completions",
        "embeddings": "/v1/embeddings",
        "models": "/v1/models",
    }
}

# Anthropic-specific header mapping
ANTHROPIC_HEADERS = {
    "x-api-key": None,  # handled specially
    "anthropic-version": "2023-06-01",
}


def build_upstream_headers(channel: ChannelConfig,
                           original_headers: dict) -> dict:
    """Build headers for the upstream request based on channel type"""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AI-Gateway/1.0",
    }

    channel_type = channel.type.lower()

    if channel_type == "anthropic":
        headers["x-api-key"] = channel.api_key
        headers["anthropic-version"] = "2023-06-01"
    elif channel_type == "gemini":
        # Gemini uses API key as query param, not header
        pass
    else:
        # OpenAI-compatible
        if channel.api_key:
            headers["Authorization"] = f"Bearer {channel.api_key}"

    # Forward some original headers that might be useful
    for h in ["Accept", "Accept-Language"]:
        if h.lower() in {k.lower() for k in original_headers}:
            headers[h] = original_headers.get(
                h, original_headers.get(h.lower(), ""))

    return headers


def get_upstream_url(channel: ChannelConfig, path: str) -> str:
    """Build the full upstream URL"""
    base = channel.base_url.rstrip("/")

    channel_type = channel.type.lower()

    # For Gemini, add API key as query param
    if channel_type == "gemini" and channel.api_key:
        sep = "&" if "?" in path else "?"
        return f"{base}{path}{sep}key={channel.api_key}"

    return f"{base}{path}"


def transform_request_for_provider(body: dict, channel: ChannelConfig) -> dict:
    """Transform request body if needed for specific providers"""
    channel_type = channel.type.lower()

    if channel_type == "anthropic":
        return transform_openai_to_anthropic(body)

    # For all other providers (openai, custom, ollama), pass through as-is
    return body


def transform_openai_to_anthropic(body: dict) -> dict:
    """Transform OpenAI chat format to Anthropic messages format"""
    messages = body.get("messages", [])
    system_prompt = None
    anthropic_messages = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            system_prompt = content
        elif role in ("user", "assistant"):
            anthropic_messages.append({
                "role":
                role,
                "content":
                content if isinstance(content, str) else content
            })

    result = {
        "model": body.get("model", "claude-3-5-sonnet-20241022"),
        "messages": anthropic_messages,
        "max_tokens": body.get("max_tokens", 4096),
    }

    if system_prompt:
        result["system"] = system_prompt

    if "temperature" in body:
        result["temperature"] = body["temperature"]
    if "top_p" in body:
        result["top_p"] = body["top_p"]
    if "stream" in body:
        result["stream"] = body["stream"]

    return result


def transform_response_from_provider(response_data: dict,
                                     channel: ChannelConfig) -> dict:
    """Transform response back to OpenAI format if needed"""
    channel_type = channel.type.lower()

    if channel_type == "anthropic":
        return transform_anthropic_to_openai(response_data)

    return response_data


def transform_anthropic_to_openai(data: dict) -> dict:
    """Transform Anthropic response to OpenAI format"""
    if data.get("type") == "error":
        return data

    content_blocks = data.get("content", [])
    text_content = ""

    for block in content_blocks:
        if block.get("type") == "text":
            text_content += block.get("text", "")

    usage = data.get("usage", {})

    return {
        "id":
        data.get("id", ""),
        "object":
        "chat.completion",
        "created":
        0,
        "model":
        data.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": text_content,
            },
            "finish_reason": data.get("stop_reason", "stop"),
        }],
        "usage": {
            "prompt_tokens":
            usage.get("input_tokens", 0),
            "completion_tokens":
            usage.get("output_tokens", 0),
            "total_tokens":
            usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }
    }


async def stream_response(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    body: dict,
    channel: ChannelConfig,
) -> AsyncGenerator[bytes, None]:
    """Stream response from upstream provider"""
    channel_type = channel.type.lower()

    try:
        async with client.stream(
                method,
                url,
                headers=headers,
                json=body,
                timeout=channel.timeout,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                error_text = error_body.decode('utf-8', errors='replace')
                yield f"data: {json.dumps({'error': error_text, 'status': response.status_code})}\n\n".encode(
                )
                yield b"data: [DONE]\n\n"
                return

            if channel_type == "anthropic":
                # Transform Anthropic SSE to OpenAI SSE format
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield b"data: [DONE]\n\n"
                            continue
                        try:
                            event_data = json.loads(data_str)
                            openai_chunk = transform_anthropic_stream_chunk(
                                event_data)
                            if openai_chunk:
                                yield f"data: {json.dumps(openai_chunk)}\n\n".encode(
                                )
                        except json.JSONDecodeError:
                            pass
                    elif line.startswith("event: "):
                        pass  # ignore event type lines
            else:
                # Pass through OpenAI-compatible SSE
                async for chunk in response.aiter_bytes():
                    yield chunk

    except httpx.TimeoutException:
        yield f"data: {json.dumps({'error': 'Upstream request timed out'})}\n\n".encode(
        )
        yield b"data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
        yield b"data: [DONE]\n\n"


def transform_anthropic_stream_chunk(event_data: dict) -> Optional[dict]:
    """Transform a single Anthropic SSE event to OpenAI delta format"""
    event_type = event_data.get("type", "")

    if event_type == "content_block_delta":
        delta = event_data.get("delta", {})
        if delta.get("type") == "text_delta":
            return {
                "id":
                "chatcmpl-stream",
                "object":
                "chat.completion.chunk",
                "created":
                0,
                "model":
                "",
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": delta.get("text", "")
                    },
                    "finish_reason": None,
                }]
            }
    elif event_type == "message_stop":
        return {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }]
        }
    elif event_type == "message_start":
        return {
            "id":
            event_data.get("message", {}).get("id", "chatcmpl-stream"),
            "object":
            "chat.completion.chunk",
            "created":
            0,
            "model":
            event_data.get("message", {}).get("model", ""),
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant"
                },
                "finish_reason": None,
            }]
        }

    return None


class ProxyEngine:
    """Main proxy engine for routing requests to upstream providers"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    def update_config(self, config: AppConfig):
        self.config = config

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(120.0),
                limits=httpx.Limits(max_connections=100,
                                    max_keepalive_connections=20),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def proxy_request(
        self,
        request: Request,
        path: str,
        token_key: Optional[str] = None,
    ) -> Union[StreamingResponse, JSONResponse]:

        # Validate token if auth is required
        token_config = None
        if self.config.settings.require_auth:
            if not token_key:
                raise HTTPException(status_code=401,
                                    detail="Authentication required")

            token_config = self.config.validate_token(token_key)
            if not token_config:
                raise HTTPException(status_code=401,
                                    detail="Invalid or disabled token")

        # Read request body
        body = {}
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = json.loads(body_bytes)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # Get model from request
        model = body.get("model", "")

        # Check token model permissions
        if token_config and token_config.allowed_models and model:
            model_lower = model.lower()
            allowed_lower = [m.lower() for m in token_config.allowed_models]
            if model_lower not in allowed_lower:
                raise HTTPException(
                    status_code=403,
                    detail=f"Model '{model}' not allowed for this token")

        # Find suitable channels
        channels = self.config.get_channels_for_model(model)

        # Filter by token channel permissions
        if token_config and token_config.allowed_channels:
            channels = [
                ch for ch in channels if ch.id in token_config.allowed_channels
            ]

        if not channels:
            raise HTTPException(
                status_code=503,
                detail=f"No available channels for model '{model}'")

        # Try channels in priority order with fallback
        last_error = None
        for channel in channels:
            try:
                return await self._forward_to_channel(request, channel, path,
                                                      body)
            except HTTPException as e:
                if e.status_code in (401, 403):
                    raise  # Don't retry auth errors
                last_error = e
                if not self.config.settings.enable_fallback:
                    raise
                logger.warning(
                    f"Channel {channel.name} failed: {e.detail}, trying next..."
                )
                continue
            except Exception as e:
                last_error = e
                if not self.config.settings.enable_fallback:
                    raise HTTPException(status_code=502, detail=str(e))
                logger.warning(
                    f"Channel {channel.name} error: {e}, trying next...")
                continue

        # All channels failed
        raise last_error or HTTPException(
            status_code=503, detail="All upstream channels failed")

    async def _forward_to_channel(
        self,
        request: Request,
        channel: ChannelConfig,
        path: str,
        body: dict,
    ) -> Union[StreamingResponse, JSONResponse]:

        # Build upstream URL
        url = get_upstream_url(channel, path)

        # Build headers
        headers = build_upstream_headers(channel, dict(request.headers))

        # Transform body for provider if needed
        upstream_body = transform_request_for_provider(body, channel)

        is_streaming = upstream_body.get("stream", False)
        client = await self.get_client()

        if is_streaming:
            return StreamingResponse(stream_response(client, "POST", url,
                                                     headers, upstream_body,
                                                     channel),
                                     media_type="text/event-stream",
                                     headers={
                                         "Cache-Control": "no-cache",
                                         "X-Accel-Buffering": "no",
                                         "Connection": "keep-alive",
                                     })
        else:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json=upstream_body,
                    timeout=channel.timeout,
                )

                if response.status_code == 200:
                    data = response.json()
                    transformed = transform_response_from_provider(
                        data, channel)
                    return JSONResponse(content=transformed, status_code=200)
                else:
                    error_detail = f"Upstream returned {response.status_code}"
                    try:
                        err_data = response.json()
                        if "error" in err_data:
                            error_detail = err_data["error"].get(
                                "message", error_detail)
                    except Exception:
                        pass
                    raise HTTPException(status_code=response.status_code,
                                        detail=error_detail)

            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail=f"Channel '{channel.name}' timed out")
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=502,
                    detail=
                    f"Channel '{channel.name}' connection error: {str(e)}")

    async def list_models(self, token_key: Optional[str] = None) -> dict:
        """List all available models across all enabled channels"""

        if self.config.settings.require_auth and token_key:
            token_config = self.config.validate_token(token_key)
            if not token_config:
                raise HTTPException(status_code=401, detail="Invalid token")

        all_models = set()

        for channel in self.config.get_enabled_channels():
            if channel.models:
                all_models.update(channel.models)

        models_list = [{
            "id": model,
            "object": "model",
            "created": 0,
            "owned_by": "ai-gateway",
        } for model in sorted(all_models)]

        return {
            "object": "list",
            "data": models_list,
        }
