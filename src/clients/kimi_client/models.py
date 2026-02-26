"""
Kimi Client 数据模型
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str
    content: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        """从字典创建"""
        return cls(
            role=data.get("role", ""),
            content=data.get("content", ""),
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
    model: str = "kimi"
    object: str = "chat.completion"
    choices: List[ChatChoice] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)
    created: int = 0
    segment_id: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "model": self.model,
            "object": self.object,
            "choices": [c.to_dict() for c in self.choices],
            "usage": self.usage.to_dict(),
            "created": self.created,
        }
        if self.segment_id:
            result["segment_id"] = self.segment_id
        return result

    def get_content(self) -> str:
        """获取响应内容"""
        if self.choices and self.choices[0].message:
            return self.choices[0].message.content
        return ""


@dataclass
class ChatCompletionChunk:
    """聊天补全流式块"""

    id: str = ""
    model: str = "kimi"
    object: str = "chat.completion.chunk"
    choices: List[ChatChoice] = field(default_factory=list)
    created: int = 0
    segment_id: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "id": self.id,
            "model": self.model,
            "object": self.object,
            "choices": [c.to_dict() for c in self.choices],
            "created": self.created,
        }
        if self.segment_id:
            result["segment_id"] = self.segment_id
        return result


@dataclass
class TokenInfo:
    """Token 信息"""

    access_token: str
    refresh_token: str
    user_id: str = ""
    refresh_time: int = 0


@dataclass
class FileUploadResult:
    """文件上传结果"""

    id: str
    name: str
    size: int
    status: str = ""
