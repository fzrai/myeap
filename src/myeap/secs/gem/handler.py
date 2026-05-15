"""GEM Message Handlers

This module implements handlers for standard GEM/SECS messages
according to SEMI E5 and E30 standards.

Handlers are provided for:
- S1: Communications
- S2: Equipment Status
- S3: Equipment Control
- S4: Material Status
- S5: Alarm Management
- S6: Data Collection
- S7: Process Program Management
- S9: Exception Handling
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

from myeap.secs.protocol.message import SecsMessage, SecsItem, SecsFormat
from myeap.secs.gem.state_machine import GemState, GemStateMachine, GemEvent

if TYPE_CHECKING:
    from myeap.secs.driver import SecsDriver


logger = logging.getLogger(__name__)


@dataclass
class AlarmInfo:
    """Alarm information."""

    alarm_id: str
    alarm_code: int
    alarm_text: str
    enabled: bool = True
    active: bool = False


@dataclass
class VariableInfo:
    """Data variable information."""

    vid: int  # Variable ID
    name: str
    value: Any = None
    unit: str = ""


@dataclass
class EquipmentConstant:
    """Equipment constant."""

    ecid: int  # Constant ID
    name: str
    value: Any = None
    unit: str = ""
    min_value: Any = None
    max_value: Any = None


class GemHandler:
    """GEM Message Handler.

    Handles standard GEM messages according to SEMI E30.

    This class provides handlers for SECS stream/function messages
    that equipment must implement. Subclass to customize behavior.

    Attributes:
        state_machine: GEM state machine
        driver: Parent driver (set by SecsDriver)

    Example:
        handler = GemHandler()
        handler.set_driver(my_driver)
    """

    def __init__(
        self,
        state_machine: Optional[GemStateMachine] = None,
    ):
        self._state_machine = state_machine or GemStateMachine()
        self._driver: Optional[SecsDriver] = None

        # Equipment configuration
        self._mdln: str = "MDL1"  # Model
        self._softrev: str = "REV1"  # Software revision
        self._comm_ack: bool = False  # Communication acknowledge
        self._on_comm_request: Optional[Callable[[], Awaitable[bool]]] = None

        # Data collection
        self._data_variables: Dict[int, VariableInfo] = {}
        self._equipment_constants: Dict[int, EquipmentConstant] = {}
        self._alarms: Dict[str, AlarmInfo] = {}

        # Terminal services
        self._terminal_display: Optional[Callable[[str, str], None]] = None

        # Register default handlers
        self._handlers: Dict[tuple[int, int], Callable] = {}
        self._register_default_handlers()

    def set_driver(self, driver: "SecsDriver") -> None:
        """Set the parent driver.

        Args:
            driver: SecsDriver instance
        """
        self._driver = driver

    @property
    def state_machine(self) -> GemStateMachine:
        """Get the GEM state machine."""
        return self._state_machine

    @property
    def is_online(self) -> bool:
        """Check if equipment is online."""
        return self._state_machine.is_online

    @property
    def is_offline(self) -> bool:
        """Check if equipment is offline."""
        return self._state_machine.is_offline

    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        # S1 - Communications
        self.register_handler(1, 1, self.handle_are_you_there)  # S1F1
        self.register_handler(1, 13, self.handle_establish_communication_request)  # S1F13
        self.register_handler(1, 3, self.handle_online_offline_request)  # S1F3
        self.register_handler(1, 15, self.handle_request_offline)  # S1F15
        self.register_handler(1, 17, self.handle_request_online)  # S1F17

        # S2 - Equipment Status
        self.register_handler(2, 13, self.handle_equipment_constant_request)  # S2F13
        self.register_handler(2, 15, self.handle_equipment_constant_update)  # S2F15
        self.register_handler(2, 29, self.handle_date_time_request)  # S2F29
        self.register_handler(2, 31, self.handle_date_time_set_request)  # S2F31
        self.register_handler(2, 41, self.handle_ppnl_request)  # S2F41
        self.register_handler(2, 49, self.handle_equipment_constant_request_list)  # S2F49

        # S5 - Alarm Management
        self.register_handler(5, 1, self.handle_alarm_report_request)  # S5F1
        self.register_handler(5, 3, self.handle_enable_disable_alarm_request)  # S5F3
        self.register_handler(5, 5, self.handle_list_alarm_request)  # S5F5

        # S6 - Data Collection
        self.register_handler(6, 1, self.handle_data_collection_request)  # S6F1
        self.register_handler(6, 3, self.handle_data_collection_request_list)  # S6F3
        self.register_handler(6, 11, self.handle_data_variable_request)  # S6F11

        # S7 - Process Program
        self.register_handler(7, 1, self.handle_process_program_request)  # S7F1
        self.register_handler(7, 3, self.handle_process_program_send)  # S7F3
        self.register_handler(7, 5, self.handle_process_program_inquire)  # S7F5
        self.register_handler(7, 17, self.handle_current_pp_request)  # S7F17
        self.register_handler(7, 19, self.handle_pp_inquire)  # S7F19
        self.register_handler(7, 23, self.handle_delete_pp)  # S7F23
        self.register_handler(7, 25, self.handle_current_pp_modified)  # S7F25

        # S9 - Exception
        self.register_handler(9, 1, self.handle_unrecognized_device_id)  # S9F1
        self.register_handler(9, 3, self.handle_unrecognized_stream)  # S9F3
        self.register_handler(9, 5, self.handle_unrecognized_function)  # S9F5
        self.register_handler(9, 7, self.handle_unrecognized_transaction_type)  # S9F7

        # S12 - Terminal Services
        self.register_handler(12, 1, self.handle_terminal_display)  # S12F1
        self.register_handler(12, 3, self.handle_terminal_display_multi)  # S12F3
        self.register_handler(12, 5, self.handle_terminal_clear)  # S12F5

        # S13 - System Errors
        self.register_handler(13, 1, self.handle_command_error_notification)  # S13F1
        self.register_handler(13, 3, self.handle_transaction_id_error)  # S13F3

    def register_handler(
        self,
        stream: int,
        function: int,
        handler: Callable[[SecsMessage], Awaitable[SecsMessage]],
    ) -> None:
        """Register a message handler.

        Args:
            stream: Stream number (S)
            function: Function number (F)
            handler: Async handler function
        """
        self._handlers[(stream, function)] = handler

    async def handle_message(self, message: SecsMessage) -> Optional[SecsMessage]:
        """Handle an incoming SECS message.

        Args:
            message: Incoming SECS message

        Returns:
            Reply message if applicable, None otherwise
        """
        stream = message.header.s_number
        function = message.header.f_number

        handler = self._handlers.get((stream, function))

        if handler:
            try:
                reply = await handler(message)

                # Post events to state machine for relevant messages
                if stream == 1:
                    if function == 13:
                        await self._state_machine.post_event(GemEvent.COMMUNICATION_ESTABLISHED)
                    elif function == 15:
                        await self._state_machine.post_event(GemEvent.OFFLINE_REQUEST)
                    elif function == 17:
                        # Check if going to LOCAL or REMOTE based on content
                        pass

                return reply

            except Exception as e:
                logger.error(f"Handler error for S{stream}F{function}: {e}")
                return await self._create_error_reply(message, str(e))

        else:
            logger.warning(f"No handler for S{stream}F{function}")
            return None

    # S1 - Communications Handlers

    async def handle_are_you_there(self, msg: SecsMessage) -> SecsMessage:
        """S1F1 - Are You There Request.

        Equipment responds with MDLN and SOFTREV.

        Reference: SEMI E5
        """
        return SecsMessage.create(
            s_number=1,
            f_number=2,
            body=[
                SecsItem(SecsFormat.ASCII, self._mdln),
                SecsItem(SecsFormat.ASCII, self._softrev),
            ],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_establish_communication_request(self, msg: SecsMessage) -> SecsMessage:
        """S1F13 - Establish Communication Request.

        COMMACK:
        - 0: Accepted
        - 1: Refused

        Reference: SEMI E5
        """
        # Get MDLN and SOFTREV from request
        mdln = ""
        softrev = ""

        if len(msg.body) >= 1 and msg.body[0].format == SecsFormat.ASCII:
            mdln = msg.body[0].value or ""

        if len(msg.body) >= 2 and msg.body[1].format == SecsFormat.ASCII:
            softrev = msg.body[1].value or ""

        # Check if we accept the request
        commack = 0  # Accepted

        if self._on_comm_request:
            try:
                accepted = await self._on_comm_request()
                commack = 0 if accepted else 1
            except Exception:
                commack = 1

        # Update state
        if commack == 0:
            await self._state_machine.post_event(GemEvent.COMMUNICATION_ESTABLISHED)

        return SecsMessage.create(
            s_number=1,
            f_number=14,
            body=[SecsItem(SecsFormat.UINT1, commack)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_online_offline_request(self, msg: SecsMessage) -> SecsMessage:
        """S1F3 - Online/Offline Request.

        Reference: SEMI E30
        """
        await self._state_machine.post_event(GemEvent.ONLINE_REQUEST)
        await self._state_machine.post_event(GemEvent.ONLINE_SUCCESS)

        return SecsMessage.create(
            s_number=1,
            f_number=4,
            body=[SecsItem(SecsFormat.UINT1, 0)],  # Online
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_request_offline(self, msg: SecsMessage) -> SecsMessage:
        """S1F15 - Request Offline.

        Reference: SEMI E30
        """
        await self._state_machine.post_event(GemEvent.OFFLINE_REQUEST)

        return SecsMessage.create_reply(msg)

    async def handle_request_online(self, msg: SecsMessage) -> SecsMessage:
        """S1F17 - Request Online.

        Returns:
        - 0: Equipment goes to LOCAL
        - 1: Equipment goes to REMOTE

        Reference: SEMI E30
        """
        # Default to REMOTE
        await self._state_machine.post_event(GemEvent.GO_REMOTE)

        return SecsMessage.create(
            s_number=1,
            f_number=18,
            body=[SecsItem(SecsFormat.UINT1, 1)],  # REMOTE
            requires_response=False,
            wait_for_reply=False,
        )

    # S2 - Equipment Status Handlers

    async def handle_equipment_constant_request(self, msg: SecsMessage) -> SecsMessage:
        """S2F13 - Equipment Constant Request.

        Returns current equipment constants.

        Reference: SEMI E5
        """
        body = []

        for ecid, ec in self._equipment_constants.items():
            body.extend([
                SecsItem(SecsFormat.UINT4, ecid),
                SecsItem(SecsFormat.ASCII, ec.name),
                SecsItem(SecsFormat.UINT4, ec.value),
            ])

        return SecsMessage.create(
            s_number=2,
            f_number=14,
            body=[SecsItem(SecsFormat.LIST, body)] if body else [],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_equipment_constant_update(self, msg: SecsMessage) -> SecsMessage:
        """S2F15 - Equipment Constant Update.

        Host sends new values for equipment constants.
        """
        ackc2 = 0  # Accepted

        # Update constants
        if msg.body and msg.body[0].format == SecsFormat.LIST:
            items = msg.body[0].value
            for i in range(0, len(items) - 1, 2):
                if i + 1 < len(items):
                    ecid = items[i].get_single_value()
                    value = items[i + 1].get_single_value()

                    if ecid in self._equipment_constants:
                        self._equipment_constants[ecid].value = value
                        logger.info(f"EC {ecid} updated to {value}")

        return SecsMessage.create(
            s_number=2,
            f_number=16,
            body=[SecsItem(SecsFormat.UINT1, ackc2)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_date_time_request(self, msg: SecsMessage) -> SecsMessage:
        """S2F29 - Date and Time Request.

        Reference: SEMI E5
        """
        import time

        # Get current time
        now = time.time()
        time_bytes = int(now).to_bytes(8, "big")

        return SecsMessage.create(
            s_number=2,
            f_number=30,
            body=[SecsItem(SecsFormat.BINARY, time_bytes)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_date_time_set_request(self, msg: SecsMessage) -> SecsMessage:
        """S2F31 - Date and Time Set Request.

        Reference: SEMI E5
        """
        # Parse time from message
        time_value = 0
        if msg.body and len(msg.body) > 0:
            data = msg.body[0].value
            if isinstance(data, bytes) and len(data) >= 8:
                time_value = int.from_bytes(data[:8], "big")

        return SecsMessage.create_reply(msg)

    async def handle_ppnl_request(self, msg: SecsMessage) -> SecsMessage:
        """S2F41 - Process Program Names List Request.

        Reference: SEMI E5
        """
        # Return list of process program names
        return SecsMessage.create(
            s_number=2,
            f_number=42,
            body=[SecsItem(SecsFormat.LIST, [])],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_equipment_constant_request_list(self, msg: SecsMessage) -> SecsMessage:
        """S2F49 - Equipment Constant Request List.

        Reference: SEMI E5
        """
        # Get requested ECIDs
        requested_ids = []

        if msg.body and msg.body[0].format == SecsFormat.LIST:
            for item in msg.body[0].value:
                val = item.get_single_value()
                if val is not None:
                    requested_ids.append(val)

        # Return matching constants
        body = []
        for ecid, ec in self._equipment_constants.items():
            if not requested_ids or ecid in requested_ids:
                body.extend([
                    SecsItem(SecsFormat.UINT4, ecid),
                    SecsItem(SecsFormat.ASCII, ec.name),
                    SecsItem(SecsFormat.UINT4, ec.value),
                ])

        return SecsMessage.create(
            s_number=2,
            f_number=50,
            body=[SecsItem(SecsFormat.LIST, body)] if body else [],
            requires_response=False,
            wait_for_reply=False,
        )

    # S5 - Alarm Management Handlers

    async def handle_alarm_report_request(self, msg: SecsMessage) -> SecsMessage:
        """S5F1 - Alarm Report Request.

        Reference: SEMI E5
        """
        # Return active alarms
        body = []
        for alarm_id, alarm in self._alarms.items():
            if alarm.active:
                body.extend([
                    SecsItem(SecsFormat.ASCII, alarm.alarm_id),
                    SecsItem(SecsFormat.UINT2, alarm.alarm_code),
                    SecsItem(SecsFormat.ASCII, alarm.alarm_text),
                ])

        return SecsMessage.create(
            s_number=5,
            f_number=2,
            body=[SecsItem(SecsFormat.LIST, body)] if body else [],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_enable_disable_alarm_request(self, msg: SecsMessage) -> SecsMessage:
        """S5F3 - Enable/Disable Alarm Request.

        Reference: SEMI E5
        """
        ack5 = 0  # Accepted

        if msg.body and msg.body[0].format == SecsFormat.LIST:
            items = msg.body[0].value
            if len(items) >= 2:
                # Enable/disable code
                code = items[0].get_single_value()
                alarm_ids = items[1].value if len(items) > 1 else []

                for alarm_id in alarm_ids:
                    if alarm_id in self._alarms:
                        self._alarms[alarm_id].enabled = (code == 0)

        return SecsMessage.create(
            s_number=5,
            f_number=4,
            body=[SecsItem(SecsFormat.UINT1, ack5)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_list_alarm_request(self, msg: SecsMessage) -> SecsMessage:
        """S5F5 - List Alarm Request.

        Reference: SEMI E5
        """
        body = []
        for alarm_id, alarm in self._alarms.items():
            body.extend([
                SecsItem(SecsFormat.ASCII, alarm.alarm_id),
                SecsItem(SecsFormat.UINT2, alarm.alarm_code),
                SecsItem(SecsFormat.ASCII, alarm.alarm_text),
                SecsItem(SecsFormat.UINT1, 1 if alarm.enabled else 0),
            ])

        return SecsMessage.create(
            s_number=5,
            f_number=6,
            body=[SecsItem(SecsFormat.LIST, body)] if body else [],
            requires_response=False,
            wait_for_reply=False,
        )

    # S6 - Data Collection Handlers

    async def handle_data_collection_request(self, msg: SecsMessage) -> SecsMessage:
        """S6F1 - Data Collection Request.

        Reference: SEMI E5
        """
        # Return data collection variables
        body = []
        for vid, dv in self._data_variables.items():
            body.extend([
                SecsItem(SecsFormat.UINT2, vid),
                SecsItem(SecsFormat.ASCII, dv.name),
                SecsItem(SecsFormat.ASCII, str(dv.value) if dv.value is not None else ""),
            ])

        return SecsMessage.create(
            s_number=6,
            f_number=2,
            body=[SecsItem(SecsFormat.LIST, body)] if body else [],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_data_collection_request_list(self, msg: SecsMessage) -> SecsMessage:
        """S6F3 - Data Collection Request List.

        Reference: SEMI E5
        """
        return await self.handle_data_collection_request(msg)

    async def handle_data_variable_request(self, msg: SecsMessage) -> SecsMessage:
        """S6F11 - Data Variable Request.

        Reference: SEMI E5
        """
        return await self.handle_data_collection_request(msg)

    # S7 - Process Program Handlers

    async def handle_process_program_request(self, msg: SecsMessage) -> SecsMessage:
        """S7F1 - Process Program Request.

        Reference: SEMI E5
        """
        # Return process program
        pp_body = []

        return SecsMessage.create(
            s_number=7,
            f_number=2,
            body=[SecsItem(SecsFormat.LIST, pp_body)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_process_program_send(self, msg: SecsMessage) -> SecsMessage:
        """S7F3 - Process Program Send.

        Reference: SEMI E5
        """
        ack7 = 0  # Accepted

        # Parse and store process program
        if msg.body and len(msg.body) > 0:
            pp_data = msg.body[0].value
            logger.info(f"Received process program: {len(pp_data)} bytes")

        return SecsMessage.create(
            s_number=7,
            f_number=4,
            body=[SecsItem(SecsFormat.UINT1, ack7)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_process_program_inquire(self, msg: SecsMessage) -> SecsMessage:
        """S7F5 - Process Program Inquire.

        Reference: SEMI E5
        """
        grant = 1  # Accept

        return SecsMessage.create(
            s_number=7,
            f_number=6,
            body=[SecsItem(SecsFormat.UINT1, grant)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_current_pp_request(self, msg: SecsMessage) -> SecsMessage:
        """S7F17 - Current PP Request.

        Reference: SEMI E5
        """
        return SecsMessage.create(
            s_number=7,
            f_number=18,
            body=[SecsItem(SecsFormat.LIST, [])],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_pp_inquire(self, msg: SecsMessage) -> SecsMessage:
        """S7F19 - PP Inquire.

        Reference: SEMI E5
        """
        grant = 1  # Accept

        return SecsMessage.create(
            s_number=7,
            f_number=20,
            body=[SecsItem(SecsFormat.UINT1, grant)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_delete_pp(self, msg: SecsMessage) -> SecsMessage:
        """S7F23 - Delete PP.

        Reference: SEMI E5
        """
        ack7 = 0  # Accepted

        return SecsMessage.create(
            s_number=7,
            f_number=24,
            body=[SecsItem(SecsFormat.UINT1, ack7)],
            requires_response=False,
            wait_for_reply=False,
        )

    async def handle_current_pp_modified(self, msg: SecsMessage) -> SecsMessage:
        """S7F25 - Current PP Modified.

        Reference: SEMI E5
        """
        return SecsMessage.create_reply(msg)

    # S9 - Exception Handlers

    async def handle_unrecognized_device_id(self, msg: SecsMessage) -> None:
        """S9F1 - Unrecognized Device ID.

        Reference: SEMI E5
        """
        logger.warning(f"Unrecognized device ID: {msg.header.device_id}")

    async def handle_unrecognized_stream(self, msg: SecsMessage) -> None:
        """S9F3 - Unrecognized Stream.

        Reference: SEMI E5
        """
        logger.warning(f"Unrecognized stream: S{msg.header.s_number}")

    async def handle_unrecognized_function(self, msg: SecsMessage) -> None:
        """S9F5 - Unrecognized Function.

        Reference: SEMI E5
        """
        logger.warning(f"Unrecognized function: S{msg.stream}F{msg.function}")

    async def handle_unrecognized_transaction_type(self, msg: SecsMessage) -> None:
        """S9F7 - Unrecognized Transaction Type.

        Reference: SEMI E5
        """
        logger.warning(f"Unrecognized transaction type for S{msg.stream}F{msg.function}")

    # S12 - Terminal Services Handlers

    async def handle_terminal_display(self, msg: SecsMessage) -> SecsMessage:
        """S12F1 - Terminal Display.

        Reference: SEMI E5
        """
        terminal_text = ""
        if msg.body and len(msg.body) >= 1:
            terminal_text = msg.body[0].value or ""

        if self._terminal_display:
            self._terminal_display("S", terminal_text)

        return SecsMessage.create_reply(msg)

    async def handle_terminal_display_multi(self, msg: SecsMessage) -> SecsMessage:
        """S12F3 - Terminal Display Multi.

        Reference: SEMI E5
        """
        if msg.body and len(msg.body) >= 2:
            texts = msg.body[1].value if msg.body[1].format == SecsFormat.LIST else []
            for text in texts:
                if self._terminal_display:
                    self._terminal_display("M", text)

        return SecsMessage.create_reply(msg)

    async def handle_terminal_clear(self, msg: SecsMessage) -> SecsMessage:
        """S12F5 - Terminal Clear.

        Reference: SEMI E5
        """
        return SecsMessage.create_reply(msg)

    # S13 - System Error Handlers

    async def handle_command_error_notification(self, msg: SecsMessage) -> SecsMessage:
        """S13F1 - Command Error Notification.

        Reference: SEMI E5
        """
        return SecsMessage.create_reply(msg)

    async def handle_transaction_id_error(self, msg: SecsMessage) -> None:
        """S13F3 - Transaction ID Error.

        Reference: SEMI E5
        """
        logger.warning("Transaction ID error received")

    # Helper methods

    async def _create_error_reply(self, msg: SecsMessage, error: str) -> SecsMessage:
        """Create an error reply message."""
        return SecsMessage.create_reply(msg)

    # Public methods for equipment state changes

    async def set_online(self, remote: bool = True) -> None:
        """Set equipment to online state.

        Args:
            remote: True for REMOTE, False for LOCAL
        """
        if remote:
            await self._state_machine.post_event(GemEvent.GO_REMOTE)
        else:
            await self._state_machine.post_event(GemEvent.GO_LOCAL)

    async def set_offline(self) -> None:
        """Set equipment to offline state."""
        await self._state_machine.post_event(GemEvent.OFFLINE_REQUEST)

    async def trigger_alarm(self, alarm_id: str, code: int, text: str) -> None:
        """Trigger an alarm.

        Args:
            alarm_id: Alarm identifier
            code: Alarm code
            text: Alarm text
        """
        if alarm_id not in self._alarms:
            self._alarms[alarm_id] = AlarmInfo(
                alarm_id=alarm_id,
                alarm_code=code,
                alarm_text=text,
            )

        self._alarms[alarm_id].active = True

        # Send S5F1 asynchronously if driver is available
        if self._driver:
            # Notify driver to send alarm report
            pass

    async def clear_alarm(self, alarm_id: str) -> None:
        """Clear an alarm.

        Args:
            alarm_id: Alarm identifier
        """
        if alarm_id in self._alarms:
            self._alarms[alarm_id].active = False

    def set_data_variable(self, vid: int, name: str, value: Any) -> None:
        """Set a data variable value.

        Args:
            vid: Variable ID
            name: Variable name
            value: Variable value
        """
        if vid not in self._data_variables:
            self._data_variables[vid] = VariableInfo(vid=vid, name=name)

        self._data_variables[vid].value = value

    def set_equipment_constant(self, ecid: int, name: str, value: Any) -> None:
        """Set an equipment constant.

        Args:
            ecid: Constant ID
            name: Constant name
            value: Constant value
        """
        if ecid not in self._equipment_constants:
            self._equipment_constants[ecid] = EquipmentConstant(ecid=ecid, name=name)

        self._equipment_constants[ecid].value = value


__all__ = [
    "GemHandler",
    "AlarmInfo",
    "VariableInfo",
    "EquipmentConstant",
]
