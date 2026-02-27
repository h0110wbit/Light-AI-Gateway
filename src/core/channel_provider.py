"""
Channel Provider 抽象基类
所有 channel 类型（HTTP 和内置）都需要实现这个接口
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Union


class ChannelProvider(ABC):
    """
    Channel Provider 抽象基类
    所有 channel 类型（HTTP 和内置）都需要实现这个接口
    """

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Channel 类型标识，如 'http:openai', 'builtin:glm'"""
        pass

    @abstractmethod
    async def chat_completion(
            self,
            request: dict,
            api_key: str,
            source_format: str = "openai",
            **kwargs) -> Union[dict, AsyncGenerator[dict, None]]:
        """
        统一的对话补全接口

        Args:
            request: 请求体字典，包含 messages, model, stream, temperature 等
            api_key: API 密钥
            source_format: 请求的原始格式 (openai, anthropic, gemini)
            **kwargs: 额外的 provider 特定参数

        Returns:
            非流式：原始格式的响应字典
            流式：AsyncGenerator[原始格式的响应字典, None]
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """检查 channel 是否可用"""
        pass
