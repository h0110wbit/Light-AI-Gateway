"""
内置 Channel Provider
所有内置 Provider（GLM, Kimi, DeepSeek 等）继承此类
"""
from abc import abstractmethod
from typing import AsyncGenerator, Union, Optional
import time

from src.core.channel_provider import ChannelProvider
from src.core.converter import FormatConverter, ProviderType
from src.models.config import ChannelConfig


class BuiltinChannelProvider(ChannelProvider):
    """
    内置 Channel Provider 基类
    所有内置 Provider（GLM, Kimi, DeepSeek 等）继承此类
    
    内置 Provider 统一返回 OpenAI 格式，然后根据 source_format 转换为目标格式
    """

    def __init__(self, channel: ChannelConfig):
        self.channel = channel

    @property
    def channel_type(self) -> str:
        return f"builtin:{self.provider_name}"

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称，如 'glm', 'kimi'"""
        pass

    @abstractmethod
    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ) -> Union[dict, AsyncGenerator[dict, None]]:
        """
        调用具体的内置 Provider

        Returns:
            非流式：响应字典
            流式：异步生成器
        """
        pass

    async def chat_completion(
            self,
            request: dict,
            api_key: str,
            source_format: str = "openai",
            **kwargs) -> Union[dict, AsyncGenerator[dict, None]]:
        """实现统一接口，返回原始格式的响应"""

        messages = request.get("messages", [])
        model = request.get("model", "")
        is_stream = request.get("stream", False)

        result = await self._call_provider(
            messages=messages,
            model=model,
            stream=is_stream,
            api_key=api_key,
        )

        if is_stream:
            # 包装生成器，转换为原始格式
            async def chunk_generator():
                async for raw_chunk in result:
                    # 处理不同类型的响应
                    if hasattr(raw_chunk, "to_dict"):
                        raw_dict = raw_chunk.to_dict()
                    elif isinstance(raw_chunk, dict):
                        raw_dict = raw_chunk
                    else:
                        raw_dict = {
                            "id":
                            f"chatcmpl-{int(time.time())}",
                            "object":
                            "chat.completion.chunk",
                            "created":
                            int(time.time()),
                            "model":
                            model,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "content": str(raw_chunk)
                                }
                            }],
                        }

                    # 转换为 source_format 格式
                    transformed = FormatConverter.transform_stream_chunk(
                        raw_dict, ProviderType.OPENAI,
                        ProviderType(source_format), model)
                    if transformed:
                        yield transformed

            return chunk_generator()
        else:
            # 处理不同类型的响应
            if hasattr(result, "to_dict"):
                raw_dict = result.to_dict()
            elif isinstance(result, dict):
                raw_dict = result
            else:
                raw_dict = {
                    "id":
                    f"chatcmpl-{int(time.time())}",
                    "object":
                    "chat.completion",
                    "created":
                    int(time.time()),
                    "model":
                    model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": str(result)
                        },
                        "finish_reason": "stop",
                    }],
                }

            # 转换为 source_format 格式
            return FormatConverter.transform_response(
                raw_dict,
                ProviderType.OPENAI,
                ProviderType(source_format),
                model,
            )

    async def is_available(self) -> bool:
        """检查 Provider 是否可用"""
        try:
            # 尝试用空消息验证
            return len(self.channel.api_key) > 0
        except Exception:
            return False


class GLMChannelProvider(BuiltinChannelProvider):
    """GLM 内置 Provider"""

    @property
    def provider_name(self) -> str:
        return "glm"

    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ):
        from src.clients.glm_client.client import chat_completion as glm_chat

        return await glm_chat(
            messages=messages,
            refresh_token=api_key,
            model=model,
            stream=stream,
        )


class KimiChannelProvider(BuiltinChannelProvider):
    """Kimi 内置 Provider"""

    @property
    def provider_name(self) -> str:
        return "kimi"

    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ):
        from src.clients.kimi_client.client import chat_completion as kimi_chat

        return await kimi_chat(
            messages=messages,
            refresh_token=api_key,
            model=model,
            stream=stream,
        )


class DeepSeekChannelProvider(BuiltinChannelProvider):
    """DeepSeek 内置 Provider"""

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ):
        from src.clients.deepseek_client.client import chat_completion as deepseek_chat

        return await deepseek_chat(
            messages=messages,
            refresh_token=api_key,
            model=model,
            stream=stream,
        )


class QwenChannelProvider(BuiltinChannelProvider):
    """通义千问内置 Provider"""

    @property
    def provider_name(self) -> str:
        return "qwen"

    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ):
        from src.clients.qwen_client.client import chat_completion as qwen_chat

        return await qwen_chat(
            messages=messages,
            refresh_token=api_key,
            model=model,
            stream=stream,
        )


class MiniMaxChannelProvider(BuiltinChannelProvider):
    """MiniMax 海螺AI内置 Provider"""

    @property
    def provider_name(self) -> str:
        return "minimax"

    async def _call_provider(
        self,
        messages: list,
        model: str,
        stream: bool,
        api_key: str,
    ):
        from src.clients.minimax_client.client import chat_completion as minimax_chat

        return await minimax_chat(
            messages=messages,
            token=api_key,
            model=model,
            stream=stream,
        )
