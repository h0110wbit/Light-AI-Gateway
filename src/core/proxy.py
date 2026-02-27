"""
Core proxy logic for AI Gateway
Handles request forwarding to upstream AI providers with streaming support
"""
from __future__ import annotations

import httpx
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional, Union
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from src.models.config import AppConfig, ChannelConfig
from src.core.rate_limiter import (
    RateLimiterManager,
    RateLimitConfig,
)
from src.core.channel_provider import ChannelProvider
from src.core.channel_providers import (
    HTTPChannelProvider,
    GLMChannelProvider,
    KimiChannelProvider,
    DeepSeekChannelProvider,
    QwenChannelProvider,
    MiniMaxChannelProvider,
)

logger = logging.getLogger("ai-gateway.proxy")


class ProxyEngine:
    """Main proxy engine for routing requests to upstream providers"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._proxy_clients: dict = {}
        self._rate_limiter_manager = RateLimiterManager()
        # Channel 选择锁，避免高并发下的竞争条件
        self._channel_select_lock = asyncio.Lock()
        # 全局轮询计数器，用于负载均衡
        self._global_round_robin = 0

    def update_config(self, config: AppConfig):
        self.config = config
        self._clear_proxy_clients()

    def _clear_proxy_clients(self):
        """Clear cached proxy clients to force re-creation with new settings."""
        for client in self._proxy_clients.values():
            if not client.is_closed:
                try:
                    # 尝试获取事件循环，如果失败则使用同步关闭
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(client.aclose())
                except RuntimeError:
                    # 没有运行的事件循环，使用同步关闭
                    try:
                        import threading

                        # 在新线程中运行异步关闭
                        def close_client():
                            try:
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                new_loop.run_until_complete(client.aclose())
                                new_loop.close()
                            except Exception:
                                pass

                        thread = threading.Thread(target=close_client)
                        thread.start()
                        thread.join(timeout=5.0)
                    except Exception:
                        pass
        self._proxy_clients.clear()

    def _get_rate_limit_config(self,
                               channel: ChannelConfig) -> RateLimitConfig:
        """
        Build rate limit configuration from channel settings.
        
        Args:
            channel: Channel configuration
            
        Returns:
            RateLimitConfig instance
        """
        return RateLimitConfig(
            max_concurrency=channel.max_concurrency,
            min_concurrency=channel.min_concurrency,
            max_adaptive_concurrency=channel.max_adaptive_concurrency,
            response_time_low=channel.response_time_low,
            response_time_high=channel.response_time_high,
            error_rate_threshold=channel.error_rate_threshold,
            increase_step=channel.increase_step,
            decrease_factor=channel.decrease_factor,
            stats_window_size=channel.stats_window_size,
            cooldown_seconds=channel.cooldown_seconds,
        )

    async def _get_limiter_for_channel(self, channel: ChannelConfig):
        """
        Get or create a rate limiter for a channel.
        
        Args:
            channel: Channel configuration
            
        Returns:
            AdaptiveLimiter instance
        """
        config = self._get_rate_limit_config(channel)
        return await self._rate_limiter_manager.get_or_create_limiter(
            channel.id, channel.name, config)

    def _is_channel_healthy(self, channel: ChannelConfig) -> bool:
        """
        Check if a channel is healthy based on recent statistics.
        
        A channel is considered unhealthy if:
        - Error rate is above 50% in recent requests
        - Or average response time is above 30 seconds
        
        Args:
            channel: Channel configuration
            
        Returns:
            True if channel is healthy, False otherwise
        """
        limiter = self._rate_limiter_manager.get_limiter(channel.id)
        if not limiter:
            return True

        stats = limiter.stats
        if stats.sample_count < 5:
            return True

        if stats.error_rate > 0.5:
            return False

        if stats.avg_response_time > 30.0:
            return False

        return True

    def _get_healthy_channels(self,
                              channels: list,
                              high_availability: bool = False) -> list:
        """
        Filter and sort channels by health status.
        
        Returns channels sorted by:
        1. Health status (healthy first)
        2. Priority (lower number first)
        3. Current load (fewer active requests first)
        
        Args:
            channels: List of channel configurations
            high_availability: Whether high availability mode is enabled
            
        Returns:
            Sorted list of channels
        """
        channel_scores = []

        for channel in channels:
            is_healthy = self._is_channel_healthy(channel)
            limiter = self._rate_limiter_manager.get_limiter(channel.id)
            active_requests = limiter.active_requests if limiter else 0

            # Score: (is_healthy descending, priority ascending, load ascending)
            score = (
                1 if is_healthy else 0,  # Healthy channels first
                -channel.priority,  # Higher priority (lower number) first
                active_requests,  # Less loaded channels first
            )
            channel_scores.append((score, channel))

        # Sort by score (descending for health, ascending for priority and load)
        channel_scores.sort(key=lambda x: x[0], reverse=True)
        return [channel for _, channel in channel_scores]

    async def _select_best_channel(
            self,
            channels: list,
            high_availability: bool = False) -> tuple[ChannelConfig, any]:
        """
        选择最佳 channel，带锁保护避免竞争条件

        策略：
        1. 使用全局轮询策略均匀分配请求
        2. 如果当前轮询的 channel 已满，尝试下一个
        3. 如果都满了，等待当前轮询位置的 channel

        Args:
            channels: 可用 channel 列表
            high_availability: 是否高可用模式

        Returns:
            (选中的 channel, 对应的 limiter)
        """
        async with self._channel_select_lock:
            # 过滤出健康的 channel
            healthy_channels = [
                ch for ch in channels if self._is_channel_healthy(ch)
            ]

            if not healthy_channels:
                raise HTTPException(status_code=503,
                                    detail="No available channels")

            # 使用全局轮询计数器获取当前位置
            current_idx = self._global_round_robin % len(healthy_channels)
            self._global_round_robin += 1

            # 从轮询位置开始尝试获取可用 channel
            for i in range(len(healthy_channels)):
                idx = (current_idx + i) % len(healthy_channels)
                channel = healthy_channels[idx]
                limiter = await self._get_limiter_for_channel(channel)
                active = limiter.active_requests
                limit = limiter.current_limit

                logger.debug(
                    f"[Channel Select] {channel.name}: active={active}, limit={limit}"
                )

                # 尝试获取许可
                if limiter.try_acquire():
                    logger.info(
                        f"[Channel Select] Selected {channel.name} (active={active}, limit={limit})"
                    )
                    return channel, limiter

            # 所有 channel 都满了，等待当前轮询位置的 channel
            best_channel = healthy_channels[current_idx]
            best_limiter = await self._get_limiter_for_channel(best_channel)
            logger.info(
                f"[Channel Select] All channels full, waiting for {best_channel.name}"
            )
            await best_limiter.acquire()
            return best_channel, best_limiter

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,  # 连接超时
                    read=self.config.settings.default_timeout,  # 读取超时
                    write=10.0,  # 写入超时
                    pool=5.0,  # 连接池获取超时
                ),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=100,  # 最大连接数
                    max_keepalive_connections=20,  # 最大保持连接数
                    keepalive_expiry=30.0,  # 连接保持时间
                ),
                http2=True,  # 启用 HTTP/2
            )
        return self._client

    async def get_proxy_client(self, proxy_url: str) -> httpx.AsyncClient:
        """Get or create an HTTP client with proxy configuration."""
        if proxy_url not in self._proxy_clients or self._proxy_clients[
                proxy_url].is_closed:
            self._proxy_clients[proxy_url] = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=self.config.settings.default_timeout,
                    write=10.0,
                    pool=5.0,
                ),
                follow_redirects=True,
                proxy=proxy_url,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
                http2=True,
            )
        return self._proxy_clients[proxy_url]

    async def close(self):
        """Close all HTTP clients."""
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

        # 使用带锁的 channel 选择策略
        # 优先选择有可用槽位的 channel，避免竞争条件
        channel, limiter = await self._select_best_channel(
            channels, high_availability)

        try:
            return await self._forward_to_channel(request, channel,
                                                  endpoint_type, body,
                                                  source_format,
                                                  high_availability, limiter)
        except HTTPException as e:
            if e.status_code in (401, 403):
                limiter.release()
                raise

            # 如果允许 fallback，尝试其他 channel
            if self.config.settings.enable_fallback:
                logger.warning(
                    f"Channel {channel.name} failed: {e.detail}, trying fallback..."
                )
                limiter.release()
                return await self._try_fallback_channels(
                    request, channels, channel, endpoint_type, body,
                    source_format, high_availability)
            else:
                limiter.release()
                raise
        except Exception as e:
            limiter.release()
            raise HTTPException(status_code=502, detail=str(e))

    async def _try_fallback_channels(
        self,
        request: Request,
        channels: list,
        failed_channel: ChannelConfig,
        endpoint_type: str,
        body: dict,
        source_format: str,
        high_availability: bool,
    ):
        """
        尝试其他 channel 作为 fallback
        """
        last_error = None

        for channel in channels:
            if channel.id == failed_channel.id:
                continue

            limiter = await self._get_limiter_for_channel(channel)
            await limiter.acquire()

            try:
                return await self._forward_to_channel(request, channel,
                                                      endpoint_type, body,
                                                      source_format,
                                                      high_availability,
                                                      limiter)
            except HTTPException as e:
                if e.status_code in (401, 403):
                    limiter.release()
                    raise
                last_error = e
                logger.warning(
                    f"Fallback channel {channel.name} failed: {e.detail}, trying next..."
                )
                limiter.release()
                continue
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Fallback channel {channel.name} error: {e}, trying next..."
                )
                limiter.release()
                continue

        raise last_error or HTTPException(
            status_code=503, detail="All upstream channels failed")

    async def _create_provider(
        self,
        channel: ChannelConfig,
        request: Request,
        source_format: str,
    ):
        """
        创建对应的 ChannelProvider
        
        Args:
            channel: Channel配置
            request: FastAPI请求对象
            source_format: 源格式
            
        Returns:
            ChannelProvider实例
        """
        target_format = channel.type.lower()

        if target_format == "builtin":
            # 内置Provider
            provider_name = channel.base_url.lower()
            provider_map = {
                "glm": GLMChannelProvider,
                "kimi": KimiChannelProvider,
                "deepseek": DeepSeekChannelProvider,
                "qwen": QwenChannelProvider,
                "minimax": MiniMaxChannelProvider,
            }

            provider_class = provider_map.get(provider_name)
            if not provider_class:
                raise ValueError(f"Unknown builtin provider: {provider_name}")

            return provider_class(channel)
        else:
            # HTTP Provider
            if channel.proxy_enabled and channel.proxy_url:
                client = await self.get_proxy_client(channel.proxy_url)
            else:
                client = await self.get_client()

            return HTTPChannelProvider(channel, client, source_format)

    async def _forward_to_channel(
        self,
        request: Request,
        channel: ChannelConfig,
        endpoint_type: str,
        body: dict,
        source_format: str,
        high_availability: bool,
        limiter,
    ) -> Union[StreamingResponse, JSONResponse]:
        """
        统一的 channel 转发入口（带外部 limiter）

        使用 ChannelProvider 统一接口处理所有 channel 类型
        limiter 已在外部获取，本方法只负责释放
        """
        # 高可用模式替换模型
        if high_availability and channel.models:
            body = dict(body)  # 创建副本
            body["model"] = channel.models[0]
            logger.info(
                f"High availability mode: replaced model with '{channel.models[0]}' for channel '{channel.name}'"
            )

        # 创建Provider
        provider = await self._create_provider(channel, request, source_format)

        start_time = time.time()
        is_error = False
        status_code = 200

        # 从 body 获取 stream 参数
        is_stream = body.get("stream", False)

        try:
            # 统一调用接口，直接传入 body 字典
            result = await provider.chat_completion(
                request=body,
                api_key=channel.api_key,
                source_format=source_format,
                original_headers=dict(request.headers),
            )

            if is_stream:
                # 流式响应
                return StreamingResponse(self._wrap_stream(
                    result, limiter, start_time),
                                         media_type="text/event-stream",
                                         headers={
                                             "Cache-Control": "no-cache",
                                             "X-Accel-Buffering": "no",
                                             "Connection": "keep-alive",
                                         })
            else:
                # 非流式响应 - result 已经是原始格式的字典
                status_code = 200
                return JSONResponse(content=result, status_code=200)

        except Exception as e:
            is_error = True
            status_code = 502
            logger.error(f"Channel {channel.name} error: {e}")
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            # 非流式在这里释放，流式在生成器中释放
            if not is_stream:
                response_time = time.time() - start_time
                limiter.record_request(response_time, is_error, status_code)
                limiter.release()

    async def _wrap_stream(
        self,
        stream_generator: AsyncGenerator[dict, None],
        limiter,
        start_time: float,
    ) -> AsyncGenerator[bytes, None]:
        """统一包装流式响应 - 直接返回原始格式的字典"""
        is_error = False
        status_code = 200

        try:
            async for chunk in stream_generator:
                # chunk 已经是原始格式的字典，直接序列化
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

        except Exception as e:
            is_error = True
            status_code = 500
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()
            yield b"data: [DONE]\n\n"
        finally:
            response_time = time.time() - start_time
            limiter.record_request(response_time, is_error, status_code)
            limiter.release()

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
