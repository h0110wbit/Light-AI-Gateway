"""
MiniMax Client - MiniMax 模型客户端
MiniMax 海螺 AI 模型的 Python 客户端实现
"""
import json
import re
import asyncio
import time
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dataclasses import dataclass, field
import httpx
import base64

from .utils import (
    generate_uuid,
    get_base_headers,
    unix_timestamp,
    timestamp_ms,
    md5_hash,
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
    DeviceInfo,
    FileUploadResult,
)
from .exceptions import (
    APIException,
    TokenExpiredException,
    RequestFailedException,
    FileURLException,
    FileSizeExceededException,
)


@dataclass
class MiniMaxConfig:
    """MiniMax 客户端配置"""

    device_info_expires: int = 10800  # 设备信息有效期（秒）
    max_retry_count: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 120.0
    poll_interval: float = 1.0  # 轮询间隔（秒）
    max_poll_count: int = 60  # 最大轮询次数
    file_max_size: int = 100 * 1024 * 1024  # 100MB


# 伪装用户数据
FAKE_USER_DATA = {
    "device_platform": "web",
    "biz_id": "3",
    "app_id": "3001",
    "version_code": "22201",
    "uuid": None,
    "device_id": None,
    "os_name": "Mac",
    "browser_name": "chrome",
    "device_memory": 8,
    "cpu_core_num": 11,
    "browser_language": "zh-CN",
    "browser_platform": "MacIntel",
    "user_id": None,
    "screen_width": 1920,
    "screen_height": 1080,
    "unix": None,
    "lang": "zh",
    "token": None,
}

# 全局客户端缓存
_client_cache: Dict[str, 'MiniMaxClient'] = {}


def get_cached_client(token: str, **kwargs) -> 'MiniMaxClient':
    """
    获取缓存的客户端实例

    如果配置没有变化，则复用已有的客户端实例

    Args:
        token: 认证 token
        **kwargs: 其他配置参数

    Returns:
        MiniMaxClient 实例
    """
    config_key = f"{token}:{json.dumps(kwargs, sort_keys=True)}"

    if config_key in _client_cache:
        return _client_cache[config_key]

    client = MiniMaxClient(token=token, **kwargs)
    _client_cache[config_key] = client
    return client


def clear_client_cache() -> None:
    """
    清除客户端缓存

    当需要强制重新创建客户端时调用
    """
    global _client_cache
    _client_cache.clear()


def remove_client_from_cache(token: str, **kwargs) -> None:
    """
    从缓存中移除指定客户端

    Args:
        token: 认证 token
        **kwargs: 其他配置参数
    """
    config_key = f"{token}:{json.dumps(kwargs, sort_keys=True)}"
    _client_cache.pop(config_key, None)


class MiniMaxClient:
    """
    MiniMax 模型客户端

    提供与 MiniMax 海螺 AI 模型交互的功能，支持同步和流式对话补全。
    """

    MODEL_NAME = "hailuo"
    BASE_URL = "https://agent.minimaxi.com"

    def __init__(
        self,
        token: str,
        config: Optional[MiniMaxConfig] = None,
    ):
        """
        初始化 MiniMax 客户端

        Args:
            token: 认证 token，格式为 "realUserID+JWTtoken" 或直接 JWT token
            config: 客户端配置
        """
        self.token = token
        self.config = config or MiniMaxConfig()
        self._device_info_cache: Optional[Dict[str, Any]] = None
        self._device_info_lock = asyncio.Lock()

    def _parse_token(self) -> Dict[str, Any]:
        """
        解析 token 格式

        Returns:
            包含 realUserID, jwtToken, deviceInfo 的字典
        """
        token = self.token
        real_user_id = ""
        jwt_token = token

        # 检查是否是 realUserID+JWTtoken 格式
        plus_index = token.find('+')
        if plus_index != -1:
            real_user_id = token[:plus_index]
            jwt_token = token[plus_index + 1:]

        # 验证JWT token格式并提取信息
        jwt_parts = jwt_token.split('.')
        jwt_user_id = ""
        device_id = ""

        if len(jwt_parts) == 3:
            try:
                # 解码 JWT payload
                payload_padding = 4 - len(jwt_parts[1]) % 4
                if payload_padding != 4:
                    jwt_payload_b64 = jwt_parts[1] + '=' * payload_padding
                else:
                    jwt_payload_b64 = jwt_parts[1]

                payload = json.loads(
                    base64.b64decode(jwt_payload_b64).decode('utf-8'))
                jwt_user_id = payload.get('user', {}).get('id', '')
                device_id = payload.get('user', {}).get('deviceID', '')
            except Exception:
                pass

        # 如果没有 real_user_id，使用 jwt_user_id
        if not real_user_id and jwt_user_id:
            real_user_id = jwt_user_id

        # 如果都没有，使用默认值
        if not real_user_id:
            real_user_id = '450394515982692354'
        if not device_id:
            device_id = str(int(time.time() * 1000) % 100000000)

        device_info = {
            "userId": jwt_user_id or real_user_id,
            "realUserID": real_user_id,
            "deviceId": device_id,
            "refreshTime": unix_timestamp() + self.config.device_info_expires,
        }

        return {
            "realUserID": real_user_id,
            "jwtToken": jwt_token,
            "deviceInfo": device_info,
        }

    def _get_headers(self,
                     with_auth: bool = False,
                     token: Optional[str] = None) -> dict:
        """
        获取请求头

        Args:
            with_auth: 是否包含认证头
            token: 认证 token

        Returns:
            请求头字典
        """
        headers = get_base_headers()
        if with_auth and token:
            headers["token"] = token
        return headers

    async def _request_device_info(self) -> Dict[str, Any]:
        """
        请求设备信息

        Returns:
            设备信息字典
        """
        import urllib.parse

        parsed = self._parse_token()
        real_user_id = parsed["realUserID"]
        jwt_token = parsed["jwtToken"]

        unix = str(timestamp_ms())
        user_data = FAKE_USER_DATA.copy()
        user_data["uuid"] = real_user_id
        user_data["user_id"] = real_user_id
        user_data["unix"] = unix
        user_data["token"] = jwt_token

        # 构建查询字符串
        query_params = []
        for key, value in user_data.items():
            if value is not None:
                query_params.append(f"{key}={value}")
        query_str = "&".join(query_params)

        uri = f"/v1/api/user/device/register?{query_str}"
        data = {"uuid": real_user_id}
        data_json = json.dumps(data)

        # 生成 yy 签名 - 使用 encodeURIComponent 编码
        encoded_uri = urllib.parse.quote(uri, safe='')
        yy = md5_hash(f"{encoded_uri}_{data_json}{md5_hash(unix)}ooui")

        # 生成 x-signature
        timestamp = str(int(time.time()))
        signature = md5_hash(f"{timestamp}{jwt_token}{data_json}")

        headers = self._get_headers(with_auth=True, token=jwt_token)
        headers.update({
            "yy": yy,
            "x-timestamp": timestamp,
            "x-signature": signature,
            "Referer": "https://agent.minimaxi.com/",
        })

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}{uri}",
                headers=headers,
                json=data,
            )

        result = self._check_response(response)
        device_id = result.get("deviceIDStr", "")

        return {
            "userId": parsed["deviceInfo"]["userId"],
            "realUserID": real_user_id,
            "deviceId": device_id,
            "refreshTime": unix_timestamp() + self.config.device_info_expires,
        }

    async def _acquire_device_info(self) -> Dict[str, Any]:
        """
        获取有效的设备信息

        Returns:
            设备信息字典
        """
        async with self._device_info_lock:
            if self._device_info_cache is None:
                self._device_info_cache = await self._request_device_info()

            if unix_timestamp() > self._device_info_cache["refreshTime"]:
                self._device_info_cache = await self._request_device_info()

            return self._device_info_cache

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
        # 检查 HTTP 状态码
        if response.status_code != 200:
            raise RequestFailedException(
                f"HTTP 请求失败: {response.status_code}, 响应: {response.text[:200]}"
            )

        if not response.content:
            raise RequestFailedException("响应为空")

        # 尝试解析 JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise RequestFailedException(
                f"JSON 解析失败: {e}, 响应内容: {response.text[:200]}")

        # 检查 statusInfo 格式的错误
        if "statusInfo" in data:
            status_info = data["statusInfo"]
            code = status_info.get("code", 0)
            message = status_info.get("message", "未知错误")
            if code != 0:
                raise RequestFailedException(f"请求 MiniMax 失败: {message}")
            return data.get("data", {})

        # 检查 base_resp 格式的错误（Agent API）
        if "base_resp" in data:
            base_resp = data["base_resp"]
            status_code = base_resp.get("status_code", 0)
            status_msg = base_resp.get("status_msg", "未知错误")
            if status_code != 0:
                raise RequestFailedException(f"请求 MiniMax 失败: {status_msg}")
            return data

        return data

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

    async def upload_file(self, file_url: str) -> FileUploadResult:
        """
        上传文件

        Args:
            file_url: 文件 URL 或 BASE64 数据

        Returns:
            FileUploadResult 对象
        """
        await self._check_file_url(file_url)

        parsed = self._parse_token()
        jwt_token = parsed["jwtToken"]
        device_info = await self._acquire_device_info()

        # 获取文件上传策略
        policy_result = await self._request(
            "GET",
            "/v1/api/files/request_policy",
            {},
            jwt_token,
            device_info,
        )

        policy_data = self._check_response(policy_result)
        access_key_id = policy_data.get("accessKeyId")
        access_key_secret = policy_data.get("accessKeySecret")
        bucket_name = policy_data.get("bucketName")
        dir_path = policy_data.get("dir")
        endpoint = policy_data.get("endpoint")
        security_token = policy_data.get("securityToken")

        # 准备文件数据
        if is_base64_data(file_url):
            import mimetypes

            mime_type = extract_base64_format(
                file_url) or "application/octet-stream"
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            filename = f"{generate_uuid(separator=False)}{ext}"
            file_data = base64.b64decode(remove_base64_header(file_url))
        else:
            import os.path
            import mimetypes

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(file_url)
                file_data = response.content

            filename = os.path.basename(file_url) or generate_uuid(
                separator=False)
            mime_type = mimetypes.guess_type(
                filename)[0] or "application/octet-stream"

        # 使用 oss2 上传文件到阿里云 OSS
        try:
            import oss2

            auth = oss2.StsAuth(access_key_id, access_key_secret,
                                security_token)
            bucket = oss2.Bucket(auth, endpoint, bucket_name)
            object_key = f"{dir_path}/{filename}"
            bucket.put_object(object_key, file_data)
        except ImportError:
            # 如果没有 oss2，使用简单的 HTTP 上传
            raise RequestFailedException("需要安装 oss2 库来上传文件: pip install oss2")

        # 上传回调
        callback_result = await self._request(
            "POST",
            "/v1/api/files/policy_callback",
            {
                "fileName": filename,
                "originFileName": filename,
                "dir": dir_path,
                "endpoint": endpoint,
                "bucketName": bucket_name,
                "size": str(len(file_data)),
                "mimeType": mime_type,
            },
            jwt_token,
            device_info,
        )

        callback_data = self._check_response(callback_result)
        file_id = callback_data.get("fileID", "")

        # 判断文件类型
        is_image = mime_type in [
            "image/jpeg",
            "image/jpg",
            "image/tiff",
            "image/png",
            "image/bmp",
            "image/gif",
            "image/svg+xml",
            "image/webp",
            "image/ico",
            "image/heic",
            "image/heif",
            "image/x-icon",
            "image/vnd.microsoft.icon",
            "image/x-png",
        ]

        return FileUploadResult(
            file_type=2 if is_image else 6,
            filename=filename,
            file_id=file_id,
        )

    async def _request(
        self,
        method: str,
        uri: str,
        data: Any,
        token: str,
        device_info: Dict[str, Any],
    ) -> httpx.Response:
        """
        发起请求

        Args:
            method: 请求方法
            uri: 请求 URI
            data: 请求数据
            token: 认证 token
            device_info: 设备信息

        Returns:
            HTTP 响应
        """
        import urllib.parse

        unix = str(timestamp_ms())
        timestamp = str(int(time.time()))

        user_data = FAKE_USER_DATA.copy()
        # 使用 realUserID 作为 uuid 和 user_id
        real_user_id = device_info.get("realUserID") or device_info.get(
            "userId", "")
        user_data["uuid"] = real_user_id
        user_data["device_id"] = device_info.get("deviceId") or None
        user_data["user_id"] = real_user_id
        user_data["unix"] = unix
        user_data["token"] = token

        # 构建查询字符串
        query_params = []
        for key, value in user_data.items():
            if value is not None:
                query_params.append(f"{key}={value}")
        query_str = "&".join(query_params)

        data_json = json.dumps(data) if data else "{}"
        separator = "&" if "?" in uri else "?"
        full_uri = f"{uri}{separator}{query_str}"

        # 生成 yy 签名 - 使用 encodeURIComponent 编码
        encoded_full_uri = urllib.parse.quote(full_uri, safe='')
        yy = md5_hash(f"{encoded_full_uri}_{data_json}{md5_hash(unix)}ooui")

        # 生成 x-signature
        signature = md5_hash(f"{timestamp}{token}{data_json}")

        headers = self._get_headers(with_auth=True, token=token)
        headers.update({
            "yy": yy,
            "x-timestamp": timestamp,
            "x-signature": signature,
            "Referer": "https://agent.minimaxi.com/",
        })

        async with httpx.AsyncClient(
                timeout=self.config.request_timeout) as client:
            if method.upper() == "GET":
                response = await client.get(
                    f"{self.BASE_URL}{full_uri}",
                    headers=headers,
                )
            else:
                response = await client.post(
                    f"{self.BASE_URL}{full_uri}",
                    headers=headers,
                    json=data,
                )

        return response

    def _prepare_messages(
        self,
        messages: List[Dict[str, Any]],
        refs: List[FileUploadResult] = None,
    ) -> Dict[str, Any]:
        """
        预处理消息 - Agent API 格式

        Args:
            messages: 消息列表
            refs: 参考文件列表

        Returns:
            处理后的消息数据
        """
        refs = refs or []

        # 构建消息内容
        if len(messages) < 2:
            # 单条消息，直接透传内容
            content = ""
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
            # 多轮对话，合并消息
            content_parts = []
            for message in messages:
                role = message.get("role", "user")
                msg_content = message.get("content", "")

                if isinstance(msg_content, list):
                    text_parts = []
                    for item in msg_content:
                        if isinstance(item,
                                      dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    content_parts.append(f"{role}:{''.join(text_parts)}")
                else:
                    content_parts.append(f"{role}:{msg_content}")

            content = "\n".join(content_parts) + "\nassistant:"
            # 移除图片标记
            content = re.sub(r"!\[.+\]\(.+\)", "", content)

        # 构建附件列表
        attachments = []
        for ref in refs:
            attachments.append({
                "file_type": ref.file_type,
                "file_id": ref.file_id,
                "file_name": ref.filename,
            })

        return {
            "msg_type": 1,
            "text": content.strip(),
            "chat_type": 1,
            "attachments": attachments,
            "selected_mcp_tools": [],
            "backend_config": {},
            "sub_agent_ids": [],
        }

    def _extract_file_urls(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        从消息中提取文件 URL

        Args:
            messages: 消息列表

        Returns:
            文件 URL 列表
        """
        urls = []
        if not messages:
            return urls

        # 只获取最新消息中的文件
        last_message = messages[-1]
        content = last_message.get("content", "")

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "file" and isinstance(
                            item.get("file_url"), dict):
                        url = item["file_url"].get("url", "")
                        if url:
                            urls.append(url)
                    elif item.get("type") == "image_url" and isinstance(
                            item.get("image_url"), dict):
                        url = item["image_url"].get("url", "")
                        if url:
                            urls.append(url)

        return urls

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str = "hailuo",
        stream: bool = False,
    ) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk,
                                                      None]]:
        """
        对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            stream: 是否使用流式输出

        Returns:
            如果 stream=False，返回 ChatCompletionResponse
            如果 stream=True，返回 AsyncGenerator[ChatCompletionChunk, None]
        """
        if stream:
            return self._chat_completion_stream(messages, model)
        return await self._chat_completion_sync(messages, model)

    async def _chat_completion_sync(
        self,
        messages: List[Dict[str, Any]],
        model: str = "hailuo",
    ) -> ChatCompletionResponse:
        """
        同步对话补全

        Args:
            messages: 消息列表
            model: 模型名称

        Returns:
            ChatCompletionResponse 对象
        """
        parsed = self._parse_token()
        jwt_token = parsed["jwtToken"]
        device_info = await self._acquire_device_info()

        # 提取并上传文件
        file_urls = self._extract_file_urls(messages)
        refs = []
        if file_urls:
            refs = await asyncio.gather(
                *[self.upload_file(url) for url in file_urls])

        # 发送消息
        msg_data = self._prepare_messages(messages, refs)
        send_result = await self._request(
            "POST",
            "/matrix/api/v1/chat/send_msg",
            msg_data,
            jwt_token,
            device_info,
        )

        # 检查 HTTP 状态码
        if send_result.status_code != 200:
            raise RequestFailedException(
                f"HTTP 请求失败: {send_result.status_code}")

        send_data = self._check_response(send_result)
        chat_id = send_data.get("chat_id")
        base_resp = send_data.get("base_resp", {})

        if base_resp.get("status_code") != 0:
            raise RequestFailedException(
                f"发送消息失败: {base_resp.get('status_msg', '未知错误')}")

        if not chat_id:
            raise RequestFailedException("发送消息失败：未获取到 chat_id")

        # 确保 chat_id 是整数类型
        if isinstance(chat_id, str):
            chat_id = int(chat_id)

        # 轮询获取 AI 回复
        poll_count = 0
        ai_message = None

        while poll_count < self.config.max_poll_count:
            await asyncio.sleep(self.config.poll_interval)
            poll_count += 1

            detail_result = await self._request(
                "POST",
                "/matrix/api/v1/chat/get_chat_detail",
                {"chat_id": chat_id},
                jwt_token,
                device_info,
            )

            detail_data = self._check_response(detail_result)
            base_resp = detail_data.get("base_resp", {})

            if base_resp.get("status_code") != 0:
                continue

            chat_messages = detail_data.get("messages", [])

            # 查找 AI 回复（msg_type === 2）
            for msg in chat_messages:
                if msg.get("msg_type") == 2:
                    ai_message = msg
                    break

            if ai_message:
                break

        if not ai_message:
            # 删除会话
            await self.delete_chat(chat_id)
            raise RequestFailedException(f"未获取到 AI 回复，轮询 {poll_count} 次后超时")

        created = unix_timestamp()
        content = ai_message.get("msg_content", "")

        # 删除会话
        await self.delete_chat(chat_id)

        return ChatCompletionResponse(
            id=str(chat_id),
            model=model,
            object="chat.completion",
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
            usage=UsageInfo(prompt_tokens=1,
                            completion_tokens=1,
                            total_tokens=2),
            created=created,
        )

    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str = "hailuo",
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        流式对话补全（带自动删除会话）

        Args:
            messages: 消息列表
            model: 模型名称

        Yields:
            ChatCompletionChunk 对象
        """
        parsed = self._parse_token()
        jwt_token = parsed["jwtToken"]
        device_info = await self._acquire_device_info()

        # 提取并上传文件
        file_urls = self._extract_file_urls(messages)
        refs = []
        if file_urls:
            refs = await asyncio.gather(
                *[self.upload_file(url) for url in file_urls])

        created = unix_timestamp()
        chat_id = ""

        # 发送初始 chunk
        yield ChatCompletionChunk(
            id=chat_id,
            model=model,
            object="chat.completion.chunk",
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
            created=created,
        )

        # 发送消息
        msg_data = self._prepare_messages(messages, refs)
        send_result = await self._request(
            "POST",
            "/matrix/api/v1/chat/send_msg",
            msg_data,
            jwt_token,
            device_info,
        )

        # 检查 HTTP 状态码
        if send_result.status_code != 200:
            raise RequestFailedException(
                f"HTTP 请求失败: {send_result.status_code}")

        send_data = self._check_response(send_result)
        base_resp = send_data.get("base_resp", {})

        if base_resp.get("status_code") != 0:
            raise RequestFailedException(
                f"发送消息失败: {base_resp.get('status_msg', '未知错误')}")

        chat_id = send_data.get("chat_id")

        if not chat_id:
            raise RequestFailedException("发送消息失败：未获取到 chat_id")

        # 确保 chat_id 是整数类型
        if isinstance(chat_id, str):
            chat_id = int(chat_id)

        try:
            # 轮询获取 AI 回复
            poll_count = 0
            last_content = ""

            while poll_count < self.config.max_poll_count:
                await asyncio.sleep(self.config.poll_interval)
                poll_count += 1

                detail_result = await self._request(
                    "POST",
                    "/matrix/api/v1/chat/get_chat_detail",
                    {"chat_id": chat_id},
                    jwt_token,
                    device_info,
                )

                detail_data = self._check_response(detail_result)
                base_resp = detail_data.get("base_resp", {})

                if base_resp.get("status_code") != 0:
                    continue

                chat_messages = detail_data.get("messages", [])

                # 查找 AI 回复
                ai_message = None
                for msg in chat_messages:
                    if msg.get("msg_type") == 2:
                        ai_message = msg
                        break

                if ai_message:
                    current_content = ai_message.get("msg_content", "")

                    # 发送新增的内容
                    if len(current_content) > len(last_content):
                        new_chunk = current_content[len(last_content):]
                        yield ChatCompletionChunk(
                            id=chat_id,
                            model=model,
                            object="chat.completion.chunk",
                            choices=[
                                ChatChoice(
                                    index=0,
                                    delta={"content": new_chunk},
                                    finish_reason=None,
                                )
                            ],
                            created=created,
                        )
                        last_content = current_content

                    # 检查是否完成（内容不再增长且轮询超过3次）
                    if poll_count > 3 and current_content == last_content and current_content:
                        yield ChatCompletionChunk(
                            id=chat_id,
                            model=model,
                            object="chat.completion.chunk",
                            choices=[
                                ChatChoice(
                                    index=0,
                                    delta={"content": ""},
                                    finish_reason="stop",
                                )
                            ],
                            created=created,
                        )
                        return

            # 超时结束
            yield ChatCompletionChunk(
                id=chat_id,
                model=model,
                object="chat.completion.chunk",
                choices=[
                    ChatChoice(
                        index=0,
                        delta={"content": ""},
                        finish_reason="stop",
                    )
                ],
                created=created,
            )
        finally:
            # 确保会话被删除
            try:
                await self.delete_chat(chat_id)
            except Exception:
                pass  # 忽略删除失败

    async def delete_chat(self, chat_id: Union[int, str]) -> bool:
        """
        删除会话

        Args:
            chat_id: 会话 ID

        Returns:
            是否删除成功
        """
        parsed = self._parse_token()
        jwt_token = parsed["jwtToken"]
        device_info = await self._acquire_device_info()

        # 确保 chat_id 是整数类型
        if isinstance(chat_id, str):
            chat_id = int(chat_id)

        result = await self._request(
            "POST",
            "/matrix/api/v1/chat/delete_chat",
            {"chat_id": chat_id},
            jwt_token,
            device_info,
        )

        data = self._check_response(result)
        base_resp = data.get("base_resp", {})

        return base_resp.get("status_code") == 0


async def chat_completion(
    token: str,
    messages: List[Dict[str, Any]],
    model: str = "hailuo",
    stream: bool = False,
    **kwargs
) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk, None]]:
    """
    便捷的对话补全函数

    Args:
        token: 认证 token，格式为 "realUserID+JWTtoken" 或直接 JWT token
        messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
        model: 模型名称，默认为 "hailuo"
        stream: 是否使用流式输出
        **kwargs: 其他配置参数

    Returns:
        如果 stream=False，返回 ChatCompletionResponse
        如果 stream=True，返回 AsyncGenerator[ChatCompletionChunk, None]

    Example:
        >>> response = await chat_completion(
        ...     token="your_token",
        ...     messages=[{"role": "user", "content": "你好"}]
        ... )
        >>> print(response.get_content())
    """
    client = get_cached_client(token, **kwargs)
    return await client.chat_completion(messages, model, stream)


async def delete_chat(token: str, chat_id: Union[int, str], **kwargs) -> bool:
    """
    删除会话

    Args:
        token: 认证 token，格式为 "realUserID+JWTtoken" 或直接 JWT token
        chat_id: 会话 ID
        **kwargs: 其他配置参数

    Returns:
        是否删除成功

    Example:
        >>> success = await delete_chat(
        ...     token="your_token",
        ...     chat_id=370062091863032
        ... )
        >>> print(f"删除成功: {success}")
    """
    client = get_cached_client(token, **kwargs)
    return await client.delete_chat(chat_id)
