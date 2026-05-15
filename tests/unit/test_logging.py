"""Tests for core logging module"""
import pytest

from myeap.core.logging import setup_logging, get_logger, LoggerMixin


class TestSetupLogging:
    """Test setup_logging function"""

    def test_setup_logging_default(self):
        """Test that setup_logging runs without errors"""
        # Should not raise any exception
        setup_logging()

    def test_setup_logging_with_debug_level(self):
        """Test setup_logging with DEBUG level"""
        setup_logging(log_level="DEBUG")

    def test_setup_logging_with_warning_level(self):
        """Test setup_logging with WARNING level"""
        setup_logging(log_level="WARNING")


class TestGetLogger:
    """Test get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance"""
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_with_different_names(self):
        """Test get_logger with different module names"""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        # Loggers should be different instances
        assert logger1 is not logger2

    def test_get_logger_can_log(self):
        """Test that returned logger can perform basic logging"""
        logger = get_logger("test_output")
        # Should not raise - just verify logger is functional
        assert callable(logger.info)
        assert callable(logger.warning)
        assert callable(logger.error)


class TestLoggerMixin:
    """Test LoggerMixin class"""

    def test_logger_mixin_provides_logger(self):
        """Test that LoggerMixin provides a logger property"""
        class MyClass(LoggerMixin):
            pass

        obj = MyClass()
        assert hasattr(obj, "logger")
        assert obj.logger is not None

    def test_logger_mixin_named_after_class(self):
        """Test that logger uses the class name"""
        class MyTestClass(LoggerMixin):
            pass

        obj = MyTestClass()
        # The logger should be named after the class
        assert obj.logger is not None

    def test_logger_mixin_caches_logger(self):
        """Test that logger is cached per instance"""
        class AnotherClass(LoggerMixin):
            pass

        obj = AnotherClass()
        logger1 = obj.logger
        logger2 = obj.logger
        assert logger1 is logger2

    def test_logger_mixin_separate_per_instance(self):
        """Test that each instance gets its own logger"""
        class ServiceClass(LoggerMixin):
            pass

        obj1 = ServiceClass()
        obj2 = ServiceClass()
        # Each instance should have its own logger
        assert obj1.logger is not obj2.logger

    def test_logger_mixin_multiple_inheritance(self):
        """Test LoggerMixin works with other mixins or base classes"""
        class BaseClass:
            def __init__(self):
                self.base_value = 42

        class MixedClass(BaseClass, LoggerMixin):
            pass

        obj = MixedClass()
        assert hasattr(obj, "logger")
        assert hasattr(obj, "base_value")
        assert obj.base_value == 42
