"""
Kimi Client - Kimi 模型客户端
"""
import json
import asyncio
import random
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from dataclasses import dataclass
import httpx

from .utils import (
    generate_uuid,
    get_base_headers,
    generate_cookie,
    unix_timestamp,
    timestamp_ms,
    wrap_urls_to_tags,
    is_base64_data,
    extract_base64_format,
    remove_base64_header,
    detect_token_type,
    extract_device_id_from_jwt,
    extract_session_id_from_jwt,
    extract_user_id_from_jwt,
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
    FileURLException,
    FileSizeExceededException,
    StreamPushingException,
    ResearchQuotaExceededException,
)


@dataclass
class KimiConfig:
    """Kimi 客户端配置"""

    access_token_expires: int = 300
    max_retry_count: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 120.0
    file_max_size: int = 100 * 1024 * 1024


# 全局客户端缓存
_client_cache: Dict[str, 'KimiClient'] = {}


def get_cached_client(refresh_token: str, **kwargs) -> 'KimiClient':
    """
    获取缓存的客户端实例

    如果配置没有变化，则复用已有的客户端实例

    Args:
        refresh_token: 刷新令牌
        **kwargs: 其他配置参数

    Returns:
        KimiClient 实例
    """
    # 生成缓存键
    config_key = f"{refresh_token}:{json.dumps(kwargs, sort_keys=True)}"

    # 检查缓存中是否存在
    if config_key in _client_cache:
        return _client_cache[config_key]

    # 创建新客户端并缓存
    client = KimiClient(refresh_token=refresh_token, **kwargs)
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


class KimiClient:
    """
    Kimi 模型客户端

    提供与 Kimi 模型交互的功能，支持同步和流式对话补全。
    """

    MODEL_NAME = "kimi"
    BASE_URL = "https://kimi.moonshot.cn"

    def __init__(
        self,
        refresh_token: str,
        config: Optional[KimiConfig] = None,
    ):
        """
        初始化 Kimi 客户端

        Args:
            refresh_token: 用于刷新 access_token 的 refresh_token
            config: 客户端配置
        """
        self.refresh_token = refresh_token
        self.config = config or KimiConfig()
        self._token_cache: Dict[str, TokenInfo] = {}
        self._token_request_queues: Dict[str, List] = {}
        self._device_id = str(
            random.randint(7000000000000000000, 7999999999999999999))
        self._session_id = str(
            random.randint(1700000000000000000, 1799999999999999999))

    def _get_headers(
        self,
        with_auth: bool = False,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        获取请求头

        Args:
            with_auth: 是否包含认证头
            token: access_token
            user_id: 用户 ID

        Returns:
            请求头字典
        """
        headers = get_base_headers()
        headers.update({
            "X-Msh-Device-Id": self._device_id,
            "X-Msh-Platform": "web",
            "X-Msh-Session-Id": self._session_id,
        })
        if with_auth and token:
            headers["Authorization"] = f"Bearer {token}"
        if user_id:
            headers["X-Traffic-Id"] = user_id
        return headers

    async def _request_token(self, refresh_token: str) -> TokenInfo:
        """
        请求 access_token

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            TokenInfo 对象
        """
        headers = self._get_headers(with_auth=True, token=refresh_token)

        async with httpx.AsyncClient(timeout=15.0,
                                     follow_redirects=True) as client:
            response = await client.get(
                f"{self.BASE_URL}/api/auth/token/refresh",
                headers=headers,
            )

        result = self._check_response(response, refresh_token)
        access_token = result.get("access_token")
        new_refresh_token = result.get("refresh_token")

        if not access_token:
            raise RequestFailedException("获取 access_token 失败")

        # 获取用户信息
        user_headers = self._get_headers(with_auth=True, token=access_token)
        async with httpx.AsyncClient(timeout=15.0,
                                     follow_redirects=True) as client:
            user_response = await client.get(
                f"{self.BASE_URL}/api/user",
                headers=user_headers,
            )

        user_result = self._check_response(user_response, refresh_token)
        user_id = user_result.get("id", "")

        if not user_id:
            raise RequestFailedException("获取用户信息失败")

        return TokenInfo(
            access_token=access_token,
            refresh_token=new_refresh_token or refresh_token,
            user_id=user_id,
            refresh_time=unix_timestamp() + self.config.access_token_expires,
        )

    async def _acquire_token(self, refresh_token: str) -> TokenInfo:
        """
        获取有效的 access_token

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            TokenInfo 对象
        """
        token_info = self._token_cache.get(refresh_token)

        if not token_info:
            token_info = await self._request_token(refresh_token)
            self._token_cache[refresh_token] = token_info

        if unix_timestamp() > token_info.refresh_time:
            token_info = await self._request_token(refresh_token)
            self._token_cache[refresh_token] = token_info

        return token_info

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
        if response.status_code == 401:
            self._token_cache.pop(refresh_token, None)
            raise TokenExpiredException("Token 已失效")

        if not response.content:
            raise RequestFailedException("响应为空")

        try:
            data = response.json()
        except Exception as e:
            # 如果 JSON 解析失败，尝试获取文本内容
            try:
                text = response.text
                raise RequestFailedException(
                    f"解析响应失败: {str(e)}, 响应内容: {text[:200]}")
            except Exception as text_e:
                raise RequestFailedException(
                    f"解析响应失败: {str(e)}, 无法读取响应文本: {str(text_e)}")

        if "error_type" in data:
            error_type = data.get("error_type")
            message = data.get("message", "未知错误")

            if error_type == "auth.token.invalid":
                self._token_cache.pop(refresh_token, None)
                raise TokenExpiredException("Token 已失效")

            if error_type == "chat.user_stream_pushing":
                raise StreamPushingException("已有对话流正在输出")

            raise RequestFailedException(f"请求 Kimi 失败: {message}")

        return data

    async def _request(
        self,
        method: str,
        uri: str,
        refresh_token: str,
        json_data: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        """
        发送请求

        Args:
            method: HTTP 方法
            uri: 请求 URI
            refresh_token: 用于刷新的 refresh_token
            json_data: JSON 数据
            headers: 额外请求头
            timeout: 超时时间

        Returns:
            响应数据
        """
        token_info = await self._acquire_token(refresh_token)
        request_headers = self._get_headers(
            with_auth=True,
            token=token_info.access_token,
            user_id=token_info.user_id,
        )
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(timeout=timeout
                                     or self.config.request_timeout,
                                     follow_redirects=True) as client:
            response = await client.request(
                method=method,
                url=f"{self.BASE_URL}{uri}",
                headers=request_headers,
                json=json_data,
            )

        return self._check_response(response, refresh_token)

    async def _create_conversation(self, model: str, name: str,
                                   refresh_token: str) -> str:
        """
        创建会话

        Args:
            model: 模型名称
            name: 会话名称
            refresh_token: 用于刷新的 refresh_token

        Returns:
            会话 ID
        """
        kimiplus_id = model if len(model) == 20 and model.isalnum() else "kimi"
        result = await self._request(
            "POST",
            "/api/chat",
            refresh_token,
            json_data={
                "enter_method": "new_chat",
                "is_example": False,
                "kimiplus_id": kimiplus_id,
                "name": name,
            },
        )
        return result.get("id")

    async def _remove_conversation(self, conv_id: str, refresh_token: str):
        """
        移除会话

        Args:
            conv_id: 会话 ID
            refresh_token: 用于刷新的 refresh_token
        """
        await self._request("DELETE", f"/api/chat/{conv_id}", refresh_token)

    async def _get_research_usage(self, refresh_token: str) -> Dict[str, int]:
        """
        获取探索版使用量

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            使用量信息
        """
        return await self._request("GET", "/api/chat/research/usage",
                                   refresh_token)

    def _prepare_messages(
        self,
        messages: List[Dict[str, Any]],
        is_ref_conv: bool = False,
    ) -> List[Dict[str, str]]:
        """
        预处理消息

        将多条消息合并为一条，实现多轮对话效果

        Args:
            messages: 消息列表
            is_ref_conv: 是否为引用会话

        Returns:
            处理后的消息列表
        """
        if not messages:
            return [{"role": "user", "content": ""}]

        if is_ref_conv or len(messages) < 2:
            # 透传模式
            content = ""
            for msg in messages:
                msg_content = msg.get("content", "")
                if isinstance(msg_content, list):
                    # 处理多模态内容
                    for item in msg_content:
                        if isinstance(item,
                                      dict) and item.get("type") == "text":
                            content += item.get("text", "") + "\n"
                else:
                    role = msg.get("role", "user")
                    if role == "user":
                        content += wrap_urls_to_tags(msg_content) + "\n"
                    else:
                        content += msg_content + "\n"
        else:
            # 合并消息模式
            latest_message = messages[-1]
            has_file_or_image = (isinstance(
                latest_message.get("content"), list) and any(
                    isinstance(v, dict)
                    and v.get("type") in ["file", "image_url"]
                    for v in latest_message.get("content", [])))

            # 注入消息提升注意力
            if has_file_or_image:
                messages = messages[:-1] + [{
                    "content": "关注用户最新发送文件和消息",
                    "role": "system"
                }] + [messages[-1]]
            else:
                messages = messages[:-1] + [{
                    "content": "关注用户最新的消息",
                    "role": "system"
                }] + [messages[-1]]

            content = ""
            for msg in messages:
                msg_content = msg.get("content", "")
                role = msg.get("role", "user")
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item,
                                      dict) and item.get("type") == "text":
                            content += f"{role}:{item.get('text', '')}\n"
                else:
                    if role == "user":
                        content += f"{role}:{wrap_urls_to_tags(msg_content)}\n"
                    else:
                        content += f"{role}:{msg_content}\n"

        return [{"role": "user", "content": content.strip()}]

    def _extract_ref_file_urls(self, messages: List[Dict[str,
                                                         Any]]) -> List[str]:
        """
        提取消息中引用的文件 URL

        Args:
            messages: 消息列表

        Returns:
            文件 URL 列表
        """
        urls = []
        if not messages:
            return urls

        last_message = messages[-1]
        content = last_message.get("content", [])

        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "file":
                    file_url = item.get("file_url", {})
                    if isinstance(file_url, dict) and file_url.get("url"):
                        urls.append(file_url["url"])
                elif item_type == "image_url":
                    image_url = item.get("image_url", {})
                    if isinstance(image_url, dict) and image_url.get("url"):
                        urls.append(image_url["url"])

        return urls

    async def _pre_sign_url(self, action: str, filename: str,
                            refresh_token: str) -> dict:
        """
        获取预签名的文件 URL

        Args:
            action: 操作类型
            filename: 文件名称
            refresh_token: 用于刷新的 refresh_token

        Returns:
            预签名信息
        """
        token_info = await self._acquire_token(refresh_token)
        headers = self._get_headers(
            with_auth=True,
            token=token_info.access_token,
            user_id=token_info.user_id,
        )
        headers["Referer"] = "https://kimi.moonshot.cn/"

        async with httpx.AsyncClient(timeout=15.0,
                                     follow_redirects=True) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/pre-sign-url",
                headers=headers,
                json={
                    "action": action,
                    "name": filename
                },
            )

        return self._check_response(response, refresh_token)

    async def _check_file_url(self, file_url: str):
        """
        预检查文件 URL 有效性

        Args:
            file_url: 文件 URL

        Raises:
            FileURLException: 文件 URL 无效
            FileSizeExceededException: 文件超出大小限制
        """
        if is_base64_data(file_url):
            return

        async with httpx.AsyncClient(timeout=15.0,
                                     follow_redirects=True) as client:
            response = await client.head(file_url)

        if response.status_code >= 400:
            raise FileURLException(
                f"文件 {file_url} 无效: [{response.status_code}]")

        content_length = response.headers.get("content-length")
        if content_length:
            file_size = int(content_length)
            if file_size > self.config.file_max_size:
                raise FileSizeExceededException(f"文件 {file_url} 超出大小限制")

    async def _upload_file(
            self,
            file_url: str,
            refresh_token: str,
            ref_conv_id: Optional[str] = None) -> FileUploadResult:
        """
        上传文件

        Args:
            file_url: 文件 URL 或 base64 数据
            refresh_token: 用于刷新的 refresh_token
            ref_conv_id: 引用会话 ID

        Returns:
            文件上传结果
        """
        # 预检查远程文件 URL 可用性
        await self._check_file_url(file_url)

        filename = ""
        file_data = b""
        mime_type = ""

        if is_base64_data(file_url):
            # 处理 base64 数据
            mime_type = extract_base64_format(file_url)
            ext = mime_type.split("/")[-1] if mime_type else "bin"
            filename = f"{generate_uuid(separator=False)}.{ext}"
            import base64
            file_data = base64.b64decode(remove_base64_header(file_url))
        else:
            # 下载文件
            import os
            filename = os.path.basename(file_url.split("?")[0])
            async with httpx.AsyncClient(timeout=60.0,
                                         follow_redirects=True) as client:
                response = await client.get(file_url)
                file_data = response.content

        file_type = "image" if "image" in mime_type else "file"

        # 获取预签名文件 URL
        pre_sign_result = await self._pre_sign_url(file_type, filename,
                                                   refresh_token)
        upload_url = pre_sign_result.get("url")
        object_name = pre_sign_result.get("object_name")
        file_id = pre_sign_result.get("file_id")

        if not upload_url:
            raise RequestFailedException("获取预签名 URL 失败")

        # 上传文件到目标 OSS
        token_info = await self._acquire_token(refresh_token)
        upload_headers = self._get_headers(
            with_auth=True,
            token=token_info.access_token,
            user_id=token_info.user_id,
        )
        upload_headers.update({
            "Content-Type": mime_type or "application/octet-stream",
            "Referer": "https://kimi.moonshot.cn/",
        })

        async with httpx.AsyncClient(timeout=120.0,
                                     follow_redirects=True) as client:
            upload_response = await client.put(
                upload_url,
                headers=upload_headers,
                content=file_data,
            )

        if upload_response.status_code >= 400:
            raise RequestFailedException(
                f"上传文件失败: {upload_response.status_code}")

        # 等待文件处理完成
        start_time = asyncio.get_event_loop().time()
        file_detail = None

        while True:
            if asyncio.get_event_loop().time() - start_time > 30:
                raise RequestFailedException("文件等待处理超时")

            token_info = await self._acquire_token(refresh_token)
            headers = self._get_headers(
                with_auth=True,
                token=token_info.access_token,
                user_id=token_info.user_id,
            )
            headers["Referer"] = "https://kimi.moonshot.cn/"

            async with httpx.AsyncClient(timeout=15.0,
                                         follow_redirects=True) as client:
                if file_type == "image":
                    response = await client.post(
                        f"{self.BASE_URL}/api/file",
                        headers=headers,
                        json={
                            "type": "image",
                            "file_id": file_id,
                            "name": filename,
                        },
                    )
                else:
                    response = await client.post(
                        f"{self.BASE_URL}/api/file",
                        headers=headers,
                        json={
                            "type": "file",
                            "name": filename,
                            "object_name": object_name,
                            "file_id": "",
                            "chat_id": ref_conv_id,
                        },
                    )

            result = self._check_response(response, refresh_token)
            file_id = result.get("id", file_id)
            status = result.get("status")

            if status in ["initialized", "parsed"]:
                file_detail = result
                break

            await asyncio.sleep(0.5)

        # 等待文件解析完成
        if file_detail and file_detail.get("status") != "parsed":
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 30:
                token_info = await self._acquire_token(refresh_token)
                headers = self._get_headers(
                    with_auth=True,
                    token=token_info.access_token,
                    user_id=token_info.user_id,
                )
                headers["Referer"] = "https://kimi.moonshot.cn/"

                try:
                    async with httpx.AsyncClient(
                            timeout=120.0, follow_redirects=True) as client:
                        await client.post(
                            f"{self.BASE_URL}/api/file/parse_process",
                            headers=headers,
                            json={
                                "ids": [file_id],
                                "timeout": 120000
                            },
                        )
                    break
                except Exception:
                    await asyncio.sleep(0.5)

        return FileUploadResult(
            id=file_detail.get("id", file_id),
            name=file_detail.get("name", filename),
            size=file_detail.get("size", len(file_data)),
            status=file_detail.get("status", "initialized"),
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str = "kimi",
        stream: bool = False,
        refresh_token: Optional[str] = None,
        ref_conv_id: Optional[str] = None,
    ) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk,
                                                      None]]:
        """
        对话补全

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            model: 模型名称，支持 kimi、kimi-search、kimi-research、k1 等
            stream: 是否使用流式输出
            refresh_token: 用于刷新的 refresh_token，如果不提供则使用初始化时的 token
            ref_conv_id: 引用会话 ID

        Returns:
            如果 stream=False，返回 ChatCompletionResponse
            如果 stream=True，返回 AsyncGenerator[ChatCompletionChunk, None]
        """
        token = refresh_token or self.refresh_token

        if stream:
            return self._chat_completion_stream(messages, model, token,
                                                ref_conv_id)
        else:
            return await self._chat_completion_sync(messages, model, token,
                                                    ref_conv_id)

    async def _chat_completion_sync(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        refresh_token: str,
        ref_conv_id: Optional[str] = None,
        retry_count: int = 0,
        segment_id: Optional[str] = None,
        conv_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """
        同步对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            refresh_token: 用于刷新的 refresh_token
            ref_conv_id: 引用会话 ID
            retry_count: 重试次数
            segment_id: 分段 ID（用于继续生成）
            conv_id: 会话 ID（用于重试时复用）

        Returns:
            对话补全响应
        """
        created_conv = False
        try:
            # 创建会话
            if conv_id:
                # 重试时复用已有会话
                pass
            elif ref_conv_id and len(ref_conv_id) == 20:
                conv_id = ref_conv_id
            else:
                conv_id = await self._create_conversation(
                    model, "未命名会话", refresh_token)
                created_conv = True

            # 提取并上传引用文件
            ref_file_urls = self._extract_ref_file_urls(messages)
            ref_results = []
            if ref_file_urls:
                for file_url in ref_file_urls:
                    result = await self._upload_file(file_url, refresh_token,
                                                     conv_id)
                    ref_results.append(result)

            refs = [r.id for r in ref_results]
            refs_file = [{
                "detail": r.__dict__,
                "done": True,
                "file": {},
                "file_info": r.__dict__,
                "id": r.id,
                "name": r.name,
                "parse_status": "success",
                "size": r.size,
                "upload_progress": 100,
                "upload_status": "success",
            } for r in ref_results]

            # 预处理消息
            send_messages = self._prepare_messages(messages, bool(ref_conv_id))

            # 判断模型类型
            is_math = "math" in model
            is_search = "search" in model
            is_research = "research" in model
            is_k1 = "k1" in model

            # 检查探索版使用量
            if is_research:
                usage = await self._get_research_usage(refresh_token)
                if usage.get("used", 0) >= usage.get("total", 0):
                    raise ResearchQuotaExceededException("探索版使用量已达到上限")

            # 确定 kimiplus_id
            if is_k1:
                kimiplus_id = "crm40ee9e5jvhsn7ptcg"
            elif len(model) == 20 and model.isalnum():
                kimiplus_id = model
            else:
                kimiplus_id = "kimi"

            # 构建请求数据
            if segment_id:
                request_data = {
                    "segment_id": segment_id,
                    "action": "continue",
                    "messages": [{
                        "role": "user",
                        "content": " "
                    }],
                    "kimiplus_id": kimiplus_id,
                    "extend": {
                        "sidebar": True
                    },
                }
            else:
                request_data = {
                    "kimiplus_id": kimiplus_id,
                    "messages": send_messages,
                    "refs": refs,
                    "refs_file": refs_file,
                    "use_math": is_math,
                    "use_research": is_research,
                    "use_search": is_search,
                    "extend": {
                        "sidebar": True
                    },
                }

            # 发送请求
            token_info = await self._acquire_token(refresh_token)
            headers = self._get_headers(
                with_auth=True,
                token=token_info.access_token,
                user_id=token_info.user_id,
            )
            headers["Referer"] = f"https://kimi.moonshot.cn/chat/{conv_id}"

            async with httpx.AsyncClient(timeout=self.config.request_timeout,
                                         follow_redirects=True) as client:
                response = await client.post(
                    f"{self.BASE_URL}/api/chat/{conv_id}/completion/stream",
                    headers=headers,
                    json=request_data,
                )

            # 处理流式响应
            result = await self._receive_stream(model, conv_id, response)

            # 如果生成长度超限，继续请求
            if result.choices[
                    0].finish_reason == "length" and result.segment_id:
                continue_result = await self._chat_completion_sync(
                    [], model, refresh_token, conv_id, 0, result.segment_id)
                result.choices[0].message.content += continue_result.choices[
                    0].message.content

            # 异步移除会话
            if created_conv:
                try:
                    await self._remove_conversation(conv_id, refresh_token)
                except Exception:
                    pass

            return result

        except Exception as e:
            if retry_count < self.config.max_retry_count:
                await asyncio.sleep(self.config.retry_delay)
                return await self._chat_completion_sync(
                    messages, model, refresh_token, ref_conv_id,
                    retry_count + 1, segment_id, conv_id)
            raise

    async def _chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        refresh_token: str,
        ref_conv_id: Optional[str] = None,
        retry_count: int = 0,
        conv_id: Optional[str] = None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        流式对话补全

        Args:
            messages: 消息列表
            model: 模型名称
            refresh_token: 用于刷新的 refresh_token
            ref_conv_id: 引用会话 ID
            retry_count: 重试次数
            conv_id: 会话 ID（用于重试时复用）

        Yields:
            对话补全流式块
        """
        created_conv = False
        try:
            # 创建会话
            if conv_id:
                # 重试时复用已有会话
                pass
            elif ref_conv_id and len(ref_conv_id) == 20:
                conv_id = ref_conv_id
            else:
                conv_id = await self._create_conversation(
                    model, "未命名会话", refresh_token)
                created_conv = True

            # 提取并上传引用文件
            ref_file_urls = self._extract_ref_file_urls(messages)
            ref_results = []
            if ref_file_urls:
                for file_url in ref_file_urls:
                    result = await self._upload_file(file_url, refresh_token,
                                                     conv_id)
                    ref_results.append(result)

            refs = [r.id for r in ref_results]
            refs_file = [{
                "detail": r.__dict__,
                "done": True,
                "file": {},
                "file_info": r.__dict__,
                "id": r.id,
                "name": r.name,
                "parse_status": "success",
                "size": r.size,
                "upload_progress": 100,
                "upload_status": "success",
            } for r in ref_results]

            # 预处理消息
            send_messages = self._prepare_messages(messages, bool(ref_conv_id))

            # 判断模型类型
            is_math = "math" in model
            is_search = "search" in model
            is_research = "research" in model
            is_k1 = "k1" in model
            is_silent = "silent" in model

            # 检查探索版使用量
            if is_research:
                usage = await self._get_research_usage(refresh_token)
                if usage.get("used", 0) >= usage.get("total", 0):
                    raise ResearchQuotaExceededException("探索版使用量已达到上限")

            # 确定 kimiplus_id
            if is_k1:
                kimiplus_id = "crm40ee9e5jvhsn7ptcg"
            elif len(model) == 20 and model.isalnum():
                kimiplus_id = model
            else:
                kimiplus_id = "kimi"

            # 发送请求
            token_info = await self._acquire_token(refresh_token)
            headers = self._get_headers(
                with_auth=True,
                token=token_info.access_token,
                user_id=token_info.user_id,
            )
            headers["Referer"] = f"https://kimi.moonshot.cn/chat/{conv_id}"

            async with httpx.AsyncClient(timeout=self.config.request_timeout,
                                         follow_redirects=True) as client:
                async with client.stream(
                        "POST",
                        f"{self.BASE_URL}/api/chat/{conv_id}/completion/stream",
                        headers=headers,
                        json={
                            "kimiplus_id": kimiplus_id,
                            "messages": send_messages,
                            "refs": refs,
                            "refs_file": refs_file,
                            "use_math": is_math,
                            "use_research": is_research,
                            "use_search": is_search,
                            "extend": {
                                "sidebar": True
                            },
                        },
                ) as response:
                    async for chunk in self._process_stream(
                            model, conv_id, response, is_silent):
                        yield chunk

            # 异步移除会话
            if created_conv:
                try:
                    await self._remove_conversation(conv_id, refresh_token)
                except Exception:
                    pass

        except (TokenExpiredException, StreamPushingException,
                ResearchQuotaExceededException, FileURLException,
                FileSizeExceededException):
            # 这些异常不应该重试
            raise
        except Exception as e:
            if retry_count < self.config.max_retry_count:
                await asyncio.sleep(self.config.retry_delay)
                async for chunk in self._chat_completion_stream(
                        messages, model, refresh_token, ref_conv_id,
                        retry_count + 1, conv_id):
                    yield chunk
            else:
                raise

    async def _receive_stream(
        self,
        model: str,
        conv_id: str,
        response: httpx.Response,
    ) -> ChatCompletionResponse:
        """
        从流接收完整的消息内容

        Args:
            model: 模型名称
            conv_id: 会话 ID
            response: HTTP 响应

        Returns:
            完整的对话补全响应
        """
        content = ""
        segment_id = ""
        finish_reason = "stop"
        ref_content = ""
        web_search_count = 0
        is_silent = "silent" in model

        # 解析 SSE 流
        buffer = ""
        async for line in response.aiter_lines():
            buffer += line + "\n"
            while "\n\n" in buffer:
                event_data, buffer = buffer.split("\n\n", 1)
                event_lines = event_data.strip().split("\n")
                event_type = ""
                data = ""

                for event_line in event_lines:
                    if event_line.startswith("event:"):
                        event_type = event_line[6:].strip()
                    elif event_line.startswith("data:"):
                        data = event_line[5:].strip()

                if not data:
                    continue

                try:
                    result = json.loads(data)
                    # 优先使用 JSON 中的 event 字段，如果没有则使用 SSE 的 event 行
                    event = result.get("event") or event_type

                    if event == "cmpl" and result.get("text"):
                        content += result["text"]
                    elif event == "req":
                        segment_id = result.get("id", "")
                    elif event == "length":
                        finish_reason = "length"
                    elif event in ["all_done", "error"]:
                        if event == "error":
                            content += "\n[内容由于不合规被停止生成，我们换个话题吧]"
                        if ref_content:
                            content += f"\n\n搜索结果来自：\n{ref_content}"
                    elif not is_silent and event == "search_plus":
                        msg = result.get("msg", {})
                        if msg.get("type") == "get_res":
                            web_search_count += 1
                            ref_content += f"【检索 {web_search_count}】 [{msg.get('title')}]({msg.get('url')})\n\n"
                except json.JSONDecodeError:
                    continue

        return ChatCompletionResponse(
            id=conv_id,
            model=model,
            object="chat.completion",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=UsageInfo(prompt_tokens=1,
                            completion_tokens=1,
                            total_tokens=2),
            created=unix_timestamp(),
            segment_id=segment_id,
        )

    async def _process_stream(
        self,
        model: str,
        conv_id: str,
        response: httpx.Response,
        is_silent: bool = False,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        处理流式响应

        Args:
            model: 模型名称
            conv_id: 会话 ID
            response: HTTP 响应
            is_silent: 是否静默搜索

        Yields:
            对话补全流式块
        """
        created = unix_timestamp()
        segment_id = ""
        web_search_count = 0
        search_flag = False
        length_exceed = False

        # 发送初始块
        yield ChatCompletionChunk(
            id=conv_id,
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
            segment_id=segment_id,
        )

        # 解析 SSE 流
        buffer = ""
        async for line in response.aiter_lines():
            buffer += line + "\n"
            while "\n\n" in buffer:
                event_data, buffer = buffer.split("\n\n", 1)
                event_lines = event_data.strip().split("\n")
                event_type = ""
                data = ""

                for event_line in event_lines:
                    if event_line.startswith("event:"):
                        event_type = event_line[6:].strip()
                    elif event_line.startswith("data:"):
                        data = event_line[5:].strip()

                if not data:
                    continue

                try:
                    result = json.loads(data)
                    # 优先使用 JSON 中的 event 字段，如果没有则使用 SSE 的 event 行
                    event = result.get("event") or event_type

                    if event == "cmpl":
                        text = result.get("text", "")
                        except_char_index = text.find("�")
                        if except_char_index != -1:
                            text = text[:except_char_index]

                        delta_content = ("\n" if search_flag else "") + text
                        if search_flag:
                            search_flag = False

                        yield ChatCompletionChunk(
                            id=conv_id,
                            model=model,
                            object="chat.completion.chunk",
                            choices=[
                                ChatChoice(
                                    index=0,
                                    delta={"content": delta_content},
                                    finish_reason=None,
                                )
                            ],
                            created=created,
                            segment_id=segment_id,
                        )
                    elif event == "req":
                        segment_id = result.get("id", "")
                    elif event == "length":
                        length_exceed = True
                    elif event in ["all_done", "error"]:
                        delta = {}
                        if event == "error":
                            delta = {"content": "\n[内容由于不合规被停止生成，我们换个话题吧]"}

                        yield ChatCompletionChunk(
                            id=conv_id,
                            model=model,
                            object="chat.completion.chunk",
                            choices=[
                                ChatChoice(
                                    index=0,
                                    delta=delta,
                                    finish_reason="length"
                                    if length_exceed else "stop",
                                )
                            ],
                            created=created,
                            segment_id=segment_id,
                        )
                        return
                    elif not is_silent and event == "search_plus":
                        msg = result.get("msg", {})
                        if msg.get("type") == "get_res":
                            if not search_flag:
                                search_flag = True
                            web_search_count += 1

                            yield ChatCompletionChunk(
                                id=conv_id,
                                model=model,
                                object="chat.completion.chunk",
                                choices=[
                                    ChatChoice(
                                        index=0,
                                        delta={
                                            "content":
                                            f"【检索 {web_search_count}】 [{msg.get('title')}]({msg.get('url')})\n"
                                        },
                                        finish_reason=None,
                                    )
                                ],
                                created=created,
                                segment_id=segment_id,
                            )
                except json.JSONDecodeError:
                    continue


async def chat_completion(
    messages: List[Dict[str, Any]],
    refresh_token: str,
    model: str = "kimi",
    stream: bool = False,
) -> Union[ChatCompletionResponse, AsyncGenerator[ChatCompletionChunk, None]]:
    """
    便捷的对话补全函数

    Args:
        messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
        refresh_token: 用于刷新的 refresh_token
        model: 模型名称，支持 kimi、kimi-search、kimi-research、k1 等
        stream: 是否使用流式输出

    Returns:
        如果 stream=False，返回 ChatCompletionResponse
        如果 stream=True，返回 AsyncGenerator[ChatCompletionChunk, None]

    Example:
        >>> # 同步调用
        >>> response = await chat_completion(
        ...     messages=[{"role": "user", "content": "你好"}],
        ...     refresh_token="your_refresh_token",
        ... )
        >>> print(response.get_content())

        >>> # 流式调用
        >>> async for chunk in await chat_completion(
        ...     messages=[{"role": "user", "content": "你好"}],
        ...     refresh_token="your_refresh_token",
        ...     stream=True,
        ... ):
        ...     print(chunk)
    """
    client = get_cached_client(refresh_token=refresh_token)
    return await client.chat_completion(messages, model, stream)
