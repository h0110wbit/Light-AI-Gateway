"""
DeepSeek Free API Client
DeepSeek 模型的 Python 客户端实现
"""
from .client import (
    DeepSeekClient,
    chat_completion,
    get_cached_client,
    clear_client_cache,
    remove_client_from_cache,
)
from .exceptions import (
    DeepSeekException,
    APIException,
    TokenExpiredException,
    RequestFailedException,
    ThinkingQuotaException,
)
from .models import (
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionChunk,
)

__all__ = [
    "DeepSeekClient",
    "chat_completion",
    "get_cached_client",
    "clear_client_cache",
    "remove_client_from_cache",
    "DeepSeekException",
    "APIException",
    "TokenExpiredException",
    "RequestFailedException",
    "ThinkingQuotaException",
    "ChatMessage",
    "ChatCompletionResponse",
    "ChatCompletionChunk",
]

__version__ = "1.0.0"
