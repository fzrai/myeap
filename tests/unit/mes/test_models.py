"""Tests for MES Message Models"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from myeap.mes.models import (
    MESMessageType,
    AlarmSeverity,
    EquipmentStatus,
    WorkOrderMessage,
    EquipmentStatusMessage,
    AlarmMessage,
    CompletionMessage,
    ProcessStartMessage,
    ProcessEndMessage,
    MaterialMoveMessage,
    DataCollectionMessage,
    RecipeMessage,
    CommandMessage,
    ResponseMessage,
    parse_mes_message,
)


class TestWorkOrderMessage:
    """Test WorkOrderMessage model"""

    def test_valid_work_order(self):
        """Test creating a valid work order message"""
        message = WorkOrderMessage(
            mes_id="WO001",
            lot_id="LOT2024001",
            recipe_name="RECIPE_A",
            wafer_count=25,
            priority=3,
        )

        assert message.mes_id == "WO001"
        assert message.lot_id == "LOT2024001"
        assert message.recipe_name == "RECIPE_A"
        assert message.wafer_count == 25
        assert message.priority == 3
        assert message.type == "work_order"

    def test_work_order_default_priority(self):
        """Test work order default priority"""
        message = WorkOrderMessage(
            mes_id="WO001",
            lot_id="LOT2024001",
            recipe_name="RECIPE_A",
            wafer_count=25,
        )

        assert message.priority == 5

    def test_work_order_with_metadata(self):
        """Test work order with metadata"""
        metadata = {"customer": "ACME", "order_id": "12345"}
        message = WorkOrderMessage(
            mes_id="WO001",
            lot_id="LOT2024001",
            recipe_name="RECIPE_A",
            wafer_count=25,
            metadata=metadata,
        )

        assert message.metadata == metadata

    def test_work_order_priority_validation(self):
        """Test priority range validation"""
        # Valid priorities
        for priority in [1, 5, 9]:
            msg = WorkOrderMessage(
                mes_id="WO001",
                lot_id="LOT001",
                recipe_name="R1",
                wafer_count=10,
                priority=priority,
            )
            assert msg.priority == priority

        # Invalid priority (should raise)
        with pytest.raises(ValidationError):
            WorkOrderMessage(
                mes_id="WO001",
                lot_id="LOT001",
                recipe_name="R1",
                wafer_count=10,
                priority=10,  # Too high
            )


class TestEquipmentStatusMessage:
    """Test EquipmentStatusMessage model"""

    def test_valid_status_message(self):
        """Test creating a valid status message"""
        message = EquipmentStatusMessage(
            equipment_id="EQP001",
            status=EquipmentStatus.RUNNING,
        )

        assert message.equipment_id == "EQP001"
        assert message.status == EquipmentStatus.RUNNING
        assert message.timestamp is not None

    def test_status_with_sub_status(self):
        """Test status message with sub-status"""
        message = EquipmentStatusMessage(
            equipment_id="EQP001",
            status=EquipmentStatus.PAUSED,
            sub_status="PAUSED_BY_OPERATOR",
        )

        assert message.sub_status == "PAUSED_BY_OPERATOR"

    def test_status_serialization(self):
        """Test status message JSON serialization"""
        message = EquipmentStatusMessage(
            equipment_id="EQP001",
            status=EquipmentStatus.IDLE,
        )

        data = message.model_dump()
        assert data["status"] == "IDLE"


class TestAlarmMessage:
    """Test AlarmMessage model"""

    def test_valid_alarm(self):
        """Test creating a valid alarm message"""
        message = AlarmMessage(
            equipment_id="EQP001",
            alarm_id="ALM001",
            alarm_code="E001",
            alarm_text="Temperature too high",
            severity=AlarmSeverity.MAJOR,
        )

        assert message.alarm_id == "ALM001"
        assert message.alarm_code == "E001"
        assert message.severity == AlarmSeverity.MAJOR
        assert message.ack_required is True

    def test_alarm_with_ack(self):
        """Test alarm with acknowledgment"""
        message = AlarmMessage(
            equipment_id="EQP001",
            alarm_id="ALM001",
            alarm_code="E001",
            alarm_text="Error",
            severity=AlarmSeverity.CRITICAL,
            ack_required=True,
            ack_user="operator1",
        )

        assert message.ack_user == "operator1"

    def test_all_severity_levels(self):
        """Test all alarm severity levels"""
        for severity in AlarmSeverity:
            message = AlarmMessage(
                equipment_id="EQP001",
                alarm_id=f"ALM_{severity.value}",
                alarm_code="E001",
                alarm_text="Test",
                severity=severity,
            )
            assert message.severity == severity


class TestCompletionMessage:
    """Test CompletionMessage model"""

    def test_valid_completion(self):
        """Test creating a valid completion message"""
        message = CompletionMessage(
            mes_id="WO001",
            lot_id="LOT001",
            equipment_id="EQP001",
            recipe_name="RECIPE_A",
            wafer_count=25,
            completed_count=25,
            good_count=24,
            reject_count=1,
            yield_rate=96.0,
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 12, 0, 0),
        )

        assert message.completed_count == 25
        assert message.good_count == 24
        assert message.reject_count == 1
        assert message.yield_rate == 96.0

    def test_yield_rate_validation(self):
        """Test yield rate range validation"""
        # Valid yield rates
        for yield_rate in [0.0, 50.0, 100.0]:
            msg = CompletionMessage(
                mes_id="WO001",
                lot_id="LOT001",
                equipment_id="EQP001",
                recipe_name="R1",
                wafer_count=10,
                completed_count=10,
                good_count=int(yield_rate / 10),
                reject_count=10 - int(yield_rate / 10),
                yield_rate=yield_rate,
                start_time=datetime.now(),
                end_time=datetime.now(),
            )
            assert msg.yield_rate == yield_rate

        # Invalid yield rate
        with pytest.raises(ValidationError):
            CompletionMessage(
                mes_id="WO001",
                lot_id="LOT001",
                equipment_id="EQP001",
                recipe_name="R1",
                wafer_count=10,
                completed_count=10,
                good_count=15,
                reject_count=0,
                yield_rate=150.0,  # Invalid
                start_time=datetime.now(),
                end_time=datetime.now(),
            )


class TestProcessMessages:
    """Test process-related messages"""

    def test_process_start_message(self):
        """Test ProcessStartMessage"""
        message = ProcessStartMessage(
            mes_id="WO001",
            lot_id="LOT001",
            equipment_id="EQP001",
            recipe_name="RECIPE_A",
            wafer_count=25,
            carrier_id="CARR001",
        )

        assert message.carrier_id == "CARR001"
        assert message.type == "process_start"

    def test_process_end_message(self):
        """Test ProcessEndMessage"""
        message = ProcessEndMessage(
            mes_id="WO001",
            lot_id="LOT001",
            equipment_id="EQP001",
            wafer_count=25,
            reason="COMPLETED",
        )

        assert message.reason == "COMPLETED"
        assert message.type == "process_end"


class TestMaterialMoveMessage:
    """Test MaterialMoveMessage"""

    def test_material_move(self):
        """Test material move message"""
        message = MaterialMoveMessage(
            lot_id="LOT001",
            carrier_id="CARR001",
            from_equipment_id="EQP001",
            to_equipment_id="EQP002",
            wafer_count=25,
        )

        assert message.from_equipment_id == "EQP001"
        assert message.to_equipment_id == "EQP002"


class TestDataCollectionMessage:
    """Test DataCollectionMessage"""

    def test_data_collection(self):
        """Test data collection message"""
        data = {
            "temperature": 250.5,
            "pressure": 1.0,
            "humidity": 45.0,
        }

        message = DataCollectionMessage(
            equipment_id="EQP001",
            lot_id="LOT001",
            data_collection_plan_id="DCP001",
            data=data,
            triggered_by="TIMER",
        )

        assert message.data["temperature"] == 250.5
        assert message.triggered_by == "TIMER"


class TestRecipeMessage:
    """Test RecipeMessage"""

    def test_recipe_download(self):
        """Test recipe download message"""
        message = RecipeMessage(
            recipe_name="RECIPE_A",
            action="DOWNLOAD",
            equipment_id="EQP001",
        )

        assert message.action == "DOWNLOAD"

    def test_recipe_upload(self):
        """Test recipe upload message"""
        import base64

        content = "recipe data here"
        encoded = base64.b64encode(content.encode()).decode()

        message = RecipeMessage(
            recipe_name="RECIPE_A",
            action="UPLOAD",
            recipe_content=encoded,
            version="v1.0",
        )

        assert message.action == "UPLOAD"
        assert message.version == "v1.0"


class TestCommandMessage:
    """Test CommandMessage"""

    def test_command_message(self):
        """Test command message"""
        message = CommandMessage(
            command_id="CMD001",
            command_type="START_PROCESS",
            equipment_id="EQP001",
            parameters={"lot_id": "LOT001", "recipe": "RECIPE_A"},
            priority=3,
            timeout=300,
        )

        assert message.command_type == "START_PROCESS"
        assert message.parameters["recipe"] == "RECIPE_A"
        assert message.timeout == 300


class TestResponseMessage:
    """Test ResponseMessage"""

    def test_success_response(self):
        """Test success response"""
        message = ResponseMessage(
            original_message_id="MSG001",
            status="SUCCESS",
            result={"processed": True, "count": 10},
        )

        assert message.status == "SUCCESS"
        assert message.result["processed"] is True

    def test_failure_response(self):
        """Test failure response"""
        message = ResponseMessage(
            original_message_id="MSG001",
            status="FAILED",
            error_code="E001",
            error_message="Processing failed",
        )

        assert message.status == "FAILED"
        assert message.error_code == "E001"


class TestMessageParsing:
    """Test message parsing functions"""

    def test_parse_work_order(self):
        """Test parsing work order message"""
        data = {
            "type": "work_order",
            "mes_id": "WO001",
            "lot_id": "LOT001",
            "recipe_name": "RECIPE_A",
            "wafer_count": 25,
        }

        message = parse_mes_message(data)
        assert isinstance(message, WorkOrderMessage)
        assert message.mes_id == "WO001"

    def test_parse_equipment_status(self):
        """Test parsing equipment status message"""
        data = {
            "type": "equipment_status",
            "equipment_id": "EQP001",
            "status": "RUNNING",
        }

        message = parse_mes_message(data)
        assert isinstance(message, EquipmentStatusMessage)
        assert message.status == EquipmentStatus.RUNNING

    def test_parse_alarm(self):
        """Test parsing alarm message"""
        data = {
            "type": "alarm",
            "equipment_id": "EQP001",
            "alarm_id": "ALM001",
            "alarm_code": "E001",
            "alarm_text": "Error",
            "severity": "MAJOR",
        }

        message = parse_mes_message(data)
        assert isinstance(message, AlarmMessage)
        assert message.severity == AlarmSeverity.MAJOR

    def test_parse_unknown_type(self):
        """Test parsing unknown message type"""
        data = {
            "type": "unknown_type",
            "data": "test",
        }

        with pytest.raises(ValueError, match="Unknown MES message type"):
            parse_mes_message(data)


class TestEnums:
    """Test enum values"""

    def test_mes_message_types(self):
        """Test MES message type enum"""
        assert MESMessageType.WORK_ORDER.value == "work_order"
        assert MESMessageType.ALARM.value == "alarm"
        assert MESMessageType.COMPLETION.value == "completion"

    def test_alarm_severity_levels(self):
        """Test alarm severity enum"""
        assert AlarmSeverity.CRITICAL.value == "CRITICAL"
        assert AlarmSeverity.MAJOR.value == "MAJOR"
        assert AlarmSeverity.MINOR.value == "MINOR"
        assert AlarmSeverity.WARNING.value == "WARNING"
        assert AlarmSeverity.INFO.value == "INFO"

    def test_equipment_status_values(self):
        """Test equipment status enum"""
        assert EquipmentStatus.IDLE.value == "IDLE"
        assert EquipmentStatus.RUNNING.value == "RUNNING"
        assert EquipmentStatus.PAUSED.value == "PAUSED"
        assert EquipmentStatus.DOWN.value == "DOWN"
        assert EquipmentStatus.MAINTENANCE.value == "MAINTENANCE"
