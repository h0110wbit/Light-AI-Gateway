"""
Qwen Client - 通义千问模型客户端
"""
import json
import re
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dataclasses import dataclass
import httpx

from .utils import (
    generate_uuid,
    get_base_headers,
    generate_cookie,
    unix_timestamp,
    timestamp_ms,
    is_base64_data,
    extract_base64_format,
    remove_base64_header,
    is_url,
    extract_ref_file_urls,
    messages_prepare,
    clean_image_url,
)
from .models import (
    ChatMessage,
    ChatChoice,
    ChatCompletionResponse,
    ChatCompletionChunk,
    UsageInfo,
    FileUploadResult,
    UploadParams,
    ModelInfo,
    SUPPORTED_MODELS,
    DEFAULT_MODEL,
    is_valid_model,
    get_model_list,
)
from .exceptions import (
    APIException,
    RequestFailedException,
    ContentFilteredException,
    FileURLException,
    FileSizeExceededException,
)


@dataclass
class QwenConfig:
    """Qwen 客户端配置"""

    max_retry_count: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 120.0
    file_max_size: int = 100 * 1024 * 1024  # 100MB


# 全局客户端缓存
_client_cache: Dict[str, 'QwenClient'] = {}


def get_cached_client(refresh_token: str, **kwargs) -> 'QwenClient':
    """
    获取缓存的客户端实例

    如果配置没有变化，则复用已有的客户端实例

    Args:
        refresh_token: 刷新令牌
        **kwargs: 其他配置参数

    Returns:
        QwenClient 实例
    """
    # 生成缓存键
    config_key = f"{refresh_token}:{json.dumps(kwargs, sort_keys=True)}"

    # 检查缓存中是否存在
    if config_key in _client_cache:
        return _client_cache[config_key]

    # 创建新客户端并缓存
    client = QwenClient(refresh_token=refresh_token, **kwargs)
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


class QwenClient:
    """
    通义千问模型客户端

    提供与通义千问模型交互的功能，支持同步和流式对话补全。
    """

    MODEL_NAME = "qwen"
    BASE_URL = "https://qianwen.biz.aliyun.com"

    def __init__(
        self,
        ticket: str,
        config: Optional[QwenConfig] = None,
    ):
        """
        初始化 Qwen 客户端

        Args:
            ticket: tongyi_sso_ticket 或 login_aliyunid_ticket
            config: 客户端配置
        """
        self.ticket = ticket
        self.config = config or QwenConfig()

    def _get_headers(self) -> dict:
        """
        获取请求头

        Returns:
            请求头字典
        """
        headers = get_base_headers()
        headers["Cookie"] = generate_cookie(self.ticket)
        return headers

    def _check_response(self, response: httpx.Response) -> dict:
        """
        检查响应结果

        Args:
            response: HTTP 响应

        Returns:
            响应数据

        Raises:
            APIException: 请求失败
        """
        if not response.content:
            raise RequestFailedException("响应为空")

        data = response.json()

        if "success" not in data:
            return data

        success = data.get("success")
        if success:
            return data.get("data", data)

        error_code = data.get("errorCode", "")
        error_msg = data.get("errorMsg", "未知错误")

        raise RequestFailedException(f"请求 Qwen 失败: {error_code}-{error_msg}")

    async def _acquire_upload_params(self) -> UploadParams:
        """
        获取上传参数

        Returns:
            UploadParams 对象
        """
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/dialog/uploadToken",
                headers=headers,
                json={},
            )

        result = self._check_response(response)
        return UploadParams.from_dict(result)

    async def _check_file_url(self, file_url: str) -> None:
        """
        预检查文件 URL 有效性

        Args:
            file_url: 文件 URL

        Raises:
            FileURLException: URL 无效
            FileSizeExceededException: 文件大小超出限制
        """
        if is_base64_data(file_url):
            return

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.head(file_url)

        if response.status_code >= 400:
            raise FileURLException(
                f"File {file_url} is not valid: [{response.status_code}] {response.reason_phrase}"
            )

        # 检查文件大小
        content_length = response.headers.get("content-length")
        if content_length:
            file_size = int(content_length)
            if file_size > self.config.file_max_size:
                raise FileSizeExceededException(
                    f"File {file_url} exceeds size limit")

    async def _upload_file(self, file_url: str) -> FileUploadResult:
        """
        上传文件

        Args:
            file_url: 文件 URL 或 BASE64 数据

        Returns:
            FileUploadResult 对象
        """
        # 预检查远程文件 URL 可用性
        await self._check_file_url(file_url)

        filename = ""
        file_data = b""
        mime_type = ""

        # 如果是 BASE64 数据则直接转换
        if is_base64_data(file_url):
            mime_type = extract_base64_format(file_url)
            ext = self._get_extension_from_mime(mime_type)
            filename = f"{generate_uuid(separator=False)}.{ext}"
            file_data = bytes.fromhex(
                remove_base64_header(file_url).encode().hex())
        else:
            # 下载文件
            from urllib.parse import urlparse
            parsed = urlparse(file_url)
            filename = parsed.path.split(
                "/")[-1] or f"{generate_uuid(separator=False)}.bin"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    file_url,
                    timeout=60.0,
                )
                file_data = response.content

        # 获取 MIME 类型
        if not mime_type:
            mime_type = self._get_mime_type(filename)

        # 获取上传参数
        upload_params = await self._acquire_upload_params()

        # 构建表单数据
        form_data = {
            "OSSAccessKeyId": upload_params.access_id,
            "policy": upload_params.policy,
            "signature": upload_params.signature,
            "key": f"{upload_params.dir}{filename}",
            "dir": upload_params.dir,
            "success_action_status": "200",
            "file": (filename, file_data, mime_type),
        }

        # 上传文件到 OSS
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://broadscope-dialogue-new.oss-cn-beijing.aliyuncs.com/",
                data={
                    k: v
                    for k, v in form_data.items() if k != "file"
                },
                files={"file": form_data["file"]},
            )

        # 判断文件类型
        is_image = mime_type in [
            "image/jpeg", "image/jpg", "image/tiff", "image/png", "image/bmp",
            "image/gif", "image/svg+xml", "image/webp", "image/ico",
            "image/heic", "image/heif", "image/x-icon",
            "image/vnd.microsoft.icon", "image/x-png"
        ]

        if is_image:
            # 获取图片下载链接
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/dialog/downloadLink",
                    headers=self._get_headers(),
                    json={
                        "fileKey": filename,
                        "fileType": "image",
                        "dir": upload_params.dir,
                    },
                )
            result = self._check_response(response)
            return FileUploadResult(
                role="user",
                content_type="image",
                content=result.get("url", ""),
            )
        else:
            # 获取文件下载链接
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/dialog/downloadLink/batch",
                    headers=self._get_headers(),
                    json={
                        "fileKeys": [filename],
                        "fileType": "file",
                        "dir": upload_params.dir,
                    },
                )
            result = self._check_response(response)
            results = result.get("results", [])
            if not results or not results[0].get("url"):
                raise RequestFailedException(
                    f"文件上传失败: {results[0].get('errorMsg', '未知错误') if results else '未知错误'}"
                )

            url = results[0]["url"]

            # 等待文件处理完成
            start_time = timestamp_ms()
            while True:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        f"{self.BASE_URL}/dialog/secResult/batch",
                        headers=self._get_headers(),
                        json={"urls": [url]},
                    )
                result = self._check_response(response)

                if result.get("pollEndFlag"):
                    status_list = result.get("statusList", [])
                    if status_list and status_list[0].get("status") == 0:
                        raise RequestFailedException(
                            f"文件处理失败: {status_list[0].get('errorMsg', '未知错误')}"
                        )
                    break

                if timestamp_ms() > start_time + 120000:
                    raise RequestFailedException("文件处理超时: 超出120秒")

                await asyncio.sleep(1)

            return FileUploadResult(
                role="user",
                content_type="file",
                content=url,
                ext={"fileSize": len(file_data)},
            )

    def _get_extension_from_mime(self, mime_type: str) -> str:
        """
        从 MIME 类型获取扩展名

        Args:
            mime_type: MIME 类型

        Returns:
            文件扩展名
        """
        mime_map = {
            "image/jpeg":
            "jpg",
            "image/jpg":
            "jpg",
            "image/png":
            "png",
            "image/gif":
            "gif",
            "image/webp":
            "webp",
            "image/bmp":
            "bmp",
            "image/svg+xml":
            "svg",
            "application/pdf":
            "pdf",
            "text/plain":
            "txt",
            "text/markdown":
            "md",
            "application/json":
            "json",
            "text/csv":
            "csv",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            "docx",
            "application/msword":
            "doc",
        }
        return mime_map.get(mime_type, "bin")

    def _get_mime_type(self, filename: str) -> str:
        """
        从文件名获取 MIME 类型

        Args:
            filename: 文件名

        Returns:
            MIME 类型
        """
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        ext_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
            "svg": "image/svg+xml",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "md": "text/markdown",
            "json": "application/json",
            "csv": "text/csv",
            "docx":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
        }
        return ext_map.get(ext, "application/octet-stream")

    async def _remove_conversation(self, conv_id: str) -> None:
        """
        移除会话

        在对话流传输完毕后移除会话，避免创建的会话出现在用户的对话列表中

        Args:
            conv_id: 会话ID
        """
        if not conv_id or not isinstance(conv_id, str):
            return

        # 提取 sessionId
        session_id = conv_id.split("-")[0] if "-" in conv_id else conv_id
        if not session_id:
            return

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self.BASE_URL}/dialog/session/delete",
                    headers=self._get_headers(),
                    json={"sessionId": session_id},
                )
        except Exception:
            # 忽略删除会话的错误
            pass

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str = DEFAULT_MODEL,
        search_type: str = "",
        ref_conv_id: str = "",
        stream: bool = False,
    ) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk,
                                                      None]]:
        """
        对话补全

        Args:
            messages: 消息列表，参考 GPT 系列消息格式
            model: 模型名称
            search_type: 搜索类型
            ref_conv_id: 引用的会话ID
            stream: 是否使用流式响应

        Returns:
            如果 stream=False，返回 ChatCompletionResponse
            如果 stream=True，返回 AsyncGenerator[ChatCompletionChunk, None]
        """
        if stream:
            return self._chat_completion_stream(
                messages=messages,
                model=model,
                search_type=search_type,
                ref_conv_id=ref_conv_id,
            )
        else:
            return await self._chat_completion_sync(
                messages=messages,
                model=model,
                search_type=search_type,
                ref_conv_id=ref_conv_id,
            )

    async def _chat_completion_sync(
        self,
        messages: List[Dict[str, Any]],
        model: str = DEFAULT_MODEL,
        search_type: str = "",
        ref_conv_id: str = "",
        retry_count: int = 0,
    ) -> ChatCompletionResponse:
        """
        同步对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            search_type: 搜索类型
            ref_conv_id: 引用的会话ID
            retry_count: 重试次数

        Returns:
            ChatCompletionResponse 对象
        """
        # 验证模型
        if not is_valid_model(model):
            model = DEFAULT_MODEL

        try:
            # 提取引用文件 URL 并上传
            ref_file_urls = extract_ref_file_urls(messages)
            refs = []
            if ref_file_urls:
                for file_url in ref_file_urls:
                    upload_result = await self._upload_file(file_url)
                    refs.append(upload_result.to_dict())

            # 检查引用对话ID格式
            if not re.match(r"[0-9a-z]{32}", ref_conv_id):
                ref_conv_id = ""

            session_id, parent_msg_id = "", ""
            if ref_conv_id and "-" in ref_conv_id:
                parts = ref_conv_id.split("-")
                session_id = parts[0]
                parent_msg_id = parts[1] if len(parts) > 1 else ""

            # 准备请求数据
            request_data = {
                "mode": "chat",
                "model": model,
                "action": "next",
                "userAction": "chat",
                "requestId": generate_uuid(separator=False),
                "sessionId": session_id,
                "sessionType": "text_chat",
                "parentMsgId": parent_msg_id,
                "params": {
                    "fileUploadBatchId": generate_uuid(),
                    "searchType": search_type,
                },
                "contents": messages_prepare(messages, refs,
                                             bool(ref_conv_id)),
            }

            # 发送请求
            headers = self._get_headers()
            headers["Accept"] = "text/event-stream"

            async with httpx.AsyncClient(
                    timeout=self.config.request_timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}/dialog/conversation",
                    headers=headers,
                    json=request_data,
                )

            # 解析 SSE 响应
            result = await self._parse_sse_response(response)

            # 异步移除会话
            asyncio.create_task(self._remove_conversation(result.get("id",
                                                                     "")))

            return self._build_response(result, model)

        except Exception as e:
            if retry_count < self.config.max_retry_count:
                await asyncio.sleep(self.config.retry_delay)
                return await self._chat_completion_sync(
                    messages=messages,
                    model=model,
                    search_type=search_type,
                    ref_conv_id=ref_conv_id,
                    retry_count=retry_count + 1,
                )
            raise

    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str = DEFAULT_MODEL,
        search_type: str = "",
        ref_conv_id: str = "",
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        流式对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            search_type: 搜索类型
            ref_conv_id: 引用的会话ID

        Yields:
            ChatCompletionChunk 对象
        """
        # 验证模型
        if not is_valid_model(model):
            model = DEFAULT_MODEL

        retry_count = 0
        while retry_count <= self.config.max_retry_count:
            try:
                # 提取引用文件 URL 并上传
                ref_file_urls = extract_ref_file_urls(messages)
                refs = []
                if ref_file_urls:
                    for file_url in ref_file_urls:
                        upload_result = await self._upload_file(file_url)
                        refs.append(upload_result.to_dict())

                # 检查引用对话ID格式
                if not re.match(r"[0-9a-z]{32}", ref_conv_id):
                    ref_conv_id = ""

                session_id, parent_msg_id = "", ""
                if ref_conv_id and "-" in ref_conv_id:
                    parts = ref_conv_id.split("-")
                    session_id = parts[0]
                    parent_msg_id = parts[1] if len(parts) > 1 else ""

                # 准备请求数据
                request_data = {
                    "mode":
                    "chat",
                    "model":
                    model,
                    "action":
                    "next",
                    "userAction":
                    "chat",
                    "requestId":
                    generate_uuid(separator=False),
                    "sessionId":
                    session_id,
                    "sessionType":
                    "text_chat",
                    "parentMsgId":
                    parent_msg_id,
                    "params": {
                        "fileUploadBatchId": generate_uuid(),
                        "searchType": search_type,
                    },
                    "contents":
                    messages_prepare(messages, refs, bool(ref_conv_id)),
                }

                # 发送请求
                headers = self._get_headers()
                headers["Accept"] = "text/event-stream"

                async with httpx.AsyncClient(
                        timeout=self.config.request_timeout) as client:
                    async with client.stream(
                            "POST",
                            f"{self.BASE_URL}/dialog/conversation",
                            headers=headers,
                            json=request_data,
                    ) as response:
                        conv_id = ""
                        async for chunk in self._parse_sse_stream(
                                response, model):
                            if chunk.id:
                                conv_id = chunk.id
                            yield chunk

                        # 异步移除会话
                        if conv_id:
                            asyncio.create_task(
                                self._remove_conversation(conv_id))

                return

            except Exception as e:
                retry_count += 1
                if retry_count > self.config.max_retry_count:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def _parse_sse_response(self, response: httpx.Response) -> dict:
        """
        解析 SSE 响应

        Args:
            response: HTTP 响应

        Returns:
            解析后的数据
        """
        text = response.text
        lines = text.strip().split("\n")

        result_data = {
            "id": "",
            "content": "",
            "can_share": True,
            "error_code": "",
        }

        last_content = ""

        for line in lines:
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)
                    if data.get("sessionId") and data.get("msgId"):
                        result_data[
                            "id"] = f"{data['sessionId']}-{data['msgId']}"

                    contents = data.get("contents", [])
                    # 只取最后一条 assistant 消息的内容
                    current_content = ""
                    for part in contents:
                        content_type = part.get("contentType", "")
                        role = part.get("role", "")
                        content = part.get("content", "")

                        if content_type in ["text", "text2image"
                                            ] and role == "assistant":
                            current_content = content  # 直接赋值，不累积

                    # 更新内容（覆盖，不累积）
                    if current_content:
                        result_data["content"] = current_content
                        last_content = current_content

                    if data.get("msgStatus") == "finished":
                        result_data["can_share"] = data.get("canShare", True)
                        result_data["error_code"] = data.get("errorCode", "")

                except json.JSONDecodeError:
                    continue

        return result_data

    async def _parse_sse_stream(
        self,
        response: httpx.Response,
        model: str,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        解析 SSE 流

        Args:
            response: HTTP 响应
            model: 模型名称

        Yields:
            ChatCompletionChunk 对象
        """
        created = unix_timestamp()
        content_buffer = ""
        conv_id = ""
        last_text = ""

        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if data.get("sessionId") and data.get("msgId"):
                conv_id = f"{data['sessionId']}-{data['msgId']}"

            contents = data.get("contents", [])
            # 找到 assistant 角色的最后一条文本消息
            current_text = ""
            for part in contents:
                content_type = part.get("contentType", "")
                role = part.get("role", "")
                content = part.get("content", "")

                if content_type in ["text", "text2image"] and isinstance(
                        content, str):
                    if role == "assistant":
                        current_text = content  # 只取最后一条 assistant 消息

            # 清理图片 URL
            if data.get("contentType") == "text2image":
                current_text = re.sub(
                    r"https?://[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=\,]*)",
                    lambda m: clean_image_url(m.group(0)),
                    current_text,
                )

            # 检查是否有无效字符
            has_invalid_char = "�" in current_text

            # 提取增量内容 - 只返回新增的部分
            chunk_text = ""
            if len(current_text) > len(last_text):
                chunk_text = current_text[len(last_text):]
                last_text = current_text

            # 如果存在无效字符，跳过此次输出
            if has_invalid_char and not chunk_text.replace("�", ""):
                continue

            if data.get("msgStatus") != "finished":
                if chunk_text and data.get("contentType") == "text":
                    yield ChatCompletionChunk(
                        id=conv_id,
                        model=model,
                        choices=[
                            ChatChoice(
                                index=0,
                                delta={"content": chunk_text},
                                finish_reason=None,
                            )
                        ],
                        created=created,
                    )
            else:
                # 最后一条消息
                delta_content = chunk_text or ""
                if not data.get("canShare", True):
                    delta_content += "\n[内容由于不合规被停止生成，我们换个话题吧]"
                if data.get("errorCode"):
                    delta_content += f"服务暂时不可用，第三方响应错误：{data['errorCode']}"

                yield ChatCompletionChunk(
                    id=conv_id,
                    model=model,
                    choices=[
                        ChatChoice(
                            index=0,
                            delta={"content": delta_content},
                            finish_reason="stop",
                        )
                    ],
                    created=created,
                )

    def _build_response(self, result: dict,
                        model: str) -> ChatCompletionResponse:
        """
        构建响应对象

        Args:
            result: 解析后的结果
            model: 模型名称

        Returns:
            ChatCompletionResponse 对象
        """
        content = result.get("content", "")

        if not result.get("can_share", True):
            content += "\n[内容由于不合规被停止生成，我们换个话题吧]"
        if result.get("error_code"):
            content += f"服务暂时不可用，第三方响应错误：{result['error_code']}"

        return ChatCompletionResponse(
            id=result.get("id", ""),
            model=model,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content,
                    ),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            ),
            created=unix_timestamp(),
        )

    async def generate_images(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
    ) -> List[str]:
        """
        生成图像

        Args:
            prompt: 图像生成提示词
            model: 模型名称

        Returns:
            图像 URL 列表
        """
        if not is_valid_model(model):
            model = DEFAULT_MODEL

        messages = [
            {
                "role": "user",
                "content": prompt if "画" in prompt else f"请画：{prompt}"
            },
        ]

        retry_count = 0
        while retry_count <= self.config.max_retry_count:
            try:
                request_data = {
                    "mode": "chat",
                    "model": model,
                    "action": "next",
                    "userAction": "chat",
                    "requestId": generate_uuid(separator=False),
                    "sessionId": "",
                    "sessionType": "text_chat",
                    "parentMsgId": "",
                    "params": {
                        "fileUploadBatchId": generate_uuid(),
                    },
                    "contents": messages_prepare(messages),
                }

                headers = self._get_headers()
                headers["Accept"] = "text/event-stream"

                async with httpx.AsyncClient(
                        timeout=self.config.request_timeout) as client:
                    response = await client.post(
                        f"{self.BASE_URL}/dialog/conversation",
                        headers=headers,
                        json=request_data,
                    )

                conv_id, image_urls = await self._parse_image_response(response
                                                                       )

                # 异步移除会话
                asyncio.create_task(self._remove_conversation(conv_id))

                return image_urls

            except Exception as e:
                retry_count += 1
                if retry_count > self.config.max_retry_count:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def _parse_image_response(self, response: httpx.Response) -> tuple:
        """
        解析图像生成响应

        Args:
            response: HTTP 响应

        Returns:
            (conv_id, image_urls) 元组
        """
        text = response.text
        lines = text.strip().split("\n")

        conv_id = ""
        image_urls = []

        for line in lines:
            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if data.get("sessionId") and not conv_id:
                conv_id = data["sessionId"]

            if data.get("contentFrom") == "text2image":
                contents = data.get("contents", [])
                for part in contents:
                    content = part.get("content", "")
                    if isinstance(content, str):
                        urls = re.findall(
                            r"https?://[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=\,]*)",
                            content,
                        )
                        for url in urls:
                            full_url = f"https{url}" if url.startswith(
                                "://") else url
                            cleaned = clean_image_url(full_url)
                            if cleaned not in image_urls:
                                image_urls.append(cleaned)

            if data.get("msgStatus") == "finished":
                if not data.get("canShare", True) or not image_urls:
                    raise ContentFilteredException()
                if data.get("errorCode"):
                    raise RequestFailedException(
                        f"服务暂时不可用，第三方响应错误：{data['errorCode']}")

        return conv_id, image_urls

    async def check_token_live(self) -> bool:
        """
        检查 Token 是否有效

        Returns:
            Token 是否有效
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/dialog/session/list",
                    headers=self._get_headers(),
                    json={},
                )
            result = self._check_response(response)
            return isinstance(result, list)
        except Exception:
            return False

    def get_supported_models(self) -> List[ModelInfo]:
        """
        获取支持的模型列表

        Returns:
            模型信息列表
        """
        return get_model_list()


# 便捷函数
async def chat_completion(
    ticket: str,
    messages: List[Dict[str, Any]],
    model: str = DEFAULT_MODEL,
    search_type: str = "",
    ref_conv_id: str = "",
    stream: bool = False,
    config: Optional[QwenConfig] = None,
) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk, None]]:
    """
    便捷的对话补全函数

    Args:
        ticket: tongyi_sso_ticket 或 login_aliyunid_ticket
        messages: 消息列表
        model: 模型名称
        search_type: 搜索类型
        ref_conv_id: 引用的会话ID
        stream: 是否使用流式响应
        config: 客户端配置

    Returns:
        对话补全响应
    """
    client = get_cached_client(refresh_token=ticket, config=config)
    return await client.chat_completion(
        messages=messages,
        model=model,
        search_type=search_type,
        ref_conv_id=ref_conv_id,
        stream=stream,
    )


async def generate_images(
    ticket: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    config: Optional[QwenConfig] = None,
) -> List[str]:
    """
    便捷的图像生成函数

    Args:
        ticket: tongyi_sso_ticket 或 login_aliyunid_ticket
        prompt: 图像生成提示词
        model: 模型名称
        config: 客户端配置

    Returns:
        图像 URL 列表
    """
    client = get_cached_client(refresh_token=ticket, config=config)
    return await client.generate_images(prompt=prompt, model=model)


async def check_token_live(ticket: str) -> bool:
    """
    便捷的 Token 检查函数

    Args:
        ticket: tongyi_sso_ticket 或 login_aliyunid_ticket

    Returns:
        Token 是否有效
    """
    client = get_cached_client(refresh_token=ticket)
    return await client.check_token_live()
