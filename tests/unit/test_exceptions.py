"""Tests for core exceptions module"""
import pytest

from myeap.core.exceptions import (
    MyEAPException,
    ConfigurationError,
    DatabaseError,
    ConnectionError,
    EquipmentError,
    ProtocolError,
    RecipeError,
    AlarmError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    WorkOrderError,
    TrackingError,
    SPCError,
    FDCError,
)


class TestMyEAPException:
    """Test MyEAPException base class"""

    def test_basic_exception(self):
        exc = MyEAPException("Test error")
        assert exc.message == "Test error"
        assert exc.code == "EAP_ERROR"
        assert exc.details == {}

    def test_exception_with_code(self):
        exc = MyEAPException("Test error", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"

    def test_exception_with_details(self):
        details = {"key": "value", "count": 42}
        exc = MyEAPException("Test error", details=details)
        assert exc.details == details


class TestEquipmentError:
    """Test EquipmentError"""

    def test_equipment_error_with_id(self):
        exc = EquipmentError("Equipment malfunction", equipment_id="EQ-001")
        assert exc.equipment_id == "EQ-001"
        assert exc.message == "Equipment malfunction"

    def test_equipment_error_without_id(self):
        exc = EquipmentError("Generic equipment error")
        assert exc.equipment_id is None

    def test_equipment_error_with_code_and_details(self):
        """Test EquipmentError with custom code and details"""
        exc = EquipmentError(
            "Equipment malfunction",
            equipment_id="EQ-002",
            code="EQ_MALFUNC",
            details={"component": "sensor", "severity": "high"},
        )
        assert exc.equipment_id == "EQ-002"
        assert exc.code == "EQ_MALFUNC"
        assert exc.details == {"component": "sensor", "severity": "high"}


class TestExceptionInheritance:
    """Test exception inheritance hierarchy"""

    def test_all_exceptions_inherit_from_my_eap_exception(self):
        """Test that all domain exceptions can be caught as MyEAPException"""
        exception_classes = [
            ConfigurationError,
            DatabaseError,
            ConnectionError,
            EquipmentError,
            ProtocolError,
            RecipeError,
            AlarmError,
            AuthenticationError,
            AuthorizationError,
            ValidationError,
            WorkOrderError,
            TrackingError,
            SPCError,
            FDCError,
        ]

        for exc_class in exception_classes:
            exc = exc_class("test message")
            assert isinstance(exc, MyEAPException)

    def test_all_exceptions_can_be_caught_together(self):
        """Test that all exceptions can be caught using MyEAPException"""
        exceptions = [
            ConfigurationError("config error"),
            DatabaseError("db error"),
            ConnectionError("conn error"),
            EquipmentError("equip error"),
            ProtocolError("protocol error"),
            RecipeError("recipe error"),
            AlarmError("alarm error"),
            AuthenticationError("auth error"),
            AuthorizationError("authz error"),
            ValidationError("validation error"),
            WorkOrderError("workorder error"),
            TrackingError("tracking error"),
            SPCError("spc error"),
            FDCError("fdc error"),
        ]

        for exc in exceptions:
            # All should be catchable as MyEAPException
            assert isinstance(exc, MyEAPException)
            # And as base Exception
            assert isinstance(exc, Exception)


class TestExceptionCodesAndDetails:
    """Test exception codes and details functionality"""

    def test_default_code(self):
        """Test that exceptions have correct default codes"""
        assert MyEAPException("test").code == "EAP_ERROR"

    def test_custom_code_is_preserved(self):
        """Test that custom codes are preserved"""
        exc = MyEAPException("test", code="CUSTOM")
        assert exc.code == "CUSTOM"

    def test_default_details_is_empty_dict(self):
        """Test that default details is an empty dict"""
        exc = MyEAPException("test")
        assert exc.details == {}

    def test_details_are_preserved(self):
        """Test that details dict is preserved"""
        details = {"key1": "value1", "key2": 123, "nested": {"a": 1}}
        exc = MyEAPException("test", details=details)
        assert exc.details == details
        assert exc.details["nested"] == {"a": 1}

    def test_exception_message_matches_first_arg(self):
        """Test that message attribute matches the first argument"""
        msg = "This is the error message"
        exc = MyEAPException(msg)
        assert exc.message == msg


class TestSpecificExceptions:
    """Test all specific exception types"""

    @pytest.mark.parametrize(
        "exception_class",
        [
            ConfigurationError,
            DatabaseError,
            ConnectionError,
            ProtocolError,
            RecipeError,
            AlarmError,
            AuthenticationError,
            AuthorizationError,
            ValidationError,
            WorkOrderError,
            TrackingError,
            SPCError,
            FDCError,
        ],
    )
    def test_exception_is_raised(self, exception_class):
        exc = exception_class("Test message")
        assert isinstance(exc, MyEAPException)
        assert exc.message == "Test message"
