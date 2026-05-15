"""Tests for GEM handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from myeap.secs.gem.handler import GemHandler, AlarmInfo, VariableInfo, EquipmentConstant
from myeap.secs.gem.state_machine import GemState
from myeap.secs.protocol.message import SecsMessage, SecsItem, SecsFormat, secs_ascii, secs_uint4, secs_uint2


class TestGemHandler:
    """Tests for GemHandler."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return GemHandler()

    def test_initial_state(self, handler):
        """Test initial handler state."""
        assert handler.is_offline
        assert not handler.is_online
        assert handler.state_machine is not None

    def test_set_driver(self, handler):
        """Test setting driver reference."""
        mock_driver = MagicMock()
        handler.set_driver(mock_driver)
        assert handler._driver is mock_driver

    def test_default_mdln_softrev(self, handler):
        """Test default MDLN and SOFTREV."""
        assert handler._mdln == "MDL1"
        assert handler._softrev == "REV1"

    def test_handler_registration(self, handler):
        """Test default handlers are registered."""
        # S1 handlers
        assert (1, 1) in handler._handlers
        assert (1, 13) in handler._handlers
        assert (1, 3) in handler._handlers

        # S2 handlers
        assert (2, 13) in handler._handlers
        assert (2, 15) in handler._handlers

        # S5 handlers
        assert (5, 1) in handler._handlers
        assert (5, 3) in handler._handlers

        # S7 handlers
        assert (7, 1) in handler._handlers
        assert (7, 3) in handler._handlers

    def test_register_custom_handler(self, handler):
        """Test registering custom handler."""
        handler.register_handler(99, 1, AsyncMock())
        assert (99, 1) in handler._handlers


class TestGemHandlerMessages:
    """Tests for GEM message handlers."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return GemHandler()

    @pytest.mark.asyncio
    async def test_handle_are_you_there(self, handler):
        """Test S1F1 - Are You There."""
        msg = SecsMessage.create(s_number=1, f_number=1)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S1F2"
        assert len(reply.body) >= 2
        assert reply.body[0].value == "MDL1"
        assert reply.body[1].value == "REV1"

    @pytest.mark.asyncio
    async def test_handle_establish_communication_request(self, handler):
        """Test S1F13 - Establish Communication Request."""
        msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("HOST"), secs_ascii("1.0")],
        )
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S1F14"
        assert len(reply.body) >= 1
        # COMMACK should be 0 (accepted)
        assert reply.body[0].get_single_value() == 0

    @pytest.mark.asyncio
    async def test_handle_online_offline_request(self, handler):
        """Test S1F3 - Online/Offline Request."""
        msg = SecsMessage.create(s_number=1, f_number=3)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S1F4"

    @pytest.mark.asyncio
    async def test_handle_request_offline(self, handler):
        """Test S1F15 - Request Offline."""
        msg = SecsMessage.create(s_number=1, f_number=15)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S1F16"
        assert handler.is_offline

    @pytest.mark.asyncio
    async def test_handle_request_online(self, handler):
        """Test S1F17 - Request Online."""
        msg = SecsMessage.create(s_number=1, f_number=17)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S1F18"
        # Should be REMOTE (1)
        assert reply.body[0].get_single_value() == 1

    @pytest.mark.asyncio
    async def test_handle_equipment_constant_request(self, handler):
        """Test S2F13 - Equipment Constant Request."""
        # Add some constants
        handler.set_equipment_constant(1, "EC1", 100)
        handler.set_equipment_constant(2, "EC2", 200)

        msg = SecsMessage.create(s_number=2, f_number=13)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S2F14"

    @pytest.mark.asyncio
    async def test_handle_alarm_report_request(self, handler):
        """Test S5F1 - Alarm Report Request."""
        # Trigger an alarm
        await handler.trigger_alarm("ALM1", 100, "Test Alarm")

        msg = SecsMessage.create(s_number=5, f_number=1)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S5F2"

    @pytest.mark.asyncio
    async def test_handle_process_program_request(self, handler):
        """Test S7F1 - Process Program Request."""
        msg = SecsMessage.create(s_number=7, f_number=1)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S7F2"

    @pytest.mark.asyncio
    async def test_handle_data_collection_request(self, handler):
        """Test S6F1 - Data Collection Request."""
        # Add some variables
        handler.set_data_variable(1, "DV1", 100)
        handler.set_data_variable(2, "DV2", "test")

        msg = SecsMessage.create(s_number=6, f_number=1)
        reply = await handler.handle_message(msg)

        assert reply is not None
        assert reply.sf == "S6F2"

    @pytest.mark.asyncio
    async def test_handle_unrecognized_function(self, handler):
        """Test handling of unrecognized message."""
        msg = SecsMessage.create(s_number=99, f_number=99)
        reply = await handler.handle_message(msg)
        assert reply is None


class TestGemHandlerState:
    """Tests for GEM handler state management."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return GemHandler()

    @pytest.mark.asyncio
    async def test_set_online_remote(self, handler):
        """Test setting online to REMOTE."""
        await handler.set_online(remote=True)
        assert handler.is_online
        assert handler.state_machine.state == GemState.REMOTE

    @pytest.mark.asyncio
    async def test_set_online_local(self, handler):
        """Test setting online to LOCAL."""
        await handler.set_online(remote=False)
        assert handler.is_online
        assert handler.state_machine.state == GemState.LOCAL

    @pytest.mark.asyncio
    async def test_set_offline(self, handler):
        """Test setting offline."""
        # First go online
        await handler.set_online(remote=True)
        assert handler.is_online

        # Then go offline
        await handler.set_offline()
        assert handler.is_offline


class TestGemHandlerData:
    """Tests for GEM handler data management."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return GemHandler()

    def test_set_data_variable(self, handler):
        """Test setting data variable."""
        handler.set_data_variable(1, "Temperature", 25.5)

        assert 1 in handler._data_variables
        assert handler._data_variables[1].name == "Temperature"
        assert handler._data_variables[1].value == 25.5

    def test_set_equipment_constant(self, handler):
        """Test setting equipment constant."""
        handler.set_equipment_constant(100, "SetPoint", 500)

        assert 100 in handler._equipment_constants
        assert handler._equipment_constants[100].name == "SetPoint"
        assert handler._equipment_constants[100].value == 500

    @pytest.mark.asyncio
    async def test_trigger_alarm(self, handler):
        """Test triggering alarm."""
        await handler.trigger_alarm("HIGH_TEMP", 0x8001, "Temperature High")

        assert "HIGH_TEMP" in handler._alarms
        assert handler._alarms["HIGH_TEMP"].active
        assert handler._alarms["HIGH_TEMP"].alarm_code == 0x8001
        assert handler._alarms["HIGH_TEMP"].alarm_text == "Temperature High"

    @pytest.mark.asyncio
    async def test_clear_alarm(self, handler):
        """Test clearing alarm."""
        await handler.trigger_alarm("TEST_ALM", 1, "Test")
        assert handler._alarms["TEST_ALM"].active

        await handler.clear_alarm("TEST_ALM")
        assert not handler._alarms["TEST_ALM"].active

    def test_alarm_info_dataclass(self):
        """Test AlarmInfo dataclass."""
        alarm = AlarmInfo(
            alarm_id="TEST",
            alarm_code=100,
            alarm_text="Test Alarm",
        )

        assert alarm.alarm_id == "TEST"
        assert alarm.alarm_code == 100
        assert alarm.enabled is True
        assert alarm.active is False

    def test_variable_info_dataclass(self):
        """Test VariableInfo dataclass."""
        var = VariableInfo(
            vid=1,
            name="Temperature",
            value=25.5,
            unit="C",
        )

        assert var.vid == 1
        assert var.name == "Temperature"
        assert var.value == 25.5
        assert var.unit == "C"

    def test_equipment_constant_dataclass(self):
        """Test EquipmentConstant dataclass."""
        ec = EquipmentConstant(
            ecid=100,
            name="SetPoint",
            value=500,
            unit="units",
            min_value=0,
            max_value=1000,
        )

        assert ec.ecid == 100
        assert ec.name == "SetPoint"
        assert ec.value == 500
        assert ec.min_value == 0
        assert ec.max_value == 1000


class TestGemHandlerCallback:
    """Tests for GEM handler callbacks."""

    @pytest.fixture
    def handler(self):
        """Create a handler instance."""
        return GemHandler()

    @pytest.mark.asyncio
    async def test_comm_request_callback(self, handler):
        """Test communication request callback."""
        callback = AsyncMock(return_value=True)
        handler._on_comm_request = callback

        msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("HOST"), secs_ascii("1.0")],
        )
        reply = await handler.handle_message(msg)

        callback.assert_called_once()
        assert reply.body[0].get_single_value() == 0  # Accepted

    @pytest.mark.asyncio
    async def test_comm_request_callback_refused(self, handler):
        """Test communication request callback returning False."""
        callback = AsyncMock(return_value=False)
        handler._on_comm_request = callback

        msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("HOST"), secs_ascii("1.0")],
        )
        reply = await handler.handle_message(msg)

        callback.assert_called_once()
        assert reply.body[0].get_single_value() == 1  # Refused

    def test_terminal_display_callback(self, handler):
        """Test terminal display callback."""
        callback = MagicMock()
        handler._terminal_display = callback

        handler._terminal_display("S", "Hello World")
        callback.assert_called_once_with("S", "Hello World")
