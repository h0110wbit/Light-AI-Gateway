"""
GLM Client 数据模型
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import Enum


class MessageRole(Enum):
    """消息角色枚举"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str
    content: str
    reasoning_content: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {"role": self.role, "content": self.content}
        if self.reasoning_content:
            result["reasoning_content"] = self.reasoning_content
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """从字典创建"""
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
            reasoning_content=data.get("reasoning_content"),
        )


@dataclass
class ChatChoice:
    """聊天选择"""

    index: int = 0
    message: Optional[ChatMessage] = None
    delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {"index": self.index}
        if self.message:
            result["message"] = self.message.to_dict()
        if self.delta:
            result["delta"] = self.delta
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        return result


@dataclass
class UsageInfo:
    """使用量信息"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class ChatCompletionResponse:
    """聊天补全响应"""

    id: str = ""
    model: str = "glm"
    object: str = "chat.completion"
    choices: List[ChatChoice] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)
    created: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "model": self.model,
            "object": self.object,
            "choices": [c.to_dict() for c in self.choices],
            "usage": self.usage.to_dict(),
            "created": self.created,
        }

    def get_content(self) -> str:
        """获取响应内容"""
        if self.choices and self.choices[0].message:
            return self.choices[0].message.content
        return ""

    def get_reasoning_content(self) -> Optional[str]:
        """获取推理内容"""
        if self.choices and self.choices[0].message:
            return self.choices[0].message.reasoning_content
        return None


@dataclass
class ChatCompletionChunk:
    """聊天补全流式响应块"""

    id: str = ""
    model: str = "glm"
    object: str = "chat.completion.chunk"
    choices: List[ChatChoice] = field(default_factory=list)
    created: int = 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "model": self.model,
            "object": self.object,
            "choices": [c.to_dict() for c in self.choices],
            "created": self.created,
        }


@dataclass
class TokenInfo:
    """Token 信息"""

    access_token: str
    refresh_token: str
    refresh_time: int


@dataclass
class FileUploadResult:
    """文件上传结果"""

    file_id: Optional[str] = None
    file_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source_id: Optional[str] = None
