"""
GLM Client - 智谱 GLM 模型客户端
"""
import json
import re
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator, Union, Callable
from dataclasses import dataclass
import httpx

from .utils import (
    generate_uuid,
    generate_sign,
    get_base_headers,
    unix_timestamp,
    is_base64_data,
    extract_base64_format,
    remove_base64_header,
)
from .models import (
    ChatMessage,
    ChatChoice,
    ChatCompletionResponse,
    ChatCompletionChunk,
    UsageInfo,
    TokenInfo,
    FileUploadResult,
)
from .exceptions import (
    APIException,
    TokenExpiredException,
    RequestFailedException,
    ContentFilteredException,
    FileURLException,
    FileSizeExceededException,
)


@dataclass
class GLMConfig:
    """GLM 客户端配置"""

    sign_secret: str = "8a1317a7468aa3ad86e997d08f3f31cb"
    default_assistant_id: str = "65940acff94777010aa6b796"
    access_token_expires: int = 3600
    max_retry_count: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 120.0
    file_max_size: int = 100 * 1024 * 1024


# 全局客户端缓存
_client_cache: Dict[str, 'GLMClient'] = {}


def get_cached_client(refresh_token: str, **kwargs) -> 'GLMClient':
    """
    获取缓存的客户端实例

    如果配置没有变化，则复用已有的客户端实例

    Args:
        refresh_token: 刷新令牌
        **kwargs: 其他配置参数

    Returns:
        GLMClient 实例
    """
    # 生成缓存键
    config_key = f"{refresh_token}:{json.dumps(kwargs, sort_keys=True)}"

    # 检查缓存中是否存在
    if config_key in _client_cache:
        return _client_cache[config_key]

    # 创建新客户端并缓存
    client = GLMClient(refresh_token=refresh_token, **kwargs)
    _client_cache[config_key] = client
    return client


def clear_client_cache() -> None:
    """
    清除客户端缓存

    当需要强制重新创建客户端时调用
    """
    global _client_cache
    _client_cache.clear()


def remove_client_from_cache(refresh_token: str, **kwargs) -> None:
    """
    从缓存中移除指定客户端

    Args:
        refresh_token: 刷新令牌
        **kwargs: 其他配置参数
    """
    config_key = f"{refresh_token}:{json.dumps(kwargs, sort_keys=True)}"
    _client_cache.pop(config_key, None)


class GLMClient:
    """
    智谱 GLM 模型客户端

    提供与智谱 GLM 模型交互的功能，支持同步和流式对话补全。
    """

    MODEL_NAME = "glm"
    BASE_URL = "https://chatglm.cn"

    def __init__(
        self,
        refresh_token: str,
        config: Optional[GLMConfig] = None,
    ):
        """
        初始化 GLM 客户端

        Args:
            refresh_token: 用于刷新 access_token 的 refresh_token
            config: 客户端配置
        """
        self.refresh_token = refresh_token
        self.config = config or GLMConfig()
        self._token_cache: Dict[str, TokenInfo] = {}
        self._token_request_queues: Dict[str, List[Callable]] = {}

    def _get_headers(self,
                     with_auth: bool = False,
                     token: Optional[str] = None) -> dict:
        """
        获取请求头

        Args:
            with_auth: 是否包含认证头
            token: access_token

        Returns:
            请求头字典
        """
        headers = get_base_headers()
        if with_auth and token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _request_token(self, refresh_token: str) -> TokenInfo:
        """
        请求 access_token

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            TokenInfo 对象
        """
        sign = generate_sign(self.config.sign_secret)
        headers = self._get_headers()
        headers.update({
            "Authorization": f"Bearer {refresh_token}",
            "X-Device-Id": generate_uuid(separator=False),
            "X-Nonce": sign["nonce"],
            "X-Request-Id": generate_uuid(separator=False),
            "X-Sign": sign["sign"],
            "X-Timestamp": sign["timestamp"],
        })

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chatglm/user-api/user/refresh",
                headers=headers,
                json={},
            )

        result = self._check_response(response, refresh_token)
        return TokenInfo(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            refresh_time=unix_timestamp() + self.config.access_token_expires,
        )

    async def _acquire_token(self, refresh_token: str) -> str:
        """
        获取有效的 access_token

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            access_token
        """
        token_info = self._token_cache.get(refresh_token)

        if not token_info:
            token_info = await self._request_token(refresh_token)
            self._token_cache[refresh_token] = token_info

        if unix_timestamp() > token_info.refresh_time:
            token_info = await self._request_token(refresh_token)
            self._token_cache[refresh_token] = token_info

        return token_info.access_token

    def _check_response(self, response: httpx.Response,
                        refresh_token: str) -> dict:
        """
        检查响应结果

        Args:
            response: HTTP 响应
            refresh_token: 用于清理缓存的 refresh_token

        Returns:
            响应数据

        Raises:
            APIException: 请求失败
        """
        if not response.content:
            raise RequestFailedException("响应为空")

        data = response.json()

        if "code" not in data and "status" not in data:
            return data

        code = data.get("code")
        status = data.get("status")
        message = data.get("message", "未知错误")

        if code == 0 or status == 0:
            return data.get("result", data)

        if code == 401:
            self._token_cache.pop(refresh_token, None)

        if "40102" in message:
            raise TokenExpiredException("您的 refresh_token 已过期，请重新登录获取")

        raise RequestFailedException(f"请求 GLM 失败: {message}")

    def _prepare_messages(self,
                          messages: List[Dict[str, Any]],
                          refs: List[Any] = None,
                          is_ref_conv: bool = False) -> List[Dict[str, Any]]:
        """
        预处理消息

        将多条消息合并为一条，实现多轮对话效果

        Args:
            messages: 消息列表
            refs: 参考文件列表
            is_ref_conv: 是否为引用会话

        Returns:
            处理后的消息列表
        """
        refs = refs or []
        content = ""

        if is_ref_conv or len(messages) < 2:
            for message in messages:
                msg_content = message.get("content", "")
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item,
                                      dict) and item.get("type") == "text":
                            content += item.get("text", "") + "\n"
                else:
                    content += f"{msg_content}\n"
        else:
            latest_message = messages[-1]
            has_file_or_image = False

            if isinstance(latest_message.get("content"), list):
                for item in latest_message["content"]:
                    if isinstance(item, dict) and item.get("type") in [
                            "file", "image_url"
                    ]:
                        has_file_or_image = True
                        break

            if has_file_or_image:
                messages = messages.copy()
                messages.insert(
                    -1,
                    {
                        "content": "关注用户最新发送文件和消息",
                        "role": "system"
                    },
                )

            for message in messages:
                role = message.get("role", "user")
                role_prefix = {
                    "system": "<|sytstem|>",
                    "assistant": "</s>",
                    "user": "user",
                }.get(role, role)

                msg_content = message.get("content", "")
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item,
                                      dict) and item.get("type") == "text":
                            content += f"{role_prefix}\n{item.get('text', '')}\n"
                else:
                    content += f"{role_prefix}\n{msg_content}\n"

            content += "</s>\n"

        content = re.sub(r"!\[.+\]\(.+\)", "", content)
        content = re.sub(r"/mnt/data/.+", "", content)

        file_refs = [
            r for r in refs if not r.get("width") and not r.get("height")
        ]
        image_refs = [{
            **r, "image_url": r.get("file_url")
        } for r in refs if r.get("width") or r.get("height")]

        result_content = [{"type": "text", "text": content}]

        if file_refs:
            result_content.append({"type": "file", "file": file_refs})

        if image_refs:
            result_content.append({"type": "image", "image": image_refs})

        return [{"role": "user", "content": result_content}]

    def _extract_file_urls(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        从消息中提取文件 URL

        Args:
            messages: 消息列表

        Returns:
            文件 URL 列表
        """
        urls = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "image_url" and isinstance(
                                item.get("image_url"), dict):
                            url = item["image_url"].get("url", "")
                            if url:
                                urls.append(url)
        return urls

    async def _check_file_url(self, file_url: str) -> None:
        """
        检查文件 URL 有效性

        Args:
            file_url: 文件 URL

        Raises:
            FileURLException: 文件 URL 无效
            FileSizeExceededException: 文件大小超出限制
        """
        if is_base64_data(file_url):
            return

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.head(file_url)

        if response.status_code >= 400:
            raise FileURLException(
                f"文件 {file_url} 无效: [{response.status_code}]")

        content_length = response.headers.get("content-length")
        if content_length:
            file_size = int(content_length)
            if file_size > self.config.file_max_size:
                raise FileSizeExceededException(f"文件 {file_url} 超出大小限制")

    async def upload_file(self,
                          file_url: str,
                          is_video_image: bool = False) -> FileUploadResult:
        """
        上传文件

        Args:
            file_url: 文件 URL 或 BASE64 数据
            is_video_image: 是否为视频图像

        Returns:
            FileUploadResult 对象
        """
        await self._check_file_url(file_url)

        token = await self._acquire_token(self.refresh_token)
        sign = generate_sign(self.config.sign_secret)

        if is_base64_data(file_url):
            import base64
            import mimetypes

            mime_type = extract_base64_format(
                file_url) or "application/octet-stream"
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            filename = f"{generate_uuid(separator=False)}{ext}"
            file_data = base64.b64decode(remove_base64_header(file_url))
        else:
            import os

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(file_url)
                file_data = response.content

            filename = os.path.basename(file_url) or generate_uuid(
                separator=False)

        files = {"file": (filename, file_data)}
        headers = self._get_headers(with_auth=True, token=token)
        headers.update({
            "X-Device-Id": generate_uuid(separator=False),
            "X-Request-Id": generate_uuid(separator=False),
            "X-Sign": sign["sign"],
            "X-Timestamp": sign["timestamp"],
            "X-Nonce": sign["nonce"],
        })
        del headers["Content-Type"]

        upload_url = (
            f"{self.BASE_URL}/chatglm/video-api/v1/static/upload"
            if is_video_image else
            f"{self.BASE_URL}/chatglm/backend-api/assistant/file_upload")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(upload_url,
                                         headers=headers,
                                         files=files)

        result = self._check_response(response, self.refresh_token)

        return FileUploadResult(
            file_id=result.get("file_id"),
            file_url=result.get("file_url"),
            width=result.get("width"),
            height=result.get("height"),
            source_id=result.get("source_id"),
        )

    async def _remove_conversation(self,
                                   conv_id: str,
                                   assistant_id: Optional[str] = None) -> None:
        """
        移除会话

        Args:
            conv_id: 会话 ID
            assistant_id: 智能体 ID
        """
        if not conv_id:
            return

        assistant_id = assistant_id or self.config.default_assistant_id
        token = await self._acquire_token(self.refresh_token)
        sign = generate_sign(self.config.sign_secret)

        headers = self._get_headers(with_auth=True, token=token)
        headers.update({
            "Referer": f"{self.BASE_URL}/main/alltoolsdetail",
            "X-Device-Id": generate_uuid(separator=False),
            "X-Request-Id": generate_uuid(separator=False),
            "X-Sign": sign["sign"],
            "X-Timestamp": sign["timestamp"],
            "X-Nonce": sign["nonce"],
        })

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self.BASE_URL}/chatglm/backend-api/assistant/conversation/delete",
                    headers=headers,
                    json={
                        "assistant_id": assistant_id,
                        "conversation_id": conv_id,
                    },
                )
        except Exception:
            pass

    def _parse_stream_response(
        self,
        model: str,
        is_silent: bool = False
    ) -> Callable[[bytes], Optional[ChatCompletionChunk]]:
        """
        创建流式响应解析器

        Args:
            model: 模型名称
            is_silent: 是否为静默模型

        Returns:
            解析函数
        """
        cached_parts: List[Dict[str, Any]] = []
        sent_content = ""
        sent_reasoning = ""
        conv_id = ""

        def parse_chunk(data: bytes) -> Optional[ChatCompletionChunk]:
            nonlocal cached_parts, sent_content, sent_reasoning, conv_id

            text = data.decode("utf-8", errors="ignore")
            for line in text.split("\n"):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue

                json_str = line[6:]
                if json_str == "[DONE]":
                    return None

                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                if result.get("conversation_id"):
                    conv_id = result["conversation_id"]

                if result.get("status") in ["finish", "intervene"]:
                    return None

                if result.get("parts"):
                    for part in result["parts"]:
                        existing_idx = next(
                            (i for i, p in enumerate(cached_parts)
                             if p.get("logic_id") == part.get("logic_id")),
                            None,
                        )
                        if existing_idx is not None:
                            cached_parts[existing_idx] = part
                        else:
                            cached_parts.append(part)

                search_map: Dict[str, Any] = {}
                for part in cached_parts:
                    meta_data = part.get("meta_data", {})
                    for item in part.get("content", []):
                        if item.get("type") == "tool_result":
                            search_results = meta_data.get(
                                "tool_result_extra",
                                {}).get("search_results", [])
                            for res in search_results:
                                if res.get("match_key"):
                                    search_map[res["match_key"]] = res

                key_to_id_map: Dict[str, int] = {}
                counter = 1
                full_text = ""
                full_reasoning = ""

                for part in cached_parts:
                    content = part.get("content", [])
                    if not isinstance(content, list):
                        continue

                    meta_data = part.get("meta_data", {})
                    part_text = ""
                    part_reasoning = ""

                    for value in content:
                        value_type = value.get("type")

                        if value_type == "text":
                            txt = value.get("text", "")
                            if search_map:
                                txt = re.sub(
                                    r"【?(turn\d+[a-zA-Z]+\d+)】?",
                                    lambda m: self._replace_search_ref(
                                        m, search_map, key_to_id_map, counter),
                                    txt,
                                )
                            part_text += txt
                        elif value_type == "think" and not is_silent:
                            part_reasoning += value.get("think", "")
                        elif value_type == "tool_result" and not is_silent:
                            search_results = meta_data.get(
                                "tool_result_extra",
                                {}).get("search_results", [])
                            for res in search_results:
                                part_reasoning += f"> 检索 {res.get('title', '')}({res.get('url', '')}) ...\n"
                        elif value_type == "image" and part.get(
                                "status") == "finish":
                            for img in value.get("image", []):
                                img_url = img.get("image_url", "")
                                if img_url.startswith(("http://", "https://")):
                                    part_text += f"![图像]({img_url})"
                            part_text += "\n"
                        elif value_type == "code":
                            code = value.get("code", "")
                            part_text += f"```python\n{code}"
                            if part.get("status") == "finish":
                                part_text += "\n```\n"
                        elif (value_type == "execution_output"
                              and part.get("status") == "finish"):
                            part_text += value.get("content", "") + "\n"

                    if part_text:
                        full_text += ("\n" if full_text else "") + part_text
                    if part_reasoning:
                        full_reasoning += ("\n" if full_reasoning else
                                           "") + part_reasoning

                new_content = full_text[len(sent_content):] if len(
                    full_text) > len(sent_content) else ""
                new_reasoning = full_reasoning[len(sent_reasoning):] if len(
                    full_reasoning) > len(sent_reasoning) else ""

                sent_content = full_text
                sent_reasoning = full_reasoning

                if new_content or new_reasoning:
                    delta = {}
                    if new_content:
                        delta["content"] = new_content
                    if new_reasoning:
                        delta["reasoning_content"] = new_reasoning

                    return ChatCompletionChunk(
                        id=conv_id,
                        model=model,
                        choices=[
                            ChatChoice(
                                index=0,
                                delta=delta,
                                finish_reason=None,
                            )
                        ],
                        created=unix_timestamp(),
                    )

            return None

        return parse_chunk

    def _replace_search_ref(
        self,
        match: re.Match,
        search_map: Dict[str, Any],
        key_to_id_map: Dict[str, int],
        counter: int,
    ) -> str:
        """
        替换搜索引用

        Args:
            match: 正则匹配对象
            search_map: 搜索结果映射
            key_to_id_map: 键到 ID 的映射
            counter: 计数器

        Returns:
            替换后的字符串
        """
        key = match.group(1)
        search_info = search_map.get(key)
        if not search_info:
            return match.group(0)

        if key not in key_to_id_map:
            key_to_id_map[key] = counter
            counter += 1

        new_id = key_to_id_map[key]
        return f" [{new_id}]({search_info.get('url', '')})"

    async def create_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        chat_mode: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """
        创建对话补全（非流式）

        Args:
            messages: 消息列表
            model: 模型名称或智能体 ID
            conversation_id: 会话 ID（用于继续对话）
            chat_mode: 聊天模式（如 'zero' 用于推理模型）

        Returns:
            ChatCompletionResponse 对象
        """
        retry_count = 0

        while retry_count < self.config.max_retry_count:
            try:
                file_urls = self._extract_file_urls(messages)
                refs = []
                if file_urls:
                    refs = await asyncio.gather(
                        *[self.upload_file(url) for url in file_urls])

                if conversation_id and not re.match(r"[0-9a-zA-Z]{24}",
                                                    conversation_id):
                    conversation_id = ""

                assistant_id = (model if model
                                and re.match(r"^[a-z0-9]{24,}$", model) else
                                self.config.default_assistant_id)

                if not chat_mode:
                    if model and ("think" in model or "zero" in model):
                        chat_mode = "zero"
                    elif model and "deepresearch" in model:
                        chat_mode = "deep_research"

                token = await self._acquire_token(self.refresh_token)
                sign = generate_sign(self.config.sign_secret)

                headers = self._get_headers(with_auth=True, token=token)
                headers.update({
                    "X-Device-Id": generate_uuid(separator=False),
                    "X-Request-Id": generate_uuid(separator=False),
                    "X-Sign": sign["sign"],
                    "X-Timestamp": sign["timestamp"],
                    "X-Nonce": sign["nonce"],
                })

                request_body = {
                    "assistant_id":
                    assistant_id,
                    "conversation_id":
                    conversation_id or "",
                    "project_id":
                    "",
                    "chat_type":
                    "user_chat",
                    "messages":
                    self._prepare_messages(messages, refs,
                                           bool(conversation_id)),
                    "meta_data": {
                        "channel": "",
                        "chat_mode": chat_mode,
                        "draft_id": "",
                        "if_plus_model": True,
                        "input_question_type": "xxxx",
                        "is_networking": True,
                        "is_test": False,
                        "platform": "pc",
                        "quote_log_id": "",
                        "cogview": {
                            "rm_label_watermark": False
                        },
                    },
                }

                async with httpx.AsyncClient(
                        timeout=self.config.request_timeout) as client:
                    async with client.stream(
                            "POST",
                            f"{self.BASE_URL}/chatglm/backend-api/assistant/stream",
                            headers=headers,
                            json=request_body,
                    ) as response:
                        content_type = response.headers.get("content-type", "")
                        if "text/event-stream" not in content_type:
                            error_text = await response.aread()
                            raise RequestFailedException(
                                f"响应类型无效: {content_type}, {error_text.decode()}"
                            )

                        result = await self._receive_stream(
                            response, model or self.MODEL_NAME)

                        if not conversation_id:
                            asyncio.create_task(
                                self._remove_conversation(
                                    result.id, assistant_id))

                        return result

            except (APIException, httpx.HTTPError) as e:
                retry_count += 1
                if retry_count >= self.config.max_retry_count:
                    raise
                await asyncio.sleep(self.config.retry_delay)

        raise RequestFailedException("达到最大重试次数")

    async def _receive_stream(self, response: httpx.Response,
                              model: str) -> ChatCompletionResponse:
        """
        接收流式响应并组装完整结果

        Args:
            response: HTTP 流式响应
            model: 模型名称

        Returns:
            ChatCompletionResponse 对象
        """
        is_silent = "silent" in model if model else False

        data = ChatCompletionResponse(
            id="",
            model=model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant",
                                        content="",
                                        reasoning_content=None),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(prompt_tokens=1,
                            completion_tokens=1,
                            total_tokens=2),
            created=unix_timestamp(),
        )

        cached_parts: List[Dict[str, Any]] = []
        buffer = ""

        async for chunk in response.aiter_bytes():
            buffer += chunk.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()

                if not line or not line.startswith("data: "):
                    continue

                json_str = line[6:]
                if json_str == "[DONE]":
                    break

                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                if result.get("conversation_id"):
                    data.id = result["conversation_id"]

                if result.get("status") == "finish":
                    break

                if result.get("parts"):
                    cached_parts = result["parts"]

                search_map: Dict[str, Any] = {}
                for part in cached_parts:
                    meta_data = part.get("meta_data", {})
                    for item in part.get("content", []):
                        if item.get("type") == "tool_result":
                            search_results = meta_data.get(
                                "tool_result_extra",
                                {}).get("search_results", [])
                            for res in search_results:
                                if res.get("match_key"):
                                    search_map[res["match_key"]] = res

                key_to_id_map: Dict[str, int] = {}
                counter = 1
                full_text = ""
                full_reasoning = ""

                for part in cached_parts:
                    content = part.get("content", [])
                    if not isinstance(content, list):
                        continue

                    meta_data = part.get("meta_data", {})
                    part_text = ""
                    part_reasoning = ""

                    for value in content:
                        value_type = value.get("type")

                        if value_type == "text":
                            txt = value.get("text", "")
                            if search_map:
                                txt = re.sub(
                                    r"【?(turn\d+[a-zA-Z]+\d+)】?",
                                    lambda m: self._replace_search_ref(
                                        m, search_map, key_to_id_map, counter),
                                    txt,
                                )
                            part_text += txt
                        elif value_type == "think" and not is_silent:
                            part_reasoning += value.get("think", "")
                        elif value_type == "tool_result" and not is_silent:
                            search_results = meta_data.get(
                                "tool_result_extra",
                                {}).get("search_results", [])
                            for res in search_results:
                                part_reasoning += f"> 检索 {res.get('title', '')}({res.get('url', '')}) ...\n"
                        elif value_type == "image" and part.get(
                                "status") == "finish":
                            for img in value.get("image", []):
                                img_url = img.get("image_url", "")
                                if img_url.startswith(("http://", "https://")):
                                    part_text += f"![图像]({img_url})"
                            part_text += "\n"
                        elif value_type == "code":
                            code = value.get("code", "")
                            part_text += f"```python\n{code}"
                            if part.get("status") == "finish":
                                part_text += "\n```\n"
                        elif (value_type == "execution_output"
                              and part.get("status") == "finish"):
                            part_text += value.get("content", "") + "\n"

                    if part_text:
                        full_text += ("\n" if full_text else "") + part_text
                    if part_reasoning:
                        full_reasoning += ("\n" if full_reasoning else
                                           "") + part_reasoning

                if data.choices and data.choices[0].message:
                    data.choices[0].message.content = full_text
                    data.choices[
                        0].message.reasoning_content = full_reasoning or None

        data.choices[0].message.content = re.sub(
            r"【\d+†(来源|源|source)】", "", data.choices[0].message.content)

        return data

    async def create_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        chat_mode: Optional[str] = None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        创建对话补全（流式）

        Args:
            messages: 消息列表
            model: 模型名称或智能体 ID
            conversation_id: 会话 ID（用于继续对话）
            chat_mode: 聊天模式

        Yields:
            ChatCompletionChunk 对象
        """
        retry_count = 0

        while retry_count < self.config.max_retry_count:
            try:
                file_urls = self._extract_file_urls(messages)
                refs = []
                if file_urls:
                    refs = await asyncio.gather(
                        *[self.upload_file(url) for url in file_urls])

                if conversation_id and not re.match(r"[0-9a-zA-Z]{24}",
                                                    conversation_id):
                    conversation_id = ""

                assistant_id = (model if model
                                and re.match(r"^[a-z0-9]{24,}$", model) else
                                self.config.default_assistant_id)

                if not chat_mode:
                    if model and ("think" in model or "zero" in model):
                        chat_mode = "zero"
                    elif model and "deepresearch" in model:
                        chat_mode = "deep_research"

                token = await self._acquire_token(self.refresh_token)
                sign = generate_sign(self.config.sign_secret)

                headers = self._get_headers(with_auth=True, token=token)
                headers.update({
                    "X-Device-Id": generate_uuid(separator=False),
                    "X-Request-Id": generate_uuid(separator=False),
                    "X-Sign": sign["sign"],
                    "X-Timestamp": sign["timestamp"],
                    "X-Nonce": sign["nonce"],
                })

                request_body = {
                    "assistant_id":
                    assistant_id,
                    "conversation_id":
                    conversation_id or "",
                    "project_id":
                    "",
                    "chat_type":
                    "user_chat",
                    "messages":
                    self._prepare_messages(messages, refs,
                                           bool(conversation_id)),
                    "meta_data": {
                        "channel": "",
                        "chat_mode": chat_mode,
                        "draft_id": "",
                        "if_plus_model": True,
                        "input_question_type": "xxxx",
                        "is_networking": True,
                        "is_test": False,
                        "platform": "pc",
                        "quote_log_id": "",
                        "cogview": {
                            "rm_label_watermark": False
                        },
                    },
                }

                async with httpx.AsyncClient(
                        timeout=self.config.request_timeout) as client:
                    async with client.stream(
                            "POST",
                            f"{self.BASE_URL}/chatglm/backend-api/assistant/stream",
                            headers=headers,
                            json=request_body,
                    ) as response:
                        content_type = response.headers.get("content-type", "")
                        if "text/event-stream" not in content_type:
                            error_text = await response.aread()
                            raise RequestFailedException(
                                f"响应类型无效: {content_type}")

                        is_silent = "silent" in model if model else False
                        cached_parts: List[Dict[str, Any]] = []
                        sent_content = ""
                        sent_reasoning = ""
                        conv_id = ""
                        buffer = ""
                        counter = 1
                        key_to_id_map: Dict[str, int] = {}

                        yield ChatCompletionChunk(
                            id="",
                            model=model or self.MODEL_NAME,
                            choices=[
                                ChatChoice(
                                    index=0,
                                    delta={
                                        "role": "assistant",
                                        "content": ""
                                    },
                                    finish_reason=None,
                                )
                            ],
                            created=unix_timestamp(),
                        )

                        async for chunk in response.aiter_bytes():
                            buffer += chunk.decode("utf-8", errors="ignore")

                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                line = line.strip()

                                if not line or not line.startswith("data: "):
                                    continue

                                json_str = line[6:]
                                if json_str == "[DONE]":
                                    return

                                try:
                                    result = json.loads(json_str)
                                except json.JSONDecodeError:
                                    continue

                                if result.get("conversation_id"):
                                    conv_id = result["conversation_id"]

                                if result.get("status") in [
                                        "finish", "intervene"
                                ]:
                                    yield ChatCompletionChunk(
                                        id=conv_id,
                                        model=model or self.MODEL_NAME,
                                        choices=[
                                            ChatChoice(
                                                index=0,
                                                delta={},
                                                finish_reason="stop",
                                            )
                                        ],
                                        created=unix_timestamp(),
                                    )

                                    if not conversation_id:
                                        asyncio.create_task(
                                            self._remove_conversation(
                                                conv_id, assistant_id))
                                    return

                                if result.get("parts"):
                                    for part in result["parts"]:
                                        existing_idx = next(
                                            (i for i, p in enumerate(
                                                cached_parts)
                                             if p.get("logic_id") == part.get(
                                                 "logic_id")),
                                            None,
                                        )
                                        if existing_idx is not None:
                                            cached_parts[existing_idx] = part
                                        else:
                                            cached_parts.append(part)

                                search_map: Dict[str, Any] = {}
                                for part in cached_parts:
                                    meta_data = part.get("meta_data", {})
                                    for item in part.get("content", []):
                                        if item.get("type") == "tool_result":
                                            search_results = meta_data.get(
                                                "tool_result_extra",
                                                {}).get("search_results", [])
                                            for res in search_results:
                                                if res.get("match_key"):
                                                    search_map[
                                                        res["match_key"]] = res

                                full_text = ""
                                full_reasoning = ""

                                for part in cached_parts:
                                    content = part.get("content", [])
                                    if not isinstance(content, list):
                                        continue

                                    meta_data = part.get("meta_data", {})
                                    part_text = ""
                                    part_reasoning = ""

                                    for value in content:
                                        value_type = value.get("type")

                                        if value_type == "text":
                                            txt = value.get("text", "")
                                            if search_map:
                                                txt = re.sub(
                                                    r"【?(turn\d+[a-zA-Z]+\d+)】?",
                                                    lambda m: self.
                                                    _replace_search_ref(
                                                        m, search_map,
                                                        key_to_id_map, counter
                                                    ),
                                                    txt,
                                                )
                                            part_text += txt
                                        elif value_type == "think" and not is_silent:
                                            part_reasoning += value.get(
                                                "think", "")
                                        elif value_type == "tool_result" and not is_silent:
                                            search_results = meta_data.get(
                                                "tool_result_extra",
                                                {}).get("search_results", [])
                                            for res in search_results:
                                                part_reasoning += f"> 检索 {res.get('title', '')}({res.get('url', '')}) ...\n"
                                        elif (value_type == "image" and
                                              part.get("status") == "finish"):
                                            for img in value.get("image", []):
                                                img_url = img.get(
                                                    "image_url", "")
                                                if img_url.startswith(
                                                    ("http://", "https://")):
                                                    part_text += f"![图像]({img_url})"
                                            part_text += "\n"
                                        elif value_type == "code":
                                            code = value.get("code", "")
                                            part_text += f"```python\n{code}"
                                            if part.get("status") == "finish":
                                                part_text += "\n```\n"
                                        elif (value_type == "execution_output"
                                              and part.get("status")
                                              == "finish"):
                                            part_text += value.get(
                                                "content", "") + "\n"

                                    if part_text:
                                        full_text += ("\n" if full_text else
                                                      "") + part_text
                                    if part_reasoning:
                                        full_reasoning += (
                                            ("\n" if full_reasoning else "") +
                                            part_reasoning)

                                new_content = (full_text[len(sent_content):]
                                               if len(full_text)
                                               > len(sent_content) else "")
                                new_reasoning = (
                                    full_reasoning[len(sent_reasoning):]
                                    if len(full_reasoning)
                                    > len(sent_reasoning) else "")

                                sent_content = full_text
                                sent_reasoning = full_reasoning

                                if new_content or new_reasoning:
                                    delta = {}
                                    if new_content:
                                        delta["content"] = new_content
                                    if new_reasoning:
                                        delta[
                                            "reasoning_content"] = new_reasoning

                                    yield ChatCompletionChunk(
                                        id=conv_id,
                                        model=model or self.MODEL_NAME,
                                        choices=[
                                            ChatChoice(
                                                index=0,
                                                delta=delta,
                                                finish_reason=None,
                                            )
                                        ],
                                        created=unix_timestamp(),
                                    )

                        return

            except (APIException, httpx.HTTPError) as e:
                retry_count += 1
                if retry_count >= self.config.max_retry_count:
                    raise
                await asyncio.sleep(self.config.retry_delay)

        raise RequestFailedException("达到最大重试次数")


async def chat_completion(
    messages: List[Dict[str, Any]],
    refresh_token: str,
    model: Optional[str] = None,
    conversation_id: Optional[str] = None,
    stream: bool = False,
    **kwargs,
) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk, None]]:
    """
    便捷函数：创建对话补全

    Args:
        messages: 消息列表
        refresh_token: 刷新令牌
        model: 模型名称
        conversation_id: 会话 ID
        stream: 是否使用流式输出
        **kwargs: 其他参数传递给 GLMClient

    Returns:
        ChatCompletionResponse 或 AsyncGenerator

    Example:
        # 非流式调用
        response = await chat_completion(
            messages=[{"role": "user", "content": "你好"}],
            refresh_token="your_refresh_token",
        )
        print(response.get_content())

        # 流式调用
        async for chunk in await chat_completion(
            messages=[{"role": "user", "content": "你好"}],
            refresh_token="your_refresh_token",
            stream=True,
        ):
            if chunk.choices and chunk.choices[0].delta:
                print(chunk.choices[0].delta.get("content", ""), end="")
    """
    client = get_cached_client(refresh_token=refresh_token, **kwargs)

    if stream:

        async def stream_generator():
            async for chunk in client.create_completion_stream(
                    messages=messages,
                    model=model,
                    conversation_id=conversation_id,
            ):
                yield chunk

        return stream_generator()
    else:
        return await client.create_completion(
            messages=messages,
            model=model,
            conversation_id=conversation_id,
        )
