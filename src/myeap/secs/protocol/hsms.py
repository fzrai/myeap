"""HSMS Connection Management

This module implements HSMS (High-Speed SECS Message Services) protocol
according to SEMI E37 standard.

HSMS is a TCP/IP-based protocol for SECS-II message transport.
It provides:
- Connection establishment (Select/reject)
- Heartbeat (Linktest)
- Automatic reconnection
- Message framing and flow control
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Optional, Callable, Awaitable, Dict, Any
import random

from myeap.secs.protocol.message import SecsMessage, SecsHeader, SecsItem


logger = logging.getLogger(__name__)


class HSMSMessageType(IntEnum):
    """HSMS message types.

    Reference: SEMI E37 Table 1
    """

    # Select Status (0x00-0x0F)
    SELECT_STATUS = 0x00

    # Data messages (0x10-0x1F)
    DATA = 0x10

    # Reject (0x20-0x2F)
    REJECTED = 0x20

    # Select/reject (0x30-0x3F)
    SELECT_REQUEST = 0x30
    SELECT_RESPONSE = 0x31
    DESELECT_REQUEST = 0x32
    DESELECT_RESPONSE = 0x33
    LINKTEST_REQUEST = 0x34
    LINKTEST_RESPONSE = 0x35
    SEPARATE_REQUEST = 0x36

    # Reserved (0x40-0xFF)
    RESERVED = 0x40

    @classmethod
    def is_control_message(cls, msg_type: int) -> bool:
        """Check if message type is a control message."""
        return 0x00 <= msg_type <= 0x3F

    @classmethod
    def is_data_message(cls, msg_type: int) -> bool:
        """Check if message type is a data message."""
        return msg_type == cls.DATA


class HSMSConnectionState(Enum):
    """HSMS connection states.

    Reference: SEMI E37.1 State Diagram
    """

    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    WAITING_FOR_SELECT = "WAITING_FOR_SELECT"
    SELECTED = "SELECTED"
    NOT_SELECTED = "NOT_SELECTED"
    DESELECTING = "DESELECTING"
    LINKTEST = "LINKTEST"
    SEPARATING = "SEPARATING"
    ERROR = "ERROR"


@dataclass
class HSMSHeader:
    """HSMS message header (10 bytes).

    Layout (10 bytes):
    - Session ID: 2 bytes (device ID or 0xFFFF for control messages)
    - Header Status: 2 bytes
    - System Bytes: 4 bytes
    - Message Type: 2 bytes

    For data messages, the Session ID maps to the SECS-II device ID.

    For control messages:
    - Session ID = 0xFFFF
    - System Bytes = 0x00000000
    - Message Type encodes the control function
    """

    session_id: int = 0
    header_status: int = 0  # For future use, always 0
    system_bytes: int = 0
    message_type: HSMSMessageType = HSMSMessageType.DATA

    HEADER_SIZE = 10

    # Status bits
    BIT_REQUIRES_REPLY = 0x8000  # R-bit
    BIT_WAIT_FOR_REPLY = 0x4000  # W-bit

    def encode(self) -> bytes:
        """Encode header to 10-byte binary.

        Returns:
            10-byte header
        """
        # Session ID
        session_bytes = struct.pack(">H", self.session_id)

        # Header status (with R/W bits from SECS header)
        status = self.header_status
        status_bytes = struct.pack(">H", status)

        # System bytes
        sys_bytes = struct.pack(">I", self.system_bytes)

        # Message type
        msg_type_bytes = struct.pack(">H", self.message_type)

        return session_bytes + status_bytes + sys_bytes + msg_type_bytes

    @classmethod
    def decode(cls, data: bytes) -> HSMSHeader:
        """Decode header from binary.

        Args:
            data: 10-byte header

        Returns:
            HSMSHeader instance
        """
        if len(data) < 10:
            raise ValueError(f"HSMS header must be 10 bytes, got {len(data)}")

        session_id = struct.unpack(">H", data[0:2])[0]
        header_status = struct.unpack(">H", data[2:4])[0]
        system_bytes = struct.unpack(">I", data[4:8])[0]
        message_type = HSMSMessageType(struct.unpack(">H", data[8:10])[0])

        return cls(
            session_id=session_id,
            header_status=header_status,
            system_bytes=system_bytes,
            message_type=message_type,
        )

    @classmethod
    def create_control(
        cls,
        message_type: HSMSMessageType,
        system_bytes: int = 0,
    ) -> HSMSHeader:
        """Create a control message header.

        Args:
            message_type: Type of control message
            system_bytes: System bytes (usually 0 for control messages)

        Returns:
            Control message header
        """
        return cls(
            session_id=0xFFFF,
            header_status=0,
            system_bytes=system_bytes,
            message_type=message_type,
        )

    @classmethod
    def create_data(
        cls,
        session_id: int,
        system_bytes: int,
        requires_reply: bool = False,
        wait_for_reply: bool = True,
    ) -> HSMSHeader:
        """Create a data message header.

        Args:
            session_id: Session/device ID
            system_bytes: System bytes for correlation
            requires_reply: R-bit
            wait_for_reply: W-bit

        Returns:
            Data message header
        """
        header_status = 0
        if requires_reply:
            header_status |= cls.BIT_REQUIRES_REPLY
        if wait_for_reply:
            header_status |= cls.BIT_WAIT_FOR_REPLY

        return cls(
            session_id=session_id,
            header_status=header_status,
            system_bytes=system_bytes,
            message_type=HSMSMessageType.DATA,
        )

    @property
    def is_control(self) -> bool:
        """Check if this is a control message."""
        return self.session_id == 0xFFFF

    @property
    def is_data(self) -> bool:
        """Check if this is a data message."""
        return self.message_type == HSMSMessageType.DATA

    @property
    def requires_reply(self) -> bool:
        """Check if R-bit is set."""
        return bool(self.header_status & self.BIT_REQUIRES_REPLY)

    @property
    def wait_for_reply(self) -> bool:
        """Check if W-bit is set."""
        return bool(self.header_status & self.BIT_WAIT_FOR_REPLY)


@dataclass
class HSMSMessage:
    """Complete HSMS message with header and body."""

    header: HSMSHeader
    secs_message: Optional[SecsMessage] = None
    raw_data: Optional[bytes] = None

    def encode(self) -> bytes:
        """Encode HSMS message to binary.

        Returns:
            Complete binary message
        """
        if self.secs_message:
            # Encode SECS message
            secs_bytes = self.secs_message.encode()
            # Update header with R/W bits from SECS header
            self.header.header_status = 0
            if self.secs_message.header.requires_response:
                self.header.header_status |= HSMSHeader.BIT_REQUIRES_REPLY
            if self.secs_message.header.wait_for_reply:
                self.header.header_status |= HSMSHeader.BIT_WAIT_FOR_REPLY
        else:
            secs_bytes = b""

        header_bytes = self.header.encode()
        return header_bytes + secs_bytes

    @classmethod
    def decode(cls, data: bytes) -> HSMSMessage:
        """Decode HSMS message from binary.

        Args:
            data: Complete HSMS message

        Returns:
            HSMSMessage instance
        """
        if len(data) < HSMSHeader.HEADER_SIZE:
            raise ValueError(f"HSMS message too short: {len(data)} bytes")

        header = HSMSHeader.decode(data)

        secs_message = None
        if header.is_data and len(data) > HSMSHeader.HEADER_SIZE:
            secs_data = data[HSMSHeader.HEADER_SIZE :]
            if len(secs_data) > 0:
                secs_message = SecsMessage.decode(secs_data)

        return cls(
            header=header,
            secs_message=secs_message,
            raw_data=data,
        )

    @classmethod
    def create_data(
        cls,
        secs_message: SecsMessage,
        session_id: int,
    ) -> HSMSMessage:
        """Create a data message from SECS message.

        Args:
            secs_message: SECS-II message
            session_id: Session ID

        Returns:
            HSMS data message
        """
        header = HSMSHeader.create_data(
            session_id=session_id,
            system_bytes=secs_message.header.system_bytes,
            requires_reply=secs_message.header.requires_response,
            wait_for_reply=secs_message.header.wait_for_reply,
        )

        return cls(header=header, secs_message=secs_message)

    @classmethod
    def create_control(
        cls,
        message_type: HSMSMessageType,
        system_bytes: int = 0,
    ) -> HSMSMessage:
        """Create a control message.

        Args:
            message_type: Type of control message
            system_bytes: System bytes

        Returns:
            HSMS control message
        """
        header = HSMSHeader.create_control(message_type, system_bytes)
        return cls(header=header)


# Default timeout values (in seconds)
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_RECV_TIMEOUT = 30.0
DEFAULT_SELECT_TIMEOUT = 10.0
DEFAULT_LINKTEST_INTERVAL = 30.0
DEFAULT_RECONNECT_DELAY = 5.0
MAX_RECONNECT_ATTEMPTS = 5


class HSMSConnection:
    """HSMS connection manager.

    Handles TCP/IP connection to equipment with HSMS protocol.

    Features:
    - Async connect/disconnect
    - Automatic reconnection
    - Linktest heartbeat
    - Message send/receive
    - Select/reject handshake

    Args:
        host: Equipment IP address
        port: Equipment port
        device_id: SECS device ID
        on_message: Callback for received SECS messages
        on_state_change: Callback for state changes
    """

    def __init__(
        self,
        host: str,
        port: int,
        device_id: int = 0,
        on_message: Optional[Callable[[SecsMessage], Awaitable[None]]] = None,
        on_state_change: Optional[Callable[[HSMSConnectionState], Awaitable[None]]] = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        recv_timeout: float = DEFAULT_RECV_TIMEOUT,
        linktest_interval: float = DEFAULT_LINKTEST_INTERVAL,
    ):
        self.host = host
        self.port = port
        self.device_id = device_id

        self._on_message = on_message
        self._on_state_change = on_state_change

        self._connect_timeout = connect_timeout
        self._recv_timeout = recv_timeout
        self._linktest_interval = linktest_interval

        self._state = HSMSConnectionState.NOT_CONNECTED
        self._prev_state = HSMSConnectionState.NOT_CONNECTED

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        self._recv_task: Optional[asyncio.Task] = None
        self._linktest_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        self._running = False
        self._closing = False

        # Message tracking
        self._pending_replies: Dict[int, asyncio.Future] = {}
        self._last_system_bytes = random.randint(0, 0xFFFFFF)
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "linktests_sent": 0,
            "linktests_received": 0,
            "errors": 0,
        }

    @property
    def state(self) -> HSMSConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connection is established (TCP connected)."""
        return self._state not in [
            HSMSConnectionState.NOT_CONNECTED,
            HSMSConnectionState.CONNECTING,
            HSMSConnectionState.ERROR,
        ]

    @property
    def is_selected(self) -> bool:
        """Check if HSMS session is selected."""
        return self._state == HSMSConnectionState.SELECTED

    @property
    def stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return self._stats.copy()

    async def _set_state(self, new_state: HSMSConnectionState) -> None:
        """Change connection state.

        Args:
            new_state: New state
        """
        if self._state != new_state:
            self._prev_state = self._state
            self._state = new_state
            logger.info(f"HSMS state change: {self._prev_state.value} -> {new_state.value}")

            if self._on_state_change:
                await self._on_state_change(new_state)

    async def connect(self) -> None:
        """Establish TCP/IP connection to equipment.

        This initiates the connection. Use wait_for_select() afterwards
        to complete the HSMS handshake.

        Raises:
            ConnectionError: If connection fails
        """
        if self._closing:
            raise ConnectionError("Connection is closing")

        if self.is_connected:
            logger.warning("Already connected")
            return

        await self._set_state(HSMSConnectionState.CONNECTING)

        try:
            logger.info(f"Connecting to {self.host}:{self.port}")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self._connect_timeout,
            )

            await self._set_state(HSMSConnectionState.CONNECTED)
            self._running = True

            # Start receive task
            self._recv_task = asyncio.create_task(self._recv_loop())

            logger.info(f"Connected to {self.host}:{self.port}")

        except asyncio.TimeoutError:
            await self._set_state(HSMSConnectionState.ERROR)
            raise ConnectionError(f"Connection timeout to {self.host}:{self.port}")
        except Exception as e:
            await self._set_state(HSMSConnectionState.ERROR)
            self._stats["errors"] += 1
            raise ConnectionError(f"Connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Close HSMS connection.

        Sends Separate request if selected, then closes TCP.
        """
        if self._closing:
            return

        self._closing = True
        self._running = False

        # Cancel tasks
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._linktest_task and not self._linktest_task.done():
            self._linktest_task.cancel()
            try:
                await self._linktest_task
            except asyncio.CancelledError:
                pass

        # Send separate request if selected
        if self._state == HSMSConnectionState.SELECTED:
            try:
                await self._send_control(HSMSMessageType.SEPARATE_REQUEST)
            except Exception:
                pass

        # Close TCP connection
        if self._writer:
            self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=5.0)
            except Exception:
                pass
            self._writer = None
            self._reader = None

        await self._set_state(HSMSConnectionState.NOT_CONNECTED)
        self._closing = False

        logger.info("Disconnected")

    async def select(self, timeout: float = DEFAULT_SELECT_TIMEOUT) -> bool:
        """Perform HSMS Select handshake.

        Sends Select.request and waits for Select.response.

        Args:
            timeout: Select timeout in seconds

        Returns:
            True if selected successfully

        Raises:
            ConnectionError: If not connected or select fails
        """
        if not self.is_connected:
            raise ConnectionError("Not connected")

        await self._set_state(HSMSConnectionState.WAITING_FOR_SELECT)

        # Generate system bytes for correlation
        sys_bytes = self._next_system_bytes()

        try:
            # Send Select.request
            select_req = HSMSMessage.create_control(
                HSMSMessageType.SELECT_REQUEST,
                system_bytes=sys_bytes,
            )
            await self._send_raw(select_req.encode())

            # Wait for Select.response
            future = asyncio.Future()
            self._pending_replies[sys_bytes] = future

            try:
                response = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                del self._pending_replies[sys_bytes]
                await self._set_state(HSMSConnectionState.NOT_SELECTED)
                return False

            # Check response
            if response.header.message_type == HSMSMessageType.SELECT_RESPONSE:
                await self._set_state(HSMSConnectionState.SELECTED)
                # Start linktest
                self._start_linktest()
                return True
            else:
                await self._set_state(HSMSConnectionState.NOT_SELECTED)
                return False

        except Exception as e:
            logger.error(f"Select failed: {e}")
            await self._set_state(HSMSConnectionState.ERROR)
            self._stats["errors"] += 1
            return False

    async def linktest(self, timeout: float = 10.0) -> bool:
        """Send Linktest.request and wait for response.

        Args:
            timeout: Linktest timeout

        Returns:
            True if linktest succeeds
        """
        if not self.is_connected:
            return False

        try:
            sys_bytes = self._next_system_bytes()

            linktest_req = HSMSMessage.create_control(
                HSMSMessageType.LINKTEST_REQUEST,
                system_bytes=sys_bytes,
            )
            await self._send_raw(linktest_req.encode())

            # Wait for response
            future = asyncio.Future()
            self._pending_replies[sys_bytes] = future

            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                if response.header.message_type == HSMSMessageType.LINKTEST_RESPONSE:
                    self._stats["linktests_received"] += 1
                    return True
            except asyncio.TimeoutError:
                del self._pending_replies[sys_bytes]
                logger.warning("Linktest timeout")

        except Exception as e:
            logger.error(f"Linktest failed: {e}")

        return False

    def _next_system_bytes(self) -> int:
        """Generate next system bytes.

        Returns:
            Unique system bytes value
        """
        self._last_system_bytes = (self._last_system_bytes + 1) & 0xFFFFFFFF
        return self._last_system_bytes

    async def send(self, message: SecsMessage) -> None:
        """Send a SECS message.

        Args:
            message: SECS message to send

        Raises:
            ConnectionError: If not connected or send fails
        """
        if not self.is_connected:
            raise ConnectionError("Not connected")

        if not self.is_selected:
            logger.warning("Sending message while not selected")

        # Create HSMS message
        hmsgs = HSMSMessage.create_data(
            secs_message=message,
            session_id=self.device_id,
        )

        # Update SECS message header
        message.header.device_id = self.device_id
        message.header.system_bytes = self._next_system_bytes()

        try:
            data = hmsgs.encode()
            await self._send_raw(data)
            self._stats["messages_sent"] += 1

            logger.debug(f"Sent {message.sf} (SysBytes={message.header.system_bytes})")

        except Exception as e:
            self._stats["errors"] += 1
            raise ConnectionError(f"Send failed: {e}") from e

    async def send_and_wait(
        self,
        message: SecsMessage,
        timeout: float = DEFAULT_RECV_TIMEOUT,
    ) -> SecsMessage:
        """Send a SECS message and wait for reply.

        Args:
            message: SECS message to send
            timeout: Reply timeout

        Returns:
            Reply SECS message

        Raises:
            ConnectionError: If not connected or send fails
            TimeoutError: If reply not received in time
        """
        await self.send(message)

        # Wait for reply with matching system bytes
        sys_bytes = message.header.system_bytes

        future = asyncio.Future()
        self._pending_replies[sys_bytes] = future

        try:
            response = await asyncio.wait_for(future, timeout=timeout)

            if response.secs_message:
                return response.secs_message
            else:
                raise ConnectionError("No SECS message in reply")

        except asyncio.TimeoutError:
            del self._pending_replies[sys_bytes]
            raise TimeoutError(f"Timeout waiting for reply to {message.sf}")

    async def _send_raw(self, data: bytes) -> None:
        """Send raw bytes to TCP stream.

        Args:
            data: Bytes to send
        """
        if not self._writer:
            raise ConnectionError("Not connected")

        self._writer.write(data)
        await self._writer.drain()

    async def _send_control(self, message_type: HSMSMessageType) -> None:
        """Send a control message.

        Args:
            message_type: Type of control message
        """
        msg = HSMSMessage.create_control(message_type, self._next_system_bytes())
        await self._send_raw(msg.encode())

    async def _recv_loop(self) -> None:
        """Main receive loop.

        Handles:
        - Message framing (TCP can deliver partial data)
        - Control messages
        - Data messages
        """
        buffer = bytearray()

        while self._running:
            try:
                # Read some data
                if self._reader:
                    data = await asyncio.wait_for(
                        self._reader.read(4096),
                        timeout=self._recv_timeout,
                    )

                    if not data:
                        # Connection closed
                        logger.warning("Connection closed by remote")
                        await self._handle_disconnect()
                        break

                    buffer.extend(data)

                # Process complete messages
                while len(buffer) >= HSMSHeader.HEADER_SIZE:
                    # Try to parse header to get message length
                    try:
                        header = HSMSHeader.decode(bytes(buffer[: HSMSHeader.HEADER_SIZE]))

                        # For data messages, length is in SECS header
                        if header.is_data:
                            # SECS header is at offset 10, length is bytes 7-9 (3 bytes big-endian)
                            if len(buffer) >= HSMSHeader.HEADER_SIZE + 3:
                                secs_len = struct.unpack(
                                    ">I",
                                    b"\x00" + bytes(buffer[HSMSHeader.HEADER_SIZE + 7 : HSMSHeader.HEADER_SIZE + 10]),
                                )[0]
                                total_len = HSMSHeader.HEADER_SIZE + secs_len
                            else:
                                continue  # Need more data
                        else:
                            # Control messages have no body
                            total_len = HSMSHeader.HEADER_SIZE

                        if len(buffer) >= total_len:
                            # Extract complete message
                            msg_data = bytes(buffer[:total_len])
                            del buffer[:total_len]

                            # Process message
                            await self._handle_message(msg_data)
                        else:
                            break  # Need more data

                    except ValueError:
                        # Incomplete header, continue reading
                        break

            except asyncio.TimeoutError:
                # Normal timeout, continue
                continue

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error(f"Receive error: {e}")
                self._stats["errors"] += 1
                await self._handle_disconnect()
                break

    async def _handle_message(self, data: bytes) -> None:
        """Handle received HSMS message.

        Args:
            data: Complete HSMS message data
        """
        try:
            message = HSMSMessage.decode(data)
            sys_bytes = message.header.system_bytes

            logger.debug(
                f"Received: {message.header.message_type.name} "
                f"(SysBytes={sys_bytes}, SessionID={message.header.session_id})"
            )

            # Check for pending reply
            if sys_bytes in self._pending_replies:
                future = self._pending_replies.pop(sys_bytes)
                if not future.done():
                    future.set_result(message)
                return

            # Handle control messages
            if message.header.is_control:
                await self._handle_control(message)
            else:
                # Handle data message
                if message.secs_message and self._on_message:
                    await self._on_message(message.secs_message)
                    self._stats["messages_received"] += 1

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self._stats["errors"] += 1

    async def _handle_control(self, message: HSMSMessage) -> None:
        """Handle HSMS control message.

        Args:
            message: HSMS control message
        """
        msg_type = message.header.message_type

        if msg_type == HSMSMessageType.SELECT_RESPONSE:
            # Select response - handled in select() via future
            pass

        elif msg_type == HSMSMessageType.SELECT_REQUEST:
            # Received Select.request - auto-accept
            response = HSMSMessage.create_control(HSMSMessageType.SELECT_RESPONSE)
            await self._send_raw(response.encode())
            await self._set_state(HSMSConnectionState.SELECTED)
            self._start_linktest()

        elif msg_type == HSMSMessageType.REJECTED:
            # Message was rejected
            logger.warning("Received Reject")
            await self._set_state(HSMSConnectionState.NOT_SELECTED)

        elif msg_type == HSMSMessageType.DESELECT_REQUEST:
            response = HSMSMessage.create_control(HSMSMessageType.DESELECT_RESPONSE)
            await self._send_raw(response.encode())
            await self._set_state(HSMSConnectionState.NOT_SELECTED)
            self._stop_linktest()

        elif msg_type == HSMSMessageType.DESELECT_RESPONSE:
            await self._set_state(HSMSConnectionState.NOT_SELECTED)
            self._stop_linktest()

        elif msg_type == HSMSMessageType.LINKTEST_REQUEST:
            response = HSMSMessage.create_control(HSMSMessageType.LINKTEST_RESPONSE)
            await self._send_raw(response.encode())

        elif msg_type == HSMSMessageType.LINKTEST_RESPONSE:
            self._stats["linktests_received"] += 1

        elif msg_type == HSMSMessageType.SEPARATE_REQUEST:
            # Remote wants to disconnect
            logger.info("Received Separate.request")
            await self._handle_disconnect()

    async def _handle_disconnect(self) -> None:
        """Handle unexpected disconnection."""
        self._running = False

        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        # Cancel pending replies
        for future in self._pending_replies.values():
            if not future.done():
                future.set_exception(ConnectionError("Connection lost"))

        self._pending_replies.clear()

        self._stop_linktest()

        if not self._closing:
            await self._set_state(HSMSConnectionState.NOT_CONNECTED)

    def _start_linktest(self) -> None:
        """Start periodic linktest task."""
        if self._linktest_task and not self._linktest_task.done():
            return

        self._linktest_task = asyncio.create_task(self._linktest_loop())

    def _stop_linktest(self) -> None:
        """Stop linktest task."""
        if self._linktest_task and not self._linktest_task.done():
            self._linktest_task.cancel()
            self._linktest_task = None

    async def _linktest_loop(self) -> None:
        """Periodic linktest loop."""
        while self._running and self._state == HSMSConnectionState.SELECTED:
            try:
                await asyncio.sleep(self._linktest_interval)

                if self._state == HSMSConnectionState.SELECTED:
                    success = await self.linktest()
                    self._stats["linktests_sent"] += 1

                    if not success:
                        logger.warning("Linktest failed")
                        # Connection might be dead
                        await self._handle_disconnect()
                        break

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error(f"Linktest error: {e}")

    async def __aenter__(self) -> "HSMSConnection":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


__all__ = [
    "HSMSConnection",
    "HSMSConnectionState",
    "HSMSMessage",
    "HSMSMessageType",
    "HSMSHeader",
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_RECV_TIMEOUT",
    "DEFAULT_SELECT_TIMEOUT",
    "DEFAULT_LINKTEST_INTERVAL",
]
