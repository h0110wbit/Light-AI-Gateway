"""
Qwen Free API Client
通义千问模型的 Python 客户端实现

基于 Qwen-Free-API 项目重写，提供简洁的函数调用接口。

使用示例:
    ```python
    import asyncio
    from src.clients.qwen_client import QwenClient, chat_completion

    # 方式1: 使用客户端类
    async def example1():
        client = QwenClient(ticket="your_ticket_here")

        # 同步对话
        response = await client.chat_completion(
            messages=[{"role": "user", "content": "你好"}]
        )
        print(response.get_content())

        # 流式对话
        async for chunk in await client.chat_completion(
            messages=[{"role": "user", "content": "你好"}],
            stream=True
        ):
            print(chunk.choices[0].delta.get("content", ""), end="")

    # 方式2: 使用便捷函数
    async def example2():
        response = await chat_completion(
            ticket="your_ticket_here",
            messages=[{"role": "user", "content": "你好"}]
        )
        print(response.get_content())

    asyncio.run(example1())
    ```
"""
from .client import (
    QwenClient,
    chat_completion,
    generate_images,
    check_token_live,
    get_cached_client,
    clear_client_cache,
    remove_client_from_cache,
)
from .exceptions import (
    QwenException,
    APIException,
    TokenExpiredException,
    RequestFailedException,
    ContentFilteredException,
    FileURLException,
    FileSizeExceededException,
)
from .models import (
    ChatMessage,
    ChatCompletionResponse,
    ChatCompletionChunk,
    ModelInfo,
    SUPPORTED_MODELS,
    DEFAULT_MODEL,
    is_valid_model,
    get_model_list,
)
from .utils import (
    generate_uuid,
    unix_timestamp,
    timestamp_ms,
)

__all__ = [
    # 客户端类
    "QwenClient",
    # 便捷函数
    "chat_completion",
    "generate_images",
    "check_token_live",
    # 缓存管理函数
    "get_cached_client",
    "clear_client_cache",
    "remove_client_from_cache",
    # 异常类
    "QwenException",
    "APIException",
    "TokenExpiredException",
    "RequestFailedException",
    "ContentFilteredException",
    "FileURLException",
    "FileSizeExceededException",
    # 数据模型
    "ChatMessage",
    "ChatCompletionResponse",
    "ChatCompletionChunk",
    "ModelInfo",
    # 常量
    "SUPPORTED_MODELS",
    "DEFAULT_MODEL",
    # 工具函数
    "is_valid_model",
    "get_model_list",
    "generate_uuid",
    "unix_timestamp",
    "timestamp_ms",
]

__version__ = "1.0.0"
