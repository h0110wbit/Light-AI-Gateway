"""
Qwen Client 异常定义
通义千问客户端的异常类定义
"""


class QwenException(Exception):
    """Qwen 客户端基础异常类"""

    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


class APIException(QwenException):
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


class ContentFilteredException(APIException):
    """内容被过滤异常"""

    def __init__(self, errmsg: str = "内容由于合规问题已被阻止生成"):
        super().__init__(-2006, errmsg)


class FileURLException(APIException):
    """文件 URL 非法异常"""

    def __init__(self, errmsg: str = "远程文件URL非法"):
        super().__init__(-2003, errmsg)


class FileSizeExceededException(APIException):
    """文件大小超出限制异常"""

    def __init__(self, errmsg: str = "文件大小超出限制"):
        super().__init__(-2004, errmsg)
