"""
GLM Client 工具函数
"""
import uuid
import hashlib
import time
import random
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


def md5_hash(value: str) -> str:
    """
    计算 MD5 哈希值

    Args:
        value: 待哈希的字符串

    Returns:
        MD5 哈希值
    """
    return hashlib.md5(value.encode("utf-8")).hexdigest()


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


def generate_sign(
        sign_secret: str = "8a1317a7468aa3ad86e997d08f3f31cb") -> dict:
    """
    生成智谱 API 签名

    Args:
        sign_secret: 签名密钥

    Returns:
        包含 timestamp, nonce, sign 的字典
    """
    e = int(time.time() * 1000)
    A = str(e)
    t = len(A)
    o = [int(c) for c in A]
    i = sum(o) - o[t - 2]
    a = i % 10
    timestamp = A[:t - 2] + str(a) + A[t - 1:]
    nonce = generate_uuid(separator=False)
    sign = md5_hash(f"{timestamp}-{nonce}-{sign_secret}")
    return {"timestamp": timestamp, "nonce": nonce, "sign": sign}


def get_random_user_agent() -> str:
    """
    获取随机 User-Agent

    Returns:
        随机 User-Agent 字符串
    """
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    ]
    return random.choice(user_agents)


def get_base_headers() -> dict:
    """
    获取基础请求头

    Returns:
        请求头字典
    """
    return {
        "Accept": "text/event-stream",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "App-Name": "chatglm",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": "https://chatglm.cn",
        "Pragma": "no-cache",
        "Priority": "u=1, i",
        "Sec-Ch-Ua":
        '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-App-Fr": "browser_extension",
        "X-App-Platform": "pc",
        "X-App-Version": "0.0.1",
        "X-Device-Brand": "",
        "X-Device-Model": "",
        "X-Lang": "zh",
        "User-Agent": get_random_user_agent(),
    }


def is_base64_data(value: str) -> bool:
    """
    检查是否为 BASE64 数据

    Args:
        value: 待检查的字符串

    Returns:
        是否为 BASE64 数据
    """
    return value.startswith("data:")


def extract_base64_format(value: str) -> Optional[str]:
    """
    提取 BASE64 数据格式

    Args:
        value: BASE64 数据字符串

    Returns:
        数据格式（如 image/png）
    """
    import re

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
        纯 BASE64 数据
    """
    import re

    return re.sub(r"^data:(.+);base64,", "", value)
