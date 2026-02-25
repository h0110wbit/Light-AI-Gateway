"""
MiniMax Free API Client
MiniMax 海螺 AI 模型的 Python 客户端实现
"""
from .client import (
    MiniMaxClient,
    chat_completion,
    delete_chat,
    get_cached_client,
    clear_client_cache,
    remove_client_from_cache,
    MiniMaxConfig,
)
from .exceptions import (
    MiniMaxException,
    APIException,
    TokenExpiredException,
    RequestFailedException,
    FileURLException,
    FileSizeExceededException,
)
from .models import (
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionChunk,
    FileUploadResult,
    DeviceInfo,
)

__all__ = [
    "MiniMaxClient",
    "chat_completion",
    "delete_chat",
    "get_cached_client",
    "clear_client_cache",
    "remove_client_from_cache",
    "MiniMaxConfig",
    "MiniMaxException",
    "APIException",
    "TokenExpiredException",
    "RequestFailedException",
    "FileURLException",
    "FileSizeExceededException",
    "ChatMessage",
    "ChatCompletionResponse",
    "ChatCompletionChunk",
    "FileUploadResult",
    "DeviceInfo",
]

__version__ = "1.0.0"
