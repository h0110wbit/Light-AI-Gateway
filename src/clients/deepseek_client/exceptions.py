"""
DeepSeek Client 异常定义
"""


class DeepSeekException(Exception):
    """DeepSeek 客户端基础异常类"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


class APIException(DeepSeekException):
    """API 请求异常"""

    def __init__(self, errcode: int = -2001, errmsg: str = "请求失败"):
        super().__init__(errcode, errmsg)


class TokenExpiredException(APIException):
    """Token 过期异常"""

    def __init__(self, errmsg: str = "Token已失效"):
        super().__init__(-2002, errmsg)


class RequestFailedException(APIException):
    """请求失败异常"""

    def __init__(self, errmsg: str = "请求失败"):
        super().__init__(-2001, errmsg)


class ThinkingQuotaException(APIException):
    """深度思考配额不足异常"""

    def __init__(self, errmsg: str = "深度思考配额不足"):
        super().__init__(-2001, errmsg)
