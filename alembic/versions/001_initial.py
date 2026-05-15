"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create equipment table
    op.create_table(
        "equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("equipment_type", sa.String(50), nullable=False),
        sa.Column("manufacturer", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="UNKNOWN"),
        sa.Column("sub_status", sa.String(50), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_equipment_type_status", "equipment", ["equipment_type", "status"], unique=False
    )

    # Create equipment_status_history table
    op.create_table(
        "equipment_status_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "equipment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sub_status", sa.String(50), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_equipment_status_history_timestamp", "equipment_status_history", ["timestamp"], unique=False
    )
    op.create_index(
        "ix_equipment_status_timestamp", "equipment_status_history", ["equipment_id", "timestamp"], unique=False
    )

    # Create recipe table
    op.create_table(
        "recipe",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("equipment_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("fdc_limits", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["recipe.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipe_equipment_type", "recipe", ["equipment_type"], unique=False)
    op.create_index(
        "ix_recipe_equipment_active", "recipe", ["equipment_type", "is_active"], unique=False
    )

    # Create work_order table
    op.create_table(
        "work_order",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mes_id", sa.String(100), nullable=False),
        sa.Column("lot_id", sa.String(100), nullable=False),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_equipment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("wafer_count", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipe.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_equipment_id"],
            ["equipment.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mes_id"),
    )
    op.create_index("ix_work_order_mes_id", "work_order", ["mes_id"], unique=True)
    op.create_index("ix_work_order_lot_id", "work_order", ["lot_id"], unique=False)
    op.create_index("ix_work_order_status", "work_order", ["status"], unique=False)
    op.create_index(
        "ix_workorder_status_created", "work_order", ["status", "created_at"], unique=False
    )

    # Create alarm table
    op.create_table(
        "alarm",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "equipment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("alarm_code", sa.String(50), nullable=False),
        sa.Column("alarm_text", sa.String(500), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("raised_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_by", sa.String(100), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("cleared_by", sa.String(100), nullable=True),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alarm_equipment_id", "alarm", ["equipment_id"], unique=False)
    op.create_index("ix_alarm_severity", "alarm", ["severity"], unique=False)
    op.create_index("ix_alarm_raised_at", "alarm", ["raised_at"], unique=False)
    op.create_index(
        "ix_alarm_equipment_raised", "alarm", ["equipment_id", "raised_at"], unique=False
    )
    op.create_index(
        "ix_alarm_severity_raised", "alarm", ["severity", "raised_at"], unique=False
    )

    # Create carrier table
    op.create_table(
        "carrier",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("carrier_id", sa.String(100), nullable=False),
        sa.Column("carrier_type", sa.String(20), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("current_location", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="IDLE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carrier_id"),
    )
    op.create_index("ix_carrier_carrier_id", "carrier", ["carrier_id"], unique=True)
    op.create_index("ix_carrier_status", "carrier", ["status"], unique=False)

    # Create wafer_event table
    op.create_table(
        "wafer_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wafer_id", sa.String(100), nullable=False),
        sa.Column("lot_id", sa.String(100), nullable=False),
        sa.Column("carrier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chamber_id", sa.String(50), nullable=True),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("wafer_position", sa.Integer(), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["carrier_id"],
            ["carrier.id"],
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipment.id"],
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipe.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wafer_event_wafer_id", "wafer_event", ["wafer_id"], unique=False)
    op.create_index("ix_wafer_event_lot_id", "wafer_event", ["lot_id"], unique=False)
    op.create_index("ix_wafer_event_event_type", "wafer_event", ["event_type"], unique=False)
    op.create_index("ix_wafer_event_timestamp", "wafer_event", ["timestamp"], unique=False)
    op.create_index(
        "ix_wafer_lot_timestamp", "wafer_event", ["lot_id", "timestamp"], unique=False
    )

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"], unique=False)
    op.create_index(
        "ix_audit_user_timestamp", "audit_log", ["user_id", "timestamp"], unique=False
    )
    op.create_index(
        "ix_audit_resource_timestamp", "audit_log", ["resource_type", "resource_id", "timestamp"], unique=False
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("wafer_event")
    op.drop_table("carrier")
    op.drop_table("alarm")
    op.drop_table("work_order")
    op.drop_table("recipe")
    op.drop_table("equipment_status_history")
    op.drop_table("equipment")
