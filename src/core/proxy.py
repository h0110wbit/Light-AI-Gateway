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
from src.core.converter import (
    transform_request_for_provider,
    transform_response_from_provider,
    transform_stream_chunk_from_provider,
    FormatConverter,
    ProviderType,
)

logger = logging.getLogger("ai-gateway.proxy")

# Headers that should not be forwarded to upstream (hop-by-hop or sensitive)
SKIP_HEADERS = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "authorization",
    "x-api-key",
    "x-goog-api-key",
    "cookie",
}


def build_upstream_headers(channel: ChannelConfig,
                           original_headers: dict) -> dict:
    """
    Build headers for the upstream request.
    
    Preserves most original headers but removes hop-by-hop and auth headers,
    then adds channel-specific authentication.
    """
    headers = {}

    for key, value in original_headers.items():
        key_lower = key.lower()
        if key_lower in SKIP_HEADERS:
            continue
        headers[key] = value

    headers["Content-Type"] = "application/json"

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

    return headers


def get_upstream_url(
    channel: ChannelConfig,
    model: str = "",
    is_stream: bool = False,
    endpoint_type: str = "chat",
) -> str:
    """
    Build the full upstream URL based on channel type and endpoint.
    
    Args:
        channel: Channel configuration
        model: Model name (required for Gemini and some endpoints)
        is_stream: Whether this is a streaming request
        endpoint_type: Type of endpoint (chat, embeddings, models, etc.)
        
    Returns:
        Full upstream URL
    """
    base = channel.base_url.rstrip("/")
    channel_type = channel.type.lower()

    if channel_type == "anthropic":
        if endpoint_type == "chat":
            url = f"{base}/v1/messages"
        elif endpoint_type == "models":
            url = f"{base}/v1/models"
        else:
            url = f"{base}/v1/{endpoint_type}"
        return url

    if channel_type == "gemini":
        api_version = "v1beta"
        if endpoint_type == "chat":
            method = "streamGenerateContent" if is_stream else "generateContent"
            url = f"{base}/{api_version}/models/{model}:{method}"
            if is_stream:
                url += "?alt=sse"
        elif endpoint_type == "models":
            url = f"{base}/{api_version}/models"
        else:
            url = f"{base}/{api_version}/{endpoint_type}"
        if channel.api_key:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}key={channel.api_key}"
        return url

    if channel_type == "ollama":
        if endpoint_type == "chat":
            url = f"{base}/api/chat"
        elif endpoint_type == "completions":
            url = f"{base}/api/generate"
        elif endpoint_type == "embeddings":
            url = f"{base}/api/embeddings"
        elif endpoint_type == "models":
            url = f"{base}/api/tags"
        else:
            url = f"{base}/api/{endpoint_type}"
        return url

    if endpoint_type == "chat":
        url = f"{base}/chat/completions"
    elif endpoint_type == "completions":
        url = f"{base}/completions"
    elif endpoint_type == "embeddings":
        url = f"{base}/embeddings"
    elif endpoint_type == "models":
        url = f"{base}/models"
    elif endpoint_type == "images":
        url = f"{base}/images/generations"
    elif endpoint_type == "audio_speech":
        url = f"{base}/audio/speech"
    elif endpoint_type == "audio_transcriptions":
        url = f"{base}/audio/transcriptions"
    else:
        url = f"{base}/{endpoint_type}"
    return url


async def stream_response(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    body: dict,
    channel: ChannelConfig,
    model: str = "",
    source_format: str = "openai",
) -> AsyncGenerator[bytes, None]:
    """
    Stream response from upstream provider.
    
    Args:
        client: HTTP client
        method: HTTP method
        url: Target URL
        headers: Request headers
        body: Request body
        channel: Channel configuration
        model: Model name
        source_format: Format of the original request (openai, anthropic, gemini)
    """
    target_format = channel.type.lower()

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

            # If source format matches target format, pass through
            if source_format == target_format:
                async for chunk in response.aiter_bytes():
                    yield chunk
                return

            # Transform stream chunks from target format to source format
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
                        # Transform chunk from target format to source format
                        transformed_chunk = FormatConverter.transform_stream_chunk(
                            event_data, ProviderType(target_format),
                            ProviderType(source_format), model)
                        if transformed_chunk:
                            yield f"data: {json.dumps(transformed_chunk)}\n\n".encode(
                            )
                    except json.JSONDecodeError:
                        pass
                elif line.startswith("event: "):
                    pass

            # Gemini doesn't send [DONE], so we add it
            if target_format == "gemini":
                yield b"data: [DONE]\n\n"

    except httpx.TimeoutException:
        yield f"data: {json.dumps({'error': 'Upstream request timed out'})}\n\n".encode(
        )
        yield b"data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
        yield b"data: [DONE]\n\n"


class ProxyEngine:
    """Main proxy engine for routing requests to upstream providers"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._proxy_clients: dict = {}

    def update_config(self, config: AppConfig):
        self.config = config
        self._clear_proxy_clients()

    def _clear_proxy_clients(self):
        """Clear cached proxy clients to force re-creation with new settings."""
        for client in self._proxy_clients.values():
            if not client.is_closed:
                asyncio.create_task(client.aclose())
        self._proxy_clients.clear()

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(120.0),
                limits=httpx.Limits(max_connections=100,
                                    max_keepalive_connections=20),
            )
        return self._client

    async def get_proxy_client(self, proxy_url: str) -> httpx.AsyncClient:
        """
        Get or create an HTTP client with proxy support.
        
        Args:
            proxy_url: Proxy URL (e.g., http://127.0.0.1:7890, socks5://127.0.0.1:1080)
            
        Returns:
            httpx.AsyncClient configured with the specified proxy
        """
        if proxy_url in self._proxy_clients:
            client = self._proxy_clients[proxy_url]
            if not client.is_closed:
                return client

        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_connections=100,
                                max_keepalive_connections=20),
            proxy=proxy_url,
        )
        self._proxy_clients[proxy_url] = client
        return client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        for client in self._proxy_clients.values():
            if not client.is_closed:
                await client.aclose()
        self._proxy_clients.clear()

    async def proxy_request(
        self,
        request: Request,
        endpoint_type: str = "chat",
        token_key: Optional[str] = None,
        source_format: str = "openai",
    ) -> Union[StreamingResponse, JSONResponse]:
        """
        Proxy a request to upstream channels.
        
        Args:
            request: FastAPI request object
            endpoint_type: Type of endpoint (chat, embeddings, models, etc.)
            token_key: Optional authentication token
            source_format: Format of the incoming request (openai, anthropic, gemini)
        """
        source_format = source_format.lower()
        if source_format not in ("openai", "anthropic", "gemini"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported source format: {source_format}")

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

        # Check if high availability mode is enabled
        high_availability = self.config.settings.high_availability_mode

        if high_availability:
            # In high availability mode, ignore model parameter
            # Get all enabled channels regardless of model support
            channels = self.config.get_enabled_channels()
            logger.info(
                f"High availability mode enabled - routing to any available channel"
            )
        else:
            # Check token model permissions
            if token_config and token_config.allowed_models and model:
                model_lower = model.lower()
                allowed_lower = [
                    m.lower() for m in token_config.allowed_models
                ]
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
            if high_availability:
                raise HTTPException(
                    status_code=503,
                    detail="No available channels in high availability mode")
            else:
                raise HTTPException(
                    status_code=503,
                    detail=f"No available channels for model '{model}'")

        # Try channels in priority order with fallback
        last_error = None
        for channel in channels:
            try:
                return await self._forward_to_channel(request, channel,
                                                      endpoint_type, body,
                                                      source_format,
                                                      high_availability)
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
        endpoint_type: str,
        body: dict,
        source_format: str = "openai",
        high_availability: bool = False,
    ) -> Union[StreamingResponse, JSONResponse]:
        """
        Forward request to a specific channel.
        
        Args:
            request: FastAPI request object
            channel: Target channel configuration
            endpoint_type: Type of endpoint (chat, embeddings, models, etc.)
            body: Request body
            source_format: Format of the incoming request (openai, anthropic, gemini)
            high_availability: Whether high availability mode is enabled
        """
        target_format = channel.type.lower()

        # In high availability mode, replace model with channel's supported model
        if high_availability and channel.models:
            # Use the first model from channel's model list
            replacement_model = channel.models[0]
            body = dict(body)  # Create a copy to avoid modifying original
            body["model"] = replacement_model
            logger.info(
                f"High availability mode: replaced model with '{replacement_model}' for channel '{channel.name}'"
            )

        # Transform request body from source format to target format
        upstream_body, model, extra_info = FormatConverter.transform_request(
            body, ProviderType(source_format), ProviderType(target_format))
        is_streaming = extra_info.get("is_stream", body.get("stream", False))

        # Build upstream URL based on channel type and endpoint
        url = get_upstream_url(channel, model, is_streaming, endpoint_type)

        # Build headers
        headers = build_upstream_headers(channel, dict(request.headers))

        # Get appropriate client (with or without proxy)
        if channel.proxy_enabled and channel.proxy_url:
            client = await self.get_proxy_client(channel.proxy_url)
        else:
            client = await self.get_client()

        if is_streaming:
            return StreamingResponse(stream_response(client, "POST", url,
                                                     headers, upstream_body,
                                                     channel, model,
                                                     source_format),
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
                    # Transform response from target format back to source format
                    transformed = FormatConverter.transform_response(
                        data, ProviderType(target_format),
                        ProviderType(source_format), model)
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
