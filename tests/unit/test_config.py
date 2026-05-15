"""Tests for core configuration module"""
import pytest
from pathlib import Path

from myeap.core.config import (
    Settings,
    DatabaseSettings,
    RedisSettings,
    KafkaSettings,
    MESAdapterSettings,
    SecsSettings,
    SecuritySettings,
)


class TestDatabaseSettings:
    """Test DatabaseSettings"""

    def test_default_values(self):
        settings = DatabaseSettings()
        assert settings.host == "localhost"
        assert settings.port == 5432
        assert settings.name == "myeap"
        assert settings.user == "myeap"
        assert settings.pool_size == 20

    def test_url_property(self):
        settings = DatabaseSettings(
            host="db.example.com",
            port=5433,
            name="testdb",
            user="testuser",
            password="secret",
        )
        expected = "postgresql+asyncpg://testuser:secret@db.example.com:5433/testdb"
        assert settings.url == expected


class TestRedisSettings:
    """Test RedisSettings"""

    def test_default_values(self):
        settings = RedisSettings()
        assert settings.host == "localhost"
        assert settings.port == 6379
        assert settings.db == 0
        assert settings.pool_size == 50


class TestKafkaSettings:
    """Test KafkaSettings"""

    def test_default_values(self):
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "localhost:9092"
        assert settings.consumer_group == "myeap"
        assert settings.auto_offset_reset == "earliest"


class TestMESAdapterSettings:
    """Test MESAdapterSettings"""

    def test_default_values(self):
        settings = MESAdapterSettings()
        assert settings.mqtt_broker == "localhost:1883"
        assert settings.rest_endpoint == "http://localhost:8001"


class TestSecsSettings:
    """Test SecsSettings"""

    def test_default_values(self):
        settings = SecsSettings()
        assert settings.default_timeout == 10
        assert settings.reconnect_interval == 5
        assert settings.max_retries == 3


class TestSecuritySettings:
    """Test SecuritySettings"""

    def test_default_values(self):
        settings = SecuritySettings()
        assert settings.secret_key == "change-me-in-production"
        assert settings.algorithm == "HS256"
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 7


class TestSettings:
    """Test main Settings"""

    def test_default_values(self):
        settings = Settings()
        assert settings.app_name == "MyEAP"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"

    def test_ensure_dirs_creates_directories(self, tmp_path):
        """Test that ensure_dirs creates data and log directories"""
        data_dir = tmp_path / "data"
        log_dir = tmp_path / "logs"

        settings = Settings()
        settings.base_dir = tmp_path
        settings.data_dir = data_dir
        settings.log_dir = log_dir

        settings.ensure_dirs()

        assert data_dir.exists()
        assert log_dir.exists()
        assert data_dir.is_dir()
        assert log_dir.is_dir()

    def test_submodules_initialized(self):
        """Test that all submodule settings are initialized"""
        settings = Settings()
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.redis, RedisSettings)
        assert isinstance(settings.kafka, KafkaSettings)
        assert isinstance(settings.mes, MESAdapterSettings)
        assert isinstance(settings.secs, SecsSettings)
        assert isinstance(settings.security, SecuritySettings)
