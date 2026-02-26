"""
Kimi Client 异常定义
"""


class KimiException(Exception):
    """Kimi 客户端基础异常类"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


class APIException(KimiException):
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


class FileURLException(APIException):
    """文件 URL 非法异常"""

    def __init__(self, errmsg: str = "远程文件URL非法"):
        super().__init__(-2003, errmsg)


class FileSizeExceededException(APIException):
    """文件超出大小异常"""

    def __init__(self, errmsg: str = "远程文件超出大小"):
        super().__init__(-2004, errmsg)


class StreamPushingException(APIException):
    """已有对话流正在输出异常"""

    def __init__(self, errmsg: str = "已有对话流正在输出"):
        super().__init__(-2005, errmsg)


class ResearchQuotaExceededException(APIException):
    """探索版使用量已达到上限异常"""

    def __init__(self, errmsg: str = "探索版使用量已达到上限"):
        super().__init__(-2006, errmsg)
