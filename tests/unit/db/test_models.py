"""Database models unit tests"""
import uuid
from datetime import datetime
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from myeap.db.models import (
    Alarm,
    AuditLog,
    Base,
    Carrier,
    Equipment,
    EquipmentStatusHistory,
    Recipe,
    WaferEvent,
    WorkOrder,
)


class TestEquipmentModel:
    """Tests for Equipment model"""

    def test_equipment_table_name(self):
        """Test equipment table name"""
        assert Equipment.__tablename__ == "equipment"

    def test_equipment_columns(self):
        """Test equipment has all required columns"""
        columns = {c.name for c in Equipment.__table__.columns}
        expected_columns = {
            "id", "name", "equipment_type", "manufacturer", "model",
            "serial_number", "ip_address", "port", "status", "sub_status",
            "capabilities", "metadata", "created_at", "updated_at"
        }
        assert expected_columns.issubset(columns)

    def test_equipment_relationships(self):
        """Test equipment relationships exist"""
        assert hasattr(Equipment, "status_history")
        assert hasattr(Equipment, "alarms")
        assert hasattr(Equipment, "work_orders")

    def test_equipment_default_status(self):
        """Test equipment default status"""
        column = Equipment.__table__.columns["status"]
        assert column.default is None or str(column.server_default) == "'UNKNOWN'"

    def test_equipment_indexes(self):
        """Test equipment has proper indexes"""
        index_names = {idx.name for idx in Equipment.__table__.indexes}
        assert "ix_equipment_type" in index_names
        assert "ix_equipment_status" in index_names


class TestEquipmentStatusHistoryModel:
    """Tests for EquipmentStatusHistory model"""

    def test_status_history_table_name(self):
        """Test status history table name"""
        assert EquipmentStatusHistory.__tablename__ == "equipment_status_history"

    def test_status_history_foreign_key(self):
        """Test status history has foreign key to equipment"""
        fk_columns = {
            fk.column_keys[0]
            for fk in EquipmentStatusHistory.__table__.foreign_keys
        }
        assert "equipment_id" in fk_columns

    def test_status_history_relationship(self):
        """Test status history relationship to equipment"""
        assert hasattr(EquipmentStatusHistory, "equipment")


class TestRecipeModel:
    """Tests for Recipe model"""

    def test_recipe_table_name(self):
        """Test recipe table name"""
        assert Recipe.__tablename__ == "recipe"

    def test_recipe_columns(self):
        """Test recipe has all required columns"""
        columns = {c.name for c in Recipe.__table__.columns}
        expected_columns = {
            "id", "name", "equipment_type", "version", "parent_version_id",
            "parameters", "steps", "fdc_limits", "created_by", "created_at",
            "approved_by", "approved_at", "is_active"
        }
        assert expected_columns.issubset(columns)

    def test_recipe_relationships(self):
        """Test recipe relationships exist"""
        assert hasattr(Recipe, "parent_version")
        assert hasattr(Recipe, "child_versions")
        assert hasattr(Recipe, "work_orders")

    def test_recipe_jsonb_columns(self):
        """Test recipe has JSONB columns for parameters and steps"""
        parameters_col = Recipe.__table__.columns["parameters"]
        steps_col = Recipe.__table__.columns["steps"]
        assert parameters_col.type.__class__.__name__ == "JSONB"
        assert steps_col.type.__class__.__name__ == "JSONB"


class TestWorkOrderModel:
    """Tests for WorkOrder model"""

    def test_workorder_table_name(self):
        """Test work order table name"""
        assert WorkOrder.__tablename__ == "work_order"

    def test_workorder_columns(self):
        """Test work order has all required columns"""
        columns = {c.name for c in WorkOrder.__table__.columns}
        expected_columns = {
            "id", "mes_id", "lot_id", "recipe_id", "target_equipment_id",
            "wafer_count", "priority", "status", "created_at", "started_at",
            "completed_at", "metadata"
        }
        assert expected_columns.issubset(columns)

    def test_workorder_unique_mes_id(self):
        """Test work order mes_id is unique"""
        mes_id_column = WorkOrder.__table__.columns["mes_id"]
        assert mes_id_column.unique is True

    def test_workorder_foreign_keys(self):
        """Test work order has foreign keys"""
        fk_columns = {
            fk.column_keys[0]
            for fk in WorkOrder.__table__.foreign_keys
        }
        assert "recipe_id" in fk_columns
        assert "target_equipment_id" in fk_columns

    def test_workorder_relationships(self):
        """Test work order relationships"""
        assert hasattr(WorkOrder, "recipe")
        assert hasattr(WorkOrder, "target_equipment")


class TestAlarmModel:
    """Tests for Alarm model"""

    def test_alarm_table_name(self):
        """Test alarm table name"""
        assert Alarm.__tablename__ == "alarm"

    def test_alarm_columns(self):
        """Test alarm has all required columns"""
        columns = {c.name for c in Alarm.__table__.columns}
        expected_columns = {
            "id", "equipment_id", "alarm_code", "alarm_text", "severity",
            "raised_at", "acknowledged_by", "acknowledged_at", "cleared_by",
            "cleared_at", "escalated"
        }
        assert expected_columns.issubset(columns)

    def test_alarm_foreign_key(self):
        """Test alarm has foreign key to equipment"""
        fk_columns = {
            fk.column_keys[0]
            for fk in Alarm.__table__.foreign_keys
        }
        assert "equipment_id" in fk_columns

    def test_alarm_severity_index(self):
        """Test alarm severity is indexed"""
        index_names = {idx.name for idx in Alarm.__table__.indexes}
        assert "ix_alarm_severity" in index_names


class TestCarrierModel:
    """Tests for Carrier model"""

    def test_carrier_table_name(self):
        """Test carrier table name"""
        assert Carrier.__tablename__ == "carrier"

    def test_carrier_columns(self):
        """Test carrier has all required columns"""
        columns = {c.name for c in Carrier.__table__.columns}
        expected_columns = {
            "id", "carrier_id", "carrier_type", "capacity",
            "current_location", "status", "created_at"
        }
        assert expected_columns.issubset(columns)

    def test_carrier_unique_carrier_id(self):
        """Test carrier carrier_id is unique"""
        carrier_id_column = Carrier.__table__.columns["carrier_id"]
        assert carrier_id_column.unique is True


class TestWaferEventModel:
    """Tests for WaferEvent model"""

    def test_wafer_event_table_name(self):
        """Test wafer event table name"""
        assert WaferEvent.__tablename__ == "wafer_event"

    def test_wafer_event_columns(self):
        """Test wafer event has all required columns"""
        columns = {c.name for c in WaferEvent.__table__.columns}
        expected_columns = {
            "id", "wafer_id", "lot_id", "carrier_id", "equipment_id",
            "chamber_id", "recipe_id", "event_type", "wafer_position",
            "parameters", "result", "timestamp"
        }
        assert expected_columns.issubset(columns)

    def test_wafer_event_foreign_keys(self):
        """Test wafer event has foreign keys"""
        fk_columns = {
            fk.column_keys[0]
            for fk in WaferEvent.__table__.foreign_keys
        }
        assert "carrier_id" in fk_columns
        assert "equipment_id" in fk_columns
        assert "recipe_id" in fk_columns


class TestAuditLogModel:
    """Tests for AuditLog model"""

    def test_audit_log_table_name(self):
        """Test audit log table name"""
        assert AuditLog.__tablename__ == "audit_log"

    def test_audit_log_columns(self):
        """Test audit log has all required columns"""
        columns = {c.name for c in AuditLog.__table__.columns}
        expected_columns = {
            "id", "user_id", "action", "resource_type", "resource_id",
            "details", "ip_address", "timestamp"
        }
        assert expected_columns.issubset(columns)

    def test_audit_log_jsonb_column(self):
        """Test audit log details is JSONB"""
        details_col = AuditLog.__table__.columns["details"]
        assert details_col.type.__class__.__name__ == "JSONB"


class TestBaseModel:
    """Tests for Base model"""

    def test_base_is_declarative(self):
        """Test Base is a DeclarativeBase"""
        assert issubclass(Base, Base.__class__.__bases__[0])

    def test_all_models_inherit_from_base(self):
        """Test all models inherit from Base"""
        models = [
            Equipment,
            EquipmentStatusHistory,
            Recipe,
            WorkOrder,
            Alarm,
            Carrier,
            WaferEvent,
            AuditLog,
        ]
        for model in models:
            assert hasattr(model, "__table__")
            assert model.__table__.metadata is Base.metadata


class TestModelInstantiation:
    """Tests for model instantiation"""

    def test_equipment_creation(self):
        """Test creating an Equipment instance"""
        equipment = Equipment(
            id=uuid.uuid4(),
            name="Test Equipment",
            equipment_type="ETCH",
            manufacturer="AMAT",
            model="Centura",
            status="IDLE",
        )
        assert equipment.name == "Test Equipment"
        assert equipment.equipment_type == "ETCH"
        assert equipment.status == "IDLE"

    def test_recipe_creation(self):
        """Test creating a Recipe instance"""
        recipe = Recipe(
            id=uuid.uuid4(),
            name="Test Recipe",
            equipment_type="ETCH",
            version="1.0",
            parameters={"temp": 100, "pressure": 50},
            steps=[{"step": 1, "duration": 60}],
        )
        assert recipe.name == "Test Recipe"
        assert recipe.parameters["temp"] == 100
        assert len(recipe.steps) == 1

    def test_alarm_creation(self):
        """Test creating an Alarm instance"""
        alarm = Alarm(
            id=uuid.uuid4(),
            equipment_id=uuid.uuid4(),
            alarm_code="E001",
            alarm_text="Temperature exceeded",
            severity="HIGH",
            escalated=False,
        )
        assert alarm.alarm_code == "E001"
        assert alarm.severity == "HIGH"
        assert alarm.escalated is False

    def test_carrier_creation(self):
        """Test creating a Carrier instance"""
        carrier = Carrier(
            id=uuid.uuid4(),
            carrier_id="CARR-001",
            carrier_type="FOUP",
            capacity=25,
            status="IDLE",
        )
        assert carrier.carrier_id == "CARR-001"
        assert carrier.capacity == 25
        assert carrier.status == "IDLE"


class TestRelationships:
    """Tests for model relationships"""

    def test_equipment_alarms_relationship(self):
        """Test equipment to alarms relationship"""
        equipment = Equipment(id=uuid.uuid4(), name="Test", equipment_type="CVD")
        alarm = Alarm(
            id=uuid.uuid4(),
            equipment_id=equipment.id,
            alarm_code="A001",
            severity="MEDIUM",
        )
        equipment.alarms.append(alarm)
        assert len(equipment.alarms) == 1
        assert equipment.alarms[0].alarm_code == "A001"

    def test_equipment_status_history_relationship(self):
        """Test equipment to status history relationship"""
        equipment = Equipment(id=uuid.uuid4(), name="Test", equipment_type="CVD")
        history = EquipmentStatusHistory(
            equipment_id=equipment.id,
            status="RUNNING",
            reason="Production started",
        )
        equipment.status_history.append(history)
        assert len(equipment.status_history) == 1
        assert equipment.status_history[0].status == "RUNNING"
