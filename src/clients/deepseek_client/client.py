"""
DeepSeek Client - DeepSeek 模型客户端
"""
import json
import re
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
    create_challenge_response,
)
from .models import (
    ChatMessage,
    ChatChoice,
    ChatCompletionResponse,
    ChatCompletionChunk,
    UsageInfo,
    TokenInfo,
    ChallengeInfo,
)
from .exceptions import (
    APIException,
    TokenExpiredException,
    RequestFailedException,
    ThinkingQuotaException,
)


@dataclass
class DeepSeekConfig:
    """DeepSeek 客户端配置"""

    access_token_expires: int = 3600
    max_retry_count: int = 3
    retry_delay: float = 5.0
    request_timeout: float = 120.0


# 全局客户端缓存
_client_cache: Dict[str, 'DeepSeekClient'] = {}


def get_cached_client(refresh_token: str, **kwargs) -> 'DeepSeekClient':
    """
    获取缓存的客户端实例

    如果配置没有变化，则复用已有的客户端实例

    Args:
        refresh_token: 刷新令牌
        **kwargs: 其他配置参数

    Returns:
        DeepSeekClient 实例
    """
    # 生成缓存键
    config_key = f"{refresh_token}:{json.dumps(kwargs, sort_keys=True)}"

    # 检查缓存中是否存在
    if config_key in _client_cache:
        return _client_cache[config_key]

    # 创建新客户端并缓存
    client = DeepSeekClient(refresh_token=refresh_token, **kwargs)
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


class DeepSeekClient:
    """
    DeepSeek 模型客户端

    提供与 DeepSeek 模型交互的功能，支持同步和流式对话补全。
    """

    MODEL_NAME = "deepseek-chat"
    BASE_URL = "https://chat.deepseek.com"
    EVENT_COMMIT_ID = "41e9c7b1"

    def __init__(
        self,
        refresh_token: str,
        config: Optional[DeepSeekConfig] = None,
    ):
        """
        初始化 DeepSeek 客户端

        Args:
            refresh_token: 用于刷新 access_token 的 refresh_token
            config: 客户端配置
        """
        self.refresh_token = refresh_token
        self.config = config or DeepSeekConfig()
        self._token_cache: Dict[str, TokenInfo] = {}
        self._token_request_queues: Dict[str, List] = {}
        self._ip_address: Optional[str] = None

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

    async def _get_ip_address(self) -> str:
        """
        获取当前 IP 地址

        Returns:
            IP 地址
        """
        if self._ip_address:
            return self._ip_address

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.BASE_URL + "/",
                headers={
                    **get_base_headers(), "Cookie": generate_cookie()
                },
            )

        match = re.search(r'<meta name="ip" content="([\d.]+)">',
                          response.text)
        if not match:
            raise RequestFailedException("获取 IP 地址失败")

        self._ip_address = match.group(1)
        return self._ip_address

    async def _request_token(self, refresh_token: str) -> TokenInfo:
        """
        请求 access_token

        Args:
            refresh_token: 用于刷新的 refresh_token

        Returns:
            TokenInfo 对象
        """
        headers = self._get_headers(with_auth=True, token=refresh_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/api/v0/users/current",
                headers=headers,
            )

        result = self._check_response(response, refresh_token)
        # 根据原项目结构，token在biz_data中
        biz_data = result.get("biz_data", result)
        token = biz_data.get("token")

        if not token:
            raise RequestFailedException("获取token失败")

        return TokenInfo(
            access_token=token,
            refresh_token=token,
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

        if "code" not in data:
            return data.get("data", data)

        code = data.get("code")
        msg = data.get("msg", "未知错误")

        if code == 0:
            return data.get("data", data)

        if code == 40003:
            self._token_cache.pop(refresh_token, None)

        raise RequestFailedException(f"请求 DeepSeek 失败: {msg}")

    def _prepare_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        预处理消息

        将多条消息合并为一条，实现多轮对话效果

        Args:
            messages: 消息列表

        Returns:
            处理后的提示文本
        """
        processed_messages = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                texts = [
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                text = "\n".join(texts)
            else:
                text = str(content)
            processed_messages.append({
                "role": message.get("role", "user"),
                "text": text
            })

        if not processed_messages:
            return ""

        merged_blocks = []
        current_block = processed_messages[0].copy()

        for i in range(1, len(processed_messages)):
            msg = processed_messages[i]
            if msg["role"] == current_block["role"]:
                current_block["text"] += f"\n\n{msg['text']}"
            else:
                merged_blocks.append(current_block)
                current_block = msg.copy()
        merged_blocks.append(current_block)

        result_parts = []
        for idx, block in enumerate(merged_blocks):
            if block["role"] == "assistant":
                result_parts.append(
                    f"<｜Assistant｜>{block['text']}<｜end of sentence｜>")
            elif block["role"] in ["user", "system"]:
                if idx > 0:
                    result_parts.append(f"<｜User｜>{block['text']}")
                else:
                    result_parts.append(block["text"])
            else:
                result_parts.append(block["text"])

        result = "".join(result_parts)
        result = re.sub(r"!\[.+\]\(.+\)", "", result)
        return result

    async def _create_session(self) -> str:
        """
        创建会话

        Returns:
            会话 ID
        """
        token = await self._acquire_token(self.refresh_token)
        headers = self._get_headers(with_auth=True, token=token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/v0/chat_session/create",
                headers=headers,
                json={"character_id": None},
            )

        result = self._check_response(response, self.refresh_token)
        if not result:
            raise RequestFailedException("创建会话失败，可能是账号或 IP 地址被封禁")
        # 根据原项目结构，会话ID在biz_data中
        biz_data = result.get("biz_data", result)
        session_id = biz_data.get("id")
        if not session_id:
            raise RequestFailedException("创建会话失败，无法获取会话ID")
        return session_id

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否删除成功
        """
        token = await self._acquire_token(self.refresh_token)
        headers = self._get_headers(with_auth=True, token=token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/v0/chat_session/delete",
                headers=headers,
                json={"chat_session_id": session_id},
            )

        result = self._check_response(response, self.refresh_token)
        # 根据API响应结构，检查code是否为0表示成功
        biz_code = result.get("biz_code", 0)
        return biz_code == 0

    async def _get_challenge(self, target_path: str) -> ChallengeInfo:
        """
        获取 Challenge

        Args:
            target_path: 目标路径

        Returns:
            ChallengeInfo 对象
        """
        token = await self._acquire_token(self.refresh_token)
        headers = self._get_headers(with_auth=True, token=token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/v0/chat/create_pow_challenge",
                headers=headers,
                json={"target_path": target_path},
            )

        result = self._check_response(response, self.refresh_token)
        # 根据原项目结构，challenge在biz_data中
        biz_data = result.get("biz_data", result)
        challenge = biz_data.get("challenge", {})

        return ChallengeInfo(
            algorithm=challenge.get("algorithm", ""),
            challenge=challenge.get("challenge", ""),
            salt=challenge.get("salt", ""),
            difficulty=challenge.get("difficulty", 0),
            expire_at=challenge.get("expire_at", 0),
            signature=challenge.get("signature", ""),
        )

    async def _get_thinking_quota(self) -> int:
        """
        获取深度思考配额

        Returns:
            配额数量
        """
        token = await self._acquire_token(self.refresh_token)
        headers = self._get_headers(with_auth=True, token=token)
        headers["Cookie"] = generate_cookie()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/api/v0/users/feature_quota",
                headers=headers,
            )

        result = self._check_response(response, self.refresh_token)
        thinking_data = result.get("thinking", {})
        quota = thinking_data.get("quota", 0)
        used = thinking_data.get("used", 0)

        if not isinstance(quota, int) or not isinstance(used, int):
            return 0

        remaining = quota - used
        return max(0, remaining)

    async def _send_events(self, session_id: str) -> None:
        """
        发送事件（缓解被封号风险）

        Args:
            session_id: 会话 ID
        """
        try:
            token = await self._acquire_token(self.refresh_token)
            headers = self._get_headers(with_auth=True, token=token)
            headers["Cookie"] = generate_cookie()

            ip_address = await self._get_ip_address()
            ts = timestamp_ms()
            event_session_id = f"session_v0_{generate_uuid(separator=False)[:20]}"

            events = [
                {
                    "session_id": event_session_id,
                    "client_timestamp_ms": ts,
                    "event_name": "__reportEvent",
                    "event_message": "调用上报事件接口",
                    "payload": {
                        "__location": "https://chat.deepseek.com/",
                        "__ip": ip_address,
                        "__region": "CN",
                        "__pageVisibility": "true",
                        "__nodeEnv": "production",
                        "__deployEnv": "production",
                        "__appVersion": headers["X-App-Version"],
                        "__commitId": self.EVENT_COMMIT_ID,
                        "__userAgent": headers["User-Agent"],
                        "__referrer": "",
                        "method": "post",
                        "url": "/api/v0/events",
                        "path": "/api/v0/events",
                    },
                    "level": "info",
                },
                {
                    "session_id": event_session_id,
                    "client_timestamp_ms": ts + 100 + random.randint(0, 1000),
                    "event_name": "createSessionAndStartCompletion",
                    "event_message": "开始创建对话",
                    "payload": {
                        "__location": "https://chat.deepseek.com/",
                        "__ip": ip_address,
                        "__region": "CN",
                        "__pageVisibility": "true",
                        "__nodeEnv": "production",
                        "__deployEnv": "production",
                        "__appVersion": headers["X-App-Version"],
                        "__commitId": self.EVENT_COMMIT_ID,
                        "__userAgent": headers["User-Agent"],
                        "__referrer": "",
                        "agentId": "chat",
                        "thinkingEnabled": False,
                    },
                    "level": "info",
                },
            ]

            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self.BASE_URL}/api/v0/events",
                    headers=headers,
                    json={"events": events},
                )
        except Exception:
            pass

    async def create_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
    ) -> ChatCompletionResponse:
        """
        创建对话补全（非流式）

        Args:
            messages: 消息列表
            model: 模型名称
            conversation_id: 会话 ID（用于继续对话，格式：session_id@message_id）
            search_enabled: 是否启用联网搜索
            thinking_enabled: 是否启用深度思考

        Returns:
            ChatCompletionResponse 对象
        """
        retry_count = 0
        model = model or self.MODEL_NAME

        while retry_count < self.config.max_retry_count:
            try:
                if conversation_id and not re.match(r"[0-9a-z\-]{36}@[0-9]+",
                                                    conversation_id):
                    conversation_id = None

                prompt = self._prepare_messages(messages)

                ref_session_id = None
                ref_parent_msg_id = None
                if conversation_id:
                    parts = conversation_id.split("@")
                    ref_session_id = parts[0]
                    ref_parent_msg_id = parts[1] if len(parts) > 1 else None

                is_search_model = "search" in model or search_enabled
                is_thinking_model = ("think" in model or "r1" in model
                                     or thinking_enabled or "深度思考" in prompt)

                if is_thinking_model:
                    try:
                        quota = await self._get_thinking_quota()
                        if quota <= 0:
                            raise ThinkingQuotaException()
                    except ThinkingQuotaException:
                        raise
                    except Exception:
                        pass

                challenge_info = await self._get_challenge(
                    "/api/v0/chat/completion")
                challenge_response = await create_challenge_response(
                    algorithm=challenge_info.algorithm,
                    challenge=challenge_info.challenge,
                    salt=challenge_info.salt,
                    difficulty=challenge_info.difficulty,
                    expire_at=challenge_info.expire_at,
                    signature=challenge_info.signature,
                    target_path="/api/v0/chat/completion",
                )

                # 标记是否为新创建的会话，用于后续自动删除
                is_new_session = ref_session_id is None
                session_id = ref_session_id or await self._create_session()
                token = await self._acquire_token(self.refresh_token)

                headers = self._get_headers(with_auth=True, token=token)
                headers["Cookie"] = generate_cookie()
                headers["X-Ds-Pow-Response"] = challenge_response

                request_body = {
                    "chat_session_id": session_id,
                    "parent_message_id": ref_parent_msg_id,
                    "prompt": prompt,
                    "ref_file_ids": [],
                    "search_enabled": is_search_model,
                    "thinking_enabled": is_thinking_model,
                }

                asyncio.create_task(self._send_events(session_id))

                try:
                    async with httpx.AsyncClient(
                            timeout=self.config.request_timeout) as client:
                        async with client.stream(
                                "POST",
                                f"{self.BASE_URL}/api/v0/chat/completion",
                                headers=headers,
                                json=request_body,
                        ) as response:
                            content_type = response.headers.get(
                                "content-type", "")
                            if "text/event-stream" not in content_type:
                                error_text = await response.aread()
                                raise RequestFailedException(
                                    f"响应类型无效: {content_type}")

                            result = await self._receive_stream(
                                response, model, session_id)
                            return result
                finally:
                    # 如果是新创建的会话，在请求完成后自动删除
                    if is_new_session:
                        try:
                            await self.delete_session(session_id)
                        except Exception:
                            # 删除失败不影响主流程
                            pass

            except (APIException, httpx.HTTPError) as e:
                retry_count += 1
                if retry_count >= self.config.max_retry_count:
                    raise
                await asyncio.sleep(self.config.retry_delay)

        raise RequestFailedException("达到最大重试次数")

    async def _receive_stream(self, response: httpx.Response, model: str,
                              session_id: str) -> ChatCompletionResponse:
        """
        接收流式响应并组装完整结果

        Args:
            response: HTTP 流式响应
            model: 模型名称
            session_id: 会话 ID

        Returns:
            ChatCompletionResponse 对象
        """
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

        accumulated_content = ""
        accumulated_thinking = ""
        message_id = ""
        current_path = "content"
        buffer = ""

        async for chunk in response.aiter_bytes():
            buffer += chunk.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()

                if not line:
                    continue

                # 处理事件行
                if line.startswith("event: "):
                    event_type = line[7:]
                    if event_type in ["finish", "close"]:
                        # 标记需要结束，但继续处理缓冲区中剩余的数据
                        # 更新数据，但继续循环处理后续的数据行
                        if data.choices and data.choices[0].message:
                            data.choices[
                                0].message.content = accumulated_content.strip(
                                )
                            data.choices[
                                0].message.reasoning_content = accumulated_thinking.strip(
                                ) or None
                        data.id = f"{session_id}@{message_id}"
                    continue

                if not line.startswith("data: "):
                    continue

                json_str = line[6:]
                if json_str == "[DONE]":
                    # 在返回前更新数据
                    if data.choices and data.choices[0].message:
                        data.choices[
                            0].message.content = accumulated_content.strip()
                        data.choices[
                            0].message.reasoning_content = accumulated_thinking.strip(
                            ) or None
                    data.id = f"{session_id}@{message_id}"
                    return data

                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    continue

                if result.get("response_message_id") and not message_id:
                    message_id = result["response_message_id"]

                # 更新当前路径
                if result.get("v") and isinstance(result["v"], dict):
                    if result["v"].get("response", {}).get("thinking_enabled"):
                        current_path = "thinking"
                    else:
                        current_path = "content"

                # 根据路径字段更新当前路径
                if result.get("p") == "response/thinking_content":
                    current_path = "thinking"
                elif result.get("p") == "response/content":
                    current_path = "content"
                elif result.get("p") == "response/fragments":
                    current_path = "content"

                # 处理 v 是字典的情况（包含 response.fragments）
                if isinstance(result.get("v"), dict):
                    response_data = result["v"].get("response", {})
                    fragments = response_data.get("fragments", [])
                    if isinstance(fragments, list):
                        for fragment in fragments:
                            if isinstance(fragment, dict):
                                content = fragment.get("content", "")
                                if content:
                                    if current_path == "thinking":
                                        accumulated_thinking += content
                                    else:
                                        accumulated_content += content

                # 处理列表类型的值
                if isinstance(result.get("v"), list):
                    for item in result["v"]:
                        if isinstance(item, dict):
                            # 更新token使用情况
                            if item.get("accumulated_token_usage"
                                        ) and isinstance(item.get("v"), int):
                                data.usage.total_tokens = item["v"]

                            # 处理内容列表
                            if isinstance(item.get("v"), list):
                                cleaned = "".join(
                                    v.get("content", "") for v in item["v"]
                                    if isinstance(v, dict)).replace(
                                        "FINISHED", "")
                                if current_path == "thinking":
                                    accumulated_thinking += cleaned
                                else:
                                    accumulated_content += cleaned

                            # 处理字符串值
                            elif isinstance(item.get("v"), str):
                                cleaned = item["v"].replace("FINISHED", "")
                                if current_path == "thinking":
                                    accumulated_thinking += cleaned
                                else:
                                    accumulated_content += cleaned

                # 处理字符串类型的值
                if isinstance(result.get("v"), str):
                    cleaned = result["v"].replace("FINISHED", "")
                    if current_path == "thinking":
                        accumulated_thinking += cleaned
                    else:
                        accumulated_content += cleaned

        if data.choices and data.choices[0].message:
            data.choices[0].message.content = accumulated_content.strip()
            data.choices[
                0].message.reasoning_content = accumulated_thinking.strip(
                ) or None

        data.id = f"{session_id}@{message_id}"
        return data

    async def create_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
        search_enabled: bool = False,
        thinking_enabled: bool = False,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """
        创建对话补全（流式）

        Args:
            messages: 消息列表
            model: 模型名称
            conversation_id: 会话 ID
            search_enabled: 是否启用联网搜索
            thinking_enabled: 是否启用深度思考

        Yields:
            ChatCompletionChunk 对象
        """
        retry_count = 0
        model = model or self.MODEL_NAME

        while retry_count < self.config.max_retry_count:
            try:
                if conversation_id and not re.match(r"[0-9a-z\-]{36}@[0-9]+",
                                                    conversation_id):
                    conversation_id = None

                prompt = self._prepare_messages(messages)

                ref_session_id = None
                ref_parent_msg_id = None
                if conversation_id:
                    parts = conversation_id.split("@")
                    ref_session_id = parts[0]
                    ref_parent_msg_id = parts[1] if len(parts) > 1 else None

                is_search_model = "search" in model or search_enabled
                is_thinking_model = ("think" in model or "r1" in model
                                     or thinking_enabled or "深度思考" in prompt)

                if is_thinking_model:
                    try:
                        quota = await self._get_thinking_quota()
                        if quota <= 0:
                            raise ThinkingQuotaException()
                    except ThinkingQuotaException:
                        raise
                    except Exception:
                        pass

                challenge_info = await self._get_challenge(
                    "/api/v0/chat/completion")
                challenge_response = await create_challenge_response(
                    algorithm=challenge_info.algorithm,
                    challenge=challenge_info.challenge,
                    salt=challenge_info.salt,
                    difficulty=challenge_info.difficulty,
                    expire_at=challenge_info.expire_at,
                    signature=challenge_info.signature,
                    target_path="/api/v0/chat/completion",
                )

                # 标记是否为新创建的会话，用于后续自动删除
                is_new_session = ref_session_id is None
                session_id = ref_session_id or await self._create_session()
                token = await self._acquire_token(self.refresh_token)

                headers = self._get_headers(with_auth=True, token=token)
                headers["Cookie"] = generate_cookie()
                headers["X-Ds-Pow-Response"] = challenge_response

                request_body = {
                    "chat_session_id": session_id,
                    "parent_message_id": ref_parent_msg_id,
                    "prompt": prompt,
                    "ref_file_ids": [],
                    "search_enabled": is_search_model,
                    "thinking_enabled": is_thinking_model,
                }

                asyncio.create_task(self._send_events(session_id))

                try:
                    yield ChatCompletionChunk(
                        id="",
                        model=model,
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

                    async with httpx.AsyncClient(
                            timeout=self.config.request_timeout) as client:
                        async with client.stream(
                                "POST",
                                f"{self.BASE_URL}/api/v0/chat/completion",
                                headers=headers,
                                json=request_body,
                        ) as response:
                            content_type = response.headers.get(
                                "content-type", "")
                            if "text/event-stream" not in content_type:
                                raise RequestFailedException(
                                    f"响应类型无效: {content_type}")

                            message_id = ""
                            current_path = "content"
                            buffer = ""

                            async for chunk in response.aiter_bytes():
                                buffer += chunk.decode("utf-8",
                                                       errors="ignore")

                                while "\n" in buffer:
                                    line, buffer = buffer.split("\n", 1)
                                    line = line.strip()

                                    if not line or not line.startswith(
                                            "data: "):
                                        continue

                                    json_str = line[6:]
                                    if json_str == "[DONE]":
                                        yield ChatCompletionChunk(
                                            id=f"{session_id}@{message_id}",
                                            model=model,
                                            choices=[
                                                ChatChoice(
                                                    index=0,
                                                    delta={},
                                                    finish_reason="stop",
                                                )
                                            ],
                                            created=unix_timestamp(),
                                        )
                                        return

                                    try:
                                        result = json.loads(json_str)
                                    except json.JSONDecodeError:
                                        continue

                                    if result.get("response_message_id"
                                                  ) and not message_id:
                                        message_id = result[
                                            "response_message_id"]

                                    if result.get("v") and isinstance(
                                            result["v"], dict):
                                        if result["v"].get(
                                                "response",
                                            {}).get("thinking_enabled"):
                                            current_path = "thinking"
                                        else:
                                            current_path = "content"

                                    if result.get("p") == "response/fragments":
                                        current_path = "content"

                                    content_to_send = ""

                                    # 处理 v 是字典的情况（包含 response.fragments）
                                    if isinstance(result.get("v"), dict):
                                        response_data = result["v"].get(
                                            "response", {})
                                        fragments = response_data.get(
                                            "fragments", [])
                                        if isinstance(fragments, list):
                                            for fragment in fragments:
                                                if isinstance(fragment, dict):
                                                    fragment_content = fragment.get(
                                                        "content", "")
                                                    if fragment_content:
                                                        content_to_send += fragment_content

                                    if isinstance(result.get("v"), list):
                                        for item in result["v"]:
                                            if isinstance(
                                                    item, dict) and isinstance(
                                                        item.get("v"), list):
                                                content_to_send = "".join(
                                                    v.get("content", "")
                                                    for v in item["v"]
                                                    if isinstance(
                                                        v, dict)).replace(
                                                            "FINISHED", "")

                                    if isinstance(result.get("v"), str):
                                        content_to_send = result["v"].replace(
                                            "FINISHED", "")

                                    if content_to_send:
                                        delta = {}
                                        if current_path == "thinking":
                                            delta[
                                                "reasoning_content"] = content_to_send
                                        else:
                                            delta["content"] = content_to_send

                                        yield ChatCompletionChunk(
                                            id=f"{session_id}@{message_id}",
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

                            return
                finally:
                    # 如果是新创建的会话，在流式输出完成后自动删除
                    if is_new_session:
                        try:
                            await self.delete_session(session_id)
                        except Exception:
                            # 删除失败不影响主流程
                            pass

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
    search_enabled: bool = False,
    thinking_enabled: bool = False,
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
        search_enabled: 是否启用联网搜索
        thinking_enabled: 是否启用深度思考
        **kwargs: 其他参数传递给 DeepSeekClient

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
                    search_enabled=search_enabled,
                    thinking_enabled=thinking_enabled,
            ):
                yield chunk

        return stream_generator()
    else:
        return await client.create_completion(
            messages=messages,
            model=model,
            conversation_id=conversation_id,
            search_enabled=search_enabled,
            thinking_enabled=thinking_enabled,
        )
