"""
HTTP Channel Provider
处理所有通过 HTTP 协议访问的外部 AI 服务（OpenAI, Anthropic, Gemini, Ollama 等）
"""
import json
import time
from typing import AsyncGenerator, Union, Optional

import httpx

from src.core.channel_provider import ChannelProvider
from src.core.converter import FormatConverter, ProviderType
from src.models.config import ChannelConfig


class HTTPChannelProvider(ChannelProvider):
    """
    HTTP Channel Provider
    处理所有通过 HTTP 协议访问的外部 AI 服务（OpenAI, Anthropic, Gemini, Ollama 等）
    """

    def __init__(
        self,
        channel: ChannelConfig,
        client: httpx.AsyncClient,
        source_format: str = "openai",
    ):
        self.channel = channel
        self.client = client
        self.source_format = source_format
        self.target_format = channel.type.lower()

    @property
    def channel_type(self) -> str:
        return f"http:{self.target_format}"

    def _build_url(self, model: str, is_stream: bool) -> str:
        """构建上游 URL"""
        base = self.channel.base_url.rstrip("/")

        if self.target_format == "anthropic":
            return f"{base}/v1/messages"

        if self.target_format == "gemini":
            api_version = "v1beta"
            method = "streamGenerateContent" if is_stream else "generateContent"
            url = f"{base}/{api_version}/models/{model}:{method}"
            if is_stream:
                url += "?alt=sse"
            if self.channel.api_key:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}key={self.channel.api_key}"
            return url

        if self.target_format == "ollama":
            return f"{base}/api/chat"

        # 默认 OpenAI 兼容格式
        return f"{base}/chat/completions"

    def _build_headers(self, original_headers: dict) -> dict:
        """构建请求头"""
        headers = {}

        # 复制原始头（排除敏感头）
        skip_headers = {
            "host",
            "content-length",
            "transfer-encoding",
            "connection",
            "authorization",
            "x-api-key",
            "cookie",
        }
        for key, value in original_headers.items():
            if key.lower() not in skip_headers:
                headers[key] = value

        headers["Content-Type"] = "application/json"

        # 添加认证头
        if self.target_format == "anthropic":
            headers["x-api-key"] = self.channel.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.target_format != "gemini" and self.channel.api_key:
            headers["Authorization"] = f"Bearer {self.channel.api_key}"

        return headers

    def _transform_request(self, request: dict) -> tuple[dict, str]:
        """
        转换请求格式

        Returns:
            (转换后的请求体, 模型名称)
        """
        # 使用 FormatConverter 进行格式转换
        upstream_body, model, _ = FormatConverter.transform_request(
            request,
            ProviderType(self.source_format),
            ProviderType(self.target_format),
        )

        return upstream_body, model

    async def chat_completion(
            self,
            request: dict,
            api_key: str,
            source_format: str = "openai",
            **kwargs) -> Union[dict, AsyncGenerator[dict, None]]:
        """实现统一接口，直接返回原始格式的响应"""
        # 更新 source_format
        self.source_format = source_format

        # 转换请求
        upstream_body, model = self._transform_request(request)

        # 构建 URL 和 Headers
        is_stream = request.get("stream", False)
        url = self._build_url(model, is_stream)
        headers = self._build_headers(kwargs.get("original_headers", {}))

        if is_stream:
            # 返回异步生成器
            return self._stream_chat(url, headers, upstream_body, model)
        else:
            # 非流式请求
            return await self._non_stream_chat(url, headers, upstream_body,
                                               model)

    async def _non_stream_chat(self, url: str, headers: dict, body: dict,
                               model: str) -> dict:
        """非流式请求处理，返回原始格式"""
        response = await self.client.post(
            url,
            headers=headers,
            json=body,
            timeout=self.channel.timeout,
        )

        if response.status_code != 200:
            error_text = await response.aread()
            raise Exception(
                f"Upstream error {response.status_code}: {error_text.decode()}"
            )

        data = response.json()
        return FormatConverter.transform_response(
            data,
            ProviderType(self.target_format),
            ProviderType(self.source_format),
            model,
        )

    async def _stream_chat(self, url: str, headers: dict, body: dict,
                           model: str) -> AsyncGenerator[dict, None]:
        """流式请求处理，返回原始格式的字典"""
        async with self.client.stream(
                "POST",
                url,
                headers=headers,
                json=body,
                timeout=self.channel.timeout,
        ) as response:

            if response.status_code != 200:
                error_body = await response.aread()
                raise Exception(
                    f"Upstream error {response.status_code}: {error_body.decode()}"
                )

            # 格式相同直接透传 - 使用更高效的逐行读取
            if self.source_format == self.target_format:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            continue
                        try:
                            event_data = json.loads(data_str)
                            yield event_data
                        except json.JSONDecodeError:
                            pass
                # Gemini 特殊处理
                if self.target_format == "gemini":
                    yield {
                        "id":
                        f"chatcmpl-{int(time.time())}",
                        "model":
                        model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }],
                    }
                return

            # 需要格式转换
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        continue
                    try:
                        event_data = json.loads(data_str)
                        transformed = FormatConverter.transform_stream_chunk(
                            event_data, ProviderType(self.target_format),
                            ProviderType(self.source_format), model)
                        if transformed:
                            yield transformed
                    except json.JSONDecodeError:
                        pass

            # Gemini 特殊处理
            if self.target_format == "gemini":
                yield {
                    "id":
                    f"chatcmpl-{int(time.time())}",
                    "model":
                    model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }],
                }

    async def is_available(self) -> bool:
        """检查 channel 是否可用"""
        try:
            # 简单检查：尝试访问 models 端点
            url = f"{self.channel.base_url.rstrip('/')}/models"
            response = await self.client.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
