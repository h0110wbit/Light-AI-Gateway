"""
Qwen Client 工具函数
通义千问客户端的工具函数定义
"""
import uuid
import time
import random
import re
from typing import Optional


def generate_uuid(separator: bool = True) -> str:
    """
    生成 UUID

    Args:
        separator: 是否包含分隔符

    Returns:
        UUID 字符串
    """
    if separator:
        return str(uuid.uuid4())
    return uuid.uuid4().hex


def unix_timestamp() -> int:
    """
    获取当前 Unix 时间戳（秒）

    Returns:
        Unix 时间戳
    """
    return int(time.time())


def timestamp_ms() -> int:
    """
    获取当前毫秒时间戳

    Returns:
        毫秒时间戳
    """
    return int(time.time() * 1000)


def generate_random_string(length: int = 32, charset: str = "alphanumeric") -> str:
    """
    生成随机字符串

    Args:
        length: 字符串长度
        charset: 字符集类型 (alphanumeric, numeric, alphabetic)

    Returns:
        随机字符串
    """
    if charset == "numeric":
        chars = "0123456789"
    elif charset == "alphabetic":
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    else:
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    return "".join(random.choices(chars, k=length))


def generate_cookie(ticket: str) -> str:
    """
    生成 Cookies

    Args:
        ticket: tongyi_sso_ticket 或 login_aliyunid_ticket

    Returns:
        Cookie 字符串
    """
    # 根据 ticket 长度判断类型
    ticket_name = "login_aliyunid_ticket" if len(ticket) > 100 else "tongyi_sso_ticket"

    return "; ".join([
        f"{ticket_name}={ticket}",
        "aliyun_choice=intl",
        "_samesite_flag_=true",
        f"t={generate_uuid(separator=False)}",
    ])


def get_base_headers() -> dict:
    """
    获取基础请求头

    Returns:
        请求头字典
    """
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Origin": "https://tongyi.aliyun.com",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Referer": "https://tongyi.aliyun.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Platform": "pc_tongyi",
        "X-Xsrf-Token": "48b9ee49-a184-45e2-9f67-fa87213edcdc",
    }


def is_base64_data(value: str) -> bool:
    """
    检查是否为 BASE64 数据格式

    Args:
        value: 待检查的字符串

    Returns:
        是否为 BASE64 数据格式
    """
    return bool(value and value.startswith("data:"))


def extract_base64_format(value: str) -> Optional[str]:
    """
    提取 BASE64 数据格式

    Args:
        value: BASE64 数据字符串

    Returns:
        数据格式 (如 image/png)
    """
    if not value:
        return None
    match = re.match(r"^data:(.+);base64,", value.strip())
    if not match:
        return None
    return match.group(1)


def remove_base64_header(value: str) -> str:
    """
    移除 BASE64 数据头

    Args:
        value: BASE64 数据字符串

    Returns:
        纯 BASE64 编码字符串
    """
    return re.sub(r"^data:(.+);base64,", "", value)


def is_url(value: str) -> bool:
    """
    检查是否为 URL

    Args:
        value: 待检查的字符串

    Returns:
        是否为 URL
    """
    return bool(value and re.match(r"^(http|https)://", value))


def extract_url_extension(url: str) -> str:
    """
    从 URL 中提取文件扩展名

    Args:
        url: URL 字符串

    Returns:
        文件扩展名
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path
    if "." in path:
        return path.split(".")[-1].lower()
    return ""


def extract_ref_file_urls(messages: list) -> list:
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

    # 只获取最新的消息
    last_message = messages[-1]
    content = last_message.get("content", "")

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "")

            # glm-free-api 支持格式
            if item_type == "file" and isinstance(item.get("file_url"), dict):
                url = item["file_url"].get("url")
                if url:
                    urls.append(url)
            # 兼容 gpt-4-vision-preview API 格式
            elif item_type == "image_url" and isinstance(item.get("image_url"), dict):
                url = item["image_url"].get("url")
                if url:
                    urls.append(url)

    return urls


def messages_prepare(messages: list, refs: list = None, is_ref_conv: bool = False) -> list:
    """
    消息预处理

    由于接口只取第一条消息，此处会将多条消息合并为一条，实现多轮对话效果

    Args:
        messages: 消息列表
        refs: 参考文件列表
        is_ref_conv: 是否为引用会话

    Returns:
        处理后的消息列表
    """
    refs = refs or []

    if is_ref_conv or len(messages) < 2:
        # 透传模式：直接合并所有消息内容
        content_parts = []
        for message in messages:
            msg_content = message.get("content", "")
            if isinstance(msg_content, list):
                for item in msg_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        content_parts.append(item.get("text", ""))
            else:
                content_parts.append(str(msg_content))
        content = "\n".join(content_parts)
    else:
        # 对话合并模式：使用特殊标记分隔多轮对话
        content_parts = []
        for message in messages:
            msg_content = message.get("content", "")
            role = message.get("role", "user")

            if isinstance(msg_content, list):
                text_parts = []
                for item in msg_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                text = "\n".join(text_parts)
            else:
                text = str(msg_content)

            content_parts.append(f"<|im_start|>{role}\n{text}<|im_end|>")

        content = "".join(content_parts)
        # 移除图片链接
        content = re.sub(r"!\[.*\]\(.+\)", "", content)

    result = [{
        "content": content,
        "contentType": "text",
        "role": "user",
    }]

    if refs:
        result.extend(refs)

    return result


def clean_image_url(url: str) -> str:
    """
    清理图片 URL，移除查询参数

    Args:
        url: 图片 URL

    Returns:
        清理后的 URL
    """
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
