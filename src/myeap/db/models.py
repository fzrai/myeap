"""SQLAlchemy ORM模型定义"""
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class Equipment(Base):
    """设备模型"""
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    sub_status: Mapped[Optional[str]] = mapped_column(String(50))
    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    status_history: Mapped[List["EquipmentStatusHistory"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    alarms: Mapped[List["Alarm"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    work_orders: Mapped[List["WorkOrder"]] = relationship(
        back_populates="target_equipment"
    )

    __table_args__ = (
        Index("ix_equipment_type_status", "equipment_type", "status"),
    )


class EquipmentStatusHistory(Base):
    """设备状态历史"""
    __tablename__ = "equipment_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sub_status: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    equipment: Mapped["Equipment"] = relationship(back_populates="status_history")

    __table_args__ = (
        Index("ix_equipment_status_timestamp", "equipment_id", "timestamp"),
    )


class Recipe(Base):
    """配方模型"""
    __tablename__ = "recipe"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    equipment_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipe.id")
    )
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    steps: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fdc_limits: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    parent_version: Mapped[Optional["Recipe"]] = relationship(
        "Recipe", remote_side=[id], backref="child_versions"
    )
    work_orders: Mapped[List["WorkOrder"]] = relationship(back_populates="recipe")

    __table_args__ = (
        Index("ix_recipe_equipment_active", "equipment_type", "is_active"),
    )


class WorkOrder(Base):
    """工单模型"""
    __tablename__ = "work_order"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mes_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    lot_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    recipe_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipe.id")
    )
    target_equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id")
    )
    wafer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)

    recipe: Mapped[Optional["Recipe"]] = relationship(back_populates="work_orders")
    target_equipment: Mapped[Optional["Equipment"]] = relationship(
        back_populates="work_orders"
    )

    __table_args__ = (
        Index("ix_workorder_status_created", "status", "created_at"),
    )


class Alarm(Base):
    """报警模型"""
    __tablename__ = "alarm"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id"), nullable=False, index=True
    )
    alarm_code: Mapped[str] = mapped_column(String(50), nullable=False)
    alarm_text: Mapped[Optional[str]] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    raised_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cleared_by: Mapped[Optional[str]] = mapped_column(String(100))
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    equipment: Mapped["Equipment"] = relationship(back_populates="alarms")

    __table_args__ = (
        Index("ix_alarm_equipment_raised", "equipment_id", "raised_at"),
        Index("ix_alarm_severity_raised", "severity", "raised_at"),
    )


class Carrier(Base):
    """载具模型"""
    __tablename__ = "carrier"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    carrier_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    carrier_type: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    current_location: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="IDLE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class WaferEvent(Base):
    """晶圆事件模型"""
    __tablename__ = "wafer_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wafer_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lot_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    carrier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carrier.id")
    )
    equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id")
    )
    chamber_id: Mapped[Optional[str]] = mapped_column(String(50))
    recipe_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipe.id")
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    wafer_position: Mapped[Optional[int]] = mapped_column(Integer)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB)
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    __table_args__ = (
        Index("ix_wafer_lot_timestamp", "lot_id", "timestamp"),
    )


class AuditLog(Base):
    """审计日志模型"""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    __table_args__ = (
        Index("ix_audit_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_resource_timestamp", "resource_type", "resource_id", "timestamp"),
    )
