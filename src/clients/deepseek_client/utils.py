"""
DeepSeek Client 工具函数
"""
import uuid
import hashlib
import time
import random
import secrets
import asyncio
from typing import Optional
import os

# 尝试导入WASM求解器
try:
    from .wasm_solver import get_wasm_solver
    WASM_AVAILABLE = True
except ImportError:
    WASM_AVAILABLE = False
    print("警告: wasmtime库不可用，将使用备用算法")

# WASM文件路径
WASM_PATH = os.path.join(os.path.dirname(__file__),
                         "sha3_wasm_bg.7b9ca65ddd.wasm")


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


def generate_random_hex(length: int = 18) -> str:
    """
    生成随机十六进制字符串

    Args:
        length: 字符串长度

    Returns:
        随机十六进制字符串
    """
    return secrets.token_hex(length // 2 + 1)[:length]


def generate_cookie() -> str:
    """
    生成 Cookie

    Returns:
        Cookie 字符串
    """
    ts = unix_timestamp()
    return (f"intercom-HWWAFSESTIME={timestamp_ms()}; "
            f"HWWAFSESID={generate_random_hex(18)}; "
            f"Hm_lvt_{generate_uuid(separator=False)}={ts},{ts},{ts}; "
            f"Hm_lpvt_{generate_uuid(separator=False)}={ts}; "
            f"_frid={generate_uuid(separator=False)}; "
            f"_fr_ssid={generate_uuid(separator=False)}; "
            f"_fr_pvid={generate_uuid(separator=False)}")


def get_base_headers() -> dict:
    """
    获取基础请求头

    Returns:
        请求头字典
    """
    return {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://chat.deepseek.com",
        "Pragma": "no-cache",
        "Priority": "u=1, i",
        "Referer": "https://chat.deepseek.com/",
        "Sec-Ch-Ua":
        '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "X-App-Version": "20241129.1",
        "X-Client-Locale": "zh-CN",
        "X-Client-Platform": "web",
        "X-Client-Version": "1.6.1",
    }


async def solve_challenge(algorithm: str,
                          challenge: str,
                          salt: str,
                          difficulty: int,
                          expire_at: int = 0) -> int:
    """
    计算 Challenge 答案（POW）

    参考原项目challengeWorker.ts的实现：
    - 搜索范围：0 到 difficulty-1
    - 数据格式：{salt}_{expire_at}_{r}
    - 使用 SHA-256 哈希算法

    Args:
        algorithm: 算法名称
        challenge: 挑战字符串
        salt: 盐值
        difficulty: 难度
        expire_at: 过期时间戳

    Returns:
        答案值
    """
    if algorithm != "DeepSeekHashV1":
        raise ValueError(f"不支持的算法: {algorithm}")

    # 优先使用WASM求解器
    if WASM_AVAILABLE and os.path.exists(WASM_PATH):
        try:
            solver = await get_wasm_solver(WASM_PATH)
            answer = solver.calculate_hash(algorithm, challenge, salt,
                                           difficulty, expire_at)
            if answer is not None:
                return answer
        except Exception as e:
            print(f"WASM求解失败，使用备用算法: {e}")

    # 备用算法：使用SHA-256哈希算法（参考challengeWorker.ts）
    # 搜索范围：0 到 difficulty-1
    max_search = difficulty

    print(f"备用算法搜索: 难度={difficulty}, 搜索范围=0-{max_search-1}")

    for r in range(max_search):
        # 数据格式：{salt}_{expire_at}_{r}
        data = f"{salt}_{expire_at}_{r}"
        hash_result = hashlib.sha256(data.encode()).hexdigest()
        if hash_result == challenge:
            print(f"备用算法找到答案: {r}")
            return r

    print(f"备用算法未找到答案，搜索范围: 0-{max_search-1}")
    raise ValueError("未找到 Challenge 答案")


async def create_challenge_response(
    algorithm: str,
    challenge: str,
    salt: str,
    difficulty: int,
    expire_at: int,
    signature: str,
    target_path: str,
) -> str:
    """
    创建 Challenge 响应

    Args:
        algorithm: 算法名称
        challenge: 挑战字符串
        salt: 盐值
        difficulty: 难度
        expire_at: 过期时间
        signature: 签名
        target_path: 目标路径

    Returns:
        Base64 编码的响应
    """
    import base64
    import json

    answer = await solve_challenge(algorithm, challenge, salt, difficulty,
                                   expire_at)

    response_data = {
        "algorithm": algorithm,
        "challenge": challenge,
        "salt": salt,
        "answer": answer,
        "signature": signature,
        "target_path": target_path,
    }

    json_str = json.dumps(response_data)
    return base64.b64encode(json_str.encode()).decode()
