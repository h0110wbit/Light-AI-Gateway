"""
Qwen Client 数据模型
通义千问客户端的数据模型定义
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
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
    model: str = "qwen"
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


@dataclass
class ChatCompletionChunk:
    """聊天补全流式响应块"""

    id: str = ""
    model: str = "qwen"
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
class FileUploadResult:
    """文件上传结果"""

    role: str = "user"
    content_type: str = "file"
    content: str = ""
    ext: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "role": self.role,
            "contentType": self.content_type,
            "content": self.content,
        }
        if self.ext:
            result["ext"] = self.ext
        return result


@dataclass
class UploadParams:
    """上传参数"""

    access_id: str = ""
    policy: str = ""
    signature: str = ""
    dir: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "UploadParams":
        """从字典创建"""
        return cls(
            access_id=data.get("accessId", ""),
            policy=data.get("policy", ""),
            signature=data.get("signature", ""),
            dir=data.get("dir", ""),
        )


@dataclass
class ModelInfo:
    """模型信息"""

    id: str
    name: str
    object: str = "model"
    owned_by: str = "qwen-free-api"
    description: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "object": self.object,
            "owned_by": self.owned_by,
            "description": self.description,
        }


# 支持的模型列表
SUPPORTED_MODELS = [
    ModelInfo(
        id="qwen3-235b-a22b",
        name="Qwen3-235B-A22B-2507",
        description="最强大的混合专家语言模型，支持思维预算机制"
    ),
    ModelInfo(
        id="qwen3-coder-plus",
        name="Qwen3-Coder",
        description="强大的编程专用语言模型，擅长代码生成和工具使用"
    ),
    ModelInfo(
        id="qwen3-30b-a3b",
        name="Qwen3-30B-A3B-2507",
        description="紧凑高性能的混合专家模型"
    ),
    ModelInfo(
        id="qwen3-coder-30b-a3b-instruct",
        name="Qwen3-Coder-Flash",
        description="快速准确的代码生成模型"
    ),
    ModelInfo(
        id="qwen-max-latest",
        name="Qwen2.5-Max",
        description="Qwen系列中最强大的语言模型"
    ),
]

# 默认模型
DEFAULT_MODEL = "qwen3-235b-a22b"


def is_valid_model(model_id: str) -> bool:
    """验证模型是否支持"""
    return any(model.id == model_id for model in SUPPORTED_MODELS)


def get_model_list() -> List[ModelInfo]:
    """获取支持的模型列表"""
    return SUPPORTED_MODELS.copy()
