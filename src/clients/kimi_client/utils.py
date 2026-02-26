"""
Kimi Client 工具函数
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


def generate_random_string(length: int = 10, charset: str = "numeric") -> str:
    """
    生成随机字符串

    Args:
        length: 长度
        charset: 字符集类型

    Returns:
        随机字符串
    """
    if charset == "numeric":
        return "".join(random.choices("0123456789", k=length))
    elif charset == "alphabetic":
        return "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=length))
    elif charset == "alphanumeric":
        return "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=length))
    else:
        return "".join(
            random.choices(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                k=length))


def generate_cookie() -> str:
    """
    生成伪装 Cookie

    Returns:
        Cookie 字符串
    """
    timestamp = unix_timestamp()
    items = [
        f"Hm_lvt_358cae4815e85d48f7e8ab7f3680a74b={timestamp - random.randint(0, 2592000)}",
        f"_ga=GA1.1.{generate_random_string(10, 'numeric')}.{timestamp - random.randint(0, 2592000)}",
        f"_ga_YXD8W70SZP=GS1.1.{timestamp - random.randint(0, 2592000)}.1.1.{timestamp - random.randint(0, 2592000)}.0.0.0",
        f"Hm_lpvt_358cae4815e85d48f7e8ab7f3680a74b={timestamp - random.randint(0, 2592000)}"
    ]
    return "; ".join(items)


def get_random_user_agent() -> str:
    """
    获取随机 User-Agent

    Returns:
        随机 User-Agent 字符串
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    ]
    return random.choice(user_agents)


def get_base_headers() -> dict:
    """
    获取基础请求头

    Returns:
        请求头字典
    """
    return {
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Origin": "https://kimi.moonshot.cn",
        "Cookie": generate_cookie(),
        "R-Timezone": "Asia/Shanghai",
        "Sec-Ch-Ua":
        '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": get_random_user_agent(),
        "Priority": "u=1, i",
    }


def wrap_urls_to_tags(content: str) -> str:
    """
    将消息中的 URL 包装为 HTML 标签

    kimi 网页版中会自动将 url 包装为 url 标签用于处理状态，
    此处也得模仿处理，否则无法成功解析

    Args:
        content: 消息内容

    Returns:
        处理后的内容
    """
    url_pattern = r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)'
    return re.sub(
        url_pattern,
        lambda m:
        f'<url id="" type="url" status="" title="" wc="">{m.group(0)}</url>',
        content,
        flags=re.IGNORECASE)


def is_base64_data(url: str) -> bool:
    """
    检查是否为 base64 数据

    Args:
        url: URL 字符串

    Returns:
        是否为 base64 数据
    """
    return url.startswith("data:")


def extract_base64_format(url: str) -> str:
    """
    提取 base64 数据的格式

    Args:
        url: base64 URL

    Returns:
        MIME 类型
    """
    if not is_base64_data(url):
        return ""
    match = re.match(r'data:([^;]+);base64,', url)
    return match.group(1) if match else ""


def remove_base64_header(url: str) -> str:
    """
    移除 base64 数据的头部

    Args:
        url: base64 URL

    Returns:
        纯 base64 数据
    """
    if not is_base64_data(url):
        return url
    match = re.match(r'data:[^;]+;base64,(.+)', url)
    return match.group(1) if match else url


def detect_token_type(token: str) -> str:
    """
    检测 Token 类型

    Args:
        token: Token 字符串

    Returns:
        'jwt' 或 'refresh'
    """
    if token.startswith('eyJ') and len(token.split('.')) == 3:
        try:
            import base64
            import json
            payload = json.loads(
                base64.b64decode(token.split('.')[1] + '==').decode('utf-8'))
            if payload.get('app_id') == 'kimi' and payload.get(
                    'typ') == 'access':
                return 'jwt'
        except Exception:
            pass
    return 'refresh'


def extract_device_id_from_jwt(token: str) -> Optional[str]:
    """
    从 JWT Token 中提取设备 ID

    Args:
        token: JWT Token

    Returns:
        设备 ID
    """
    try:
        import base64
        import json
        payload = json.loads(
            base64.b64decode(token.split('.')[1] + '==').decode('utf-8'))
        return payload.get('device_id')
    except Exception:
        return None


def extract_session_id_from_jwt(token: str) -> Optional[str]:
    """
    从 JWT Token 中提取会话 ID

    Args:
        token: JWT Token

    Returns:
        会话 ID
    """
    try:
        import base64
        import json
        payload = json.loads(
            base64.b64decode(token.split('.')[1] + '==').decode('utf-8'))
        return payload.get('ssid')
    except Exception:
        return None


def extract_user_id_from_jwt(token: str) -> Optional[str]:
    """
    从 JWT Token 中提取用户 ID

    Args:
        token: JWT Token

    Returns:
        用户 ID
    """
    try:
        import base64
        import json
        payload = json.loads(
            base64.b64decode(token.split('.')[1] + '==').decode('utf-8'))
        return payload.get('sub')
    except Exception:
        return None
