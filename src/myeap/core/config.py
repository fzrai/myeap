"""应用配置管理"""
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "myeap"
    user: str = "myeap"
    password: str = "changeme"
    pool_size: int = 20
    max_overflow: int = 10

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis配置"""
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    pool_size: int = 50


class KafkaSettings(BaseSettings):
    """Kafka配置"""
    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "myeap"
    auto_offset_reset: str = "earliest"


class MESAdapterSettings(BaseSettings):
    """MES适配器配置"""
    model_config = SettingsConfigDict(env_prefix="MES_")

    mqtt_broker: str = "localhost:1883"
    mqtt_username: str = ""
    mqtt_password: str = ""
    rest_endpoint: str = "http://localhost:8001"


class SecsSettings(BaseSettings):
    """SECS/GEM配置"""
    model_config = SettingsConfigDict(env_prefix="SECS_")

    default_timeout: int = 10
    reconnect_interval: int = 5
    max_retries: int = 3


class SecuritySettings(BaseSettings):
    """安全配置"""
    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    ldap_server: str = "ldap://localhost:389"
    ldap_base_dn: str = "dc=example,dc=com"


class Settings(BaseSettings):
    """应用主配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用信息
    app_name: str = "MyEAP"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # 路径配置
    base_dir: Path = Path(__file__).parent.parent.parent.parent
    data_dir: Path = base_dir / "data"
    log_dir: Path = base_dir / "logs"

    # 子模块配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    mes: MESAdapterSettings = Field(default_factory=MESAdapterSettings)
    secs: SecsSettings = Field(default_factory=SecsSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    def ensure_dirs(self) -> None:
        """确保必要目录存在"""
        for dir_path in [self.data_dir, self.log_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    settings = Settings()
    settings.ensure_dirs()
    return settings
