"""
MiniMax Client 异常定义
MiniMax 客户端异常类定义
"""


class MiniMaxException(Exception):
    """MiniMax 客户端基础异常类"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


class APIException(MiniMaxException):
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
    """文件 URL 无效异常"""

    def __init__(self, errmsg: str = "文件URL无效"):
        super().__init__(-2003, errmsg)


class FileSizeExceededException(APIException):
    """文件大小超出限制异常"""

    def __init__(self, errmsg: str = "文件大小超出限制"):
        super().__init__(-2004, errmsg)
