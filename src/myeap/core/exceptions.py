"""自定义异常定义"""
from typing import Any, Optional


class MyEAPException(Exception):
    """基础异常类"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "EAP_ERROR"
        self.details = details or {}


class ConfigurationError(MyEAPException):
    """配置错误"""
    pass


class DatabaseError(MyEAPException):
    """数据库错误"""
    pass


class ConnectionError(MyEAPException):
    """连接错误"""
    pass


class EquipmentError(MyEAPException):
    """设备错误"""

    def __init__(
        self,
        message: str,
        equipment_id: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(message, **kwargs)
        self.equipment_id = equipment_id


class ProtocolError(MyEAPException):
    """协议错误"""
    pass


class RecipeError(MyEAPException):
    """配方错误"""
    pass


class AlarmError(MyEAPException):
    """报警错误"""
    pass


class AuthenticationError(MyEAPException):
    """认证错误"""
    pass


class AuthorizationError(MyEAPException):
    """授权错误"""
    pass


class ValidationError(MyEAPException):
    """验证错误"""
    pass


class WorkOrderError(MyEAPException):
    """工单错误"""
    pass


class TrackingError(MyEAPException):
    """追踪错误"""
    pass


class SPCError(MyEAPException):
    """SPC错误"""
    pass


class FDCError(MyEAPException):
    """FDC错误"""
    pass
