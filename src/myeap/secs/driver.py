"""SECS Device Driver Base Class

This module provides the base class for SECS/GEM equipment drivers.

Drivers subclass SecsDriver to implement equipment-specific communication
with SECS-II/GEM protocol.

Features:
- HSMS connection management
- GEM state machine integration
- Message send/receive with timeout
- Automatic reconnection
- Event callbacks
- Full observability (metrics, tracing, logging)
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, Awaitable

from myeap.secs.protocol.message import SecsMessage
from myeap.secs.protocol.hsms import HSMSConnection, HSMSConnectionState
from myeap.secs.gem.state_machine import GemState, GemStateMachine, GemEvent
from myeap.secs.gem.handler import GemHandler
from myeap.core.exceptions import ConnectionError, ProtocolError
from myeap.core.logging import get_logger
from myeap.observability.metrics import get_metrics_collector
from myeap.observability.tracing import create_span, SecsMessageSpan

logger = get_logger(__name__)
metrics = get_metrics_collector()


@dataclass
class DriverConfig:
    """Configuration for SECS driver.

    Attributes:
        host: Equipment IP address
        port: Equipment HSMS port
        device_id: SECS device ID
        connect_timeout: Connection timeout in seconds
        recv_timeout: Receive timeout in seconds
        reconnect_enabled: Enable automatic reconnection
        reconnect_delay: Delay between reconnection attempts
        max_reconnect_attempts: Maximum reconnection attempts
        linktest_interval: Linktest interval in seconds
    """

    host: str
    port: int
    device_id: int = 0
    connect_timeout: float = 10.0
    recv_timeout: float = 30.0
    reconnect_enabled: bool = True
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 5
    linktest_interval: float = 30.0
    mdln: str = "MYEAP"
    softrev: str = "1.0.0"


class SecsDriver(ABC):
    """Base class for SECS/GEM equipment drivers.

    This class provides the foundation for implementing equipment-specific
    SECS/GEM communication. Subclasses should implement:
    - _send_raw: Low-level send implementation
    - _receive_raw: Low-level receive implementation
    - Specific message handlers for equipment functionality

    Features:
    - HSMS connection management
    - GEM state machine integration
    - Message send/receive with timeout
    - Automatic reconnection
    - Event callbacks

    Example:
        class MyEquipmentDriver(SecsDriver):
            async def _send_raw(self, data: bytes) -> None:
                await self._connection.send(data)

        driver = MyEquipmentDriver(config)
        await driver.connect()
        reply = await driver.send_command(message)
    """

    def __init__(
        self,
        config: DriverConfig,
        gem_handler: Optional[GemHandler] = None,
    ):
        """Initialize SECS driver.

        Args:
            config: Driver configuration
            gem_handler: GEM handler (created if not provided)
        """
        self.config = config

        # Connection
        self._connection: Optional[HSMSConnection] = None
        self._connected = False

        # Reconnection
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._stop_reconnect = False

        # GEM
        self._gem_handler = gem_handler or GemHandler()
        self._gem_handler.set_driver(self)

        # Statistics
        self._stats: Dict[str, Any] = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "last_error": None,
        }

        # Callbacks
        self._on_connect: Optional[Callable[[], Awaitable[None]]] = None
        self._on_disconnect: Optional[Callable[[], Awaitable[None]]] = None
        self._on_message: Optional[Callable[[SecsMessage], Awaitable[None]]] = None
        self._on_error: Optional[Callable[[Exception], Awaitable[None]]] = None

        logger.info(f"SECS driver initialized for {config.host}:{config.port}")

    @property
    def is_connected(self) -> bool:
        """Check if driver is connected."""
        return self._connected

    @property
    def is_selected(self) -> bool:
        """Check if HSMS session is selected."""
        return self._connection.is_selected if self._connection else False

    @property
    def gem_handler(self) -> GemHandler:
        """Get GEM handler."""
        return self._gem_handler

    @property
    def state(self) -> GemState:
        """Get current GEM state."""
        return self._gem_handler.state_machine.state

    @property
    def is_online(self) -> bool:
        """Check if equipment is online."""
        return self._gem_handler.state_machine.is_online

    @property
    def stats(self) -> Dict[str, Any]:
        """Get driver statistics."""
        stats = self._stats.copy()
        if self._connection:
            stats["hsms_stats"] = self._connection.stats
        return stats

    def set_callbacks(
        self,
        on_connect: Optional[Callable[[], Awaitable[None]]] = None,
        on_disconnect: Optional[Callable[[], Awaitable[None]]] = None,
        on_message: Optional[Callable[[SecsMessage], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    ) -> None:
        """Set driver callbacks.

        Args:
            on_connect: Called when connection is established
            on_disconnect: Called when connection is lost
            on_message: Called when message is received
            on_error: Called on error
        """
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_message = on_message
        self._on_error = on_error

    async def connect(self) -> None:
        """Connect to equipment.

        Establishes HSMS connection and performs select handshake.
        """
        if self._connected:
            logger.warning("Already connected")
            return

        with create_span(
            "secs_connect",
            attributes={
                "equipment_host": self.config.host,
                "equipment_port": self.config.port,
                "device_id": self.config.device_id,
            },
        ) as span:
            try:
                logger.info(
                    "secs_connecting",
                    equipment_id=self.config.host,
                    host=self.config.host,
                    port=self.config.port,
                    device_id=self.config.device_id,
                )

                # Create HSMS connection
                self._connection = HSMSConnection(
                    host=self.config.host,
                    port=self.config.port,
                    device_id=self.config.device_id,
                    on_message=self._handle_message,
                    on_state_change=self._handle_state_change,
                    connect_timeout=self.config.connect_timeout,
                    recv_timeout=self.config.recv_timeout,
                    linktest_interval=self.config.linktest_interval,
                )

                # Connect TCP
                await self._connection.connect()

                # Select HSMS session
                selected = await self._connection.select()

                if not selected:
                    await self._connection.disconnect()
                    raise ConnectionError("HSMS select failed")

                self._connected = True
                self._reconnect_attempts = 0

                # 更新连接状态指标
                metrics.set_connection_status(
                    self.config.host,
                    self.config.host,
                    self.config.port,
                    True,
                )

                # Establish GEM communication
                await self._establish_communication()

                # Notify callback
                if self._on_connect:
                    await self._on_connect()

                logger.info(
                    "secs_connected",
                    equipment_id=self.config.host,
                    host=self.config.host,
                    port=self.config.port,
                )

            except Exception as e:
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)
                metrics.record_secs_message_error(self.config.host, "connection_failed")
                span.add_event("connection_failed", {"error": str(e)})
                logger.error(
                    "secs_connection_failed",
                    equipment_id=self.config.host,
                    error=str(e),
                )
                await self._cleanup_connection()

                # Try reconnect if enabled
                if self.config.reconnect_enabled:
                    await self._schedule_reconnect()
                else:
                    raise

    async def disconnect(self) -> None:
        """Disconnect from equipment."""
        self._stop_reconnect = True

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        await self._cleanup_connection()

        # 更新连接状态指标
        metrics.set_connection_status(
            self.config.host,
            self.config.host,
            self.config.port,
            False,
        )

        if self._on_disconnect:
            await self._on_disconnect()

        logger.info(
            "secs_disconnected",
            equipment_id=self.config.host,
            host=self.config.host,
            port=self.config.port,
        )

    async def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self._connection:
            try:
                await self._connection.disconnect()
            except Exception:
                pass
            self._connection = None
        self._connected = False

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._stop_reconnect:
            return

        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return

        self._reconnect_attempts += 1
        delay = self.config.reconnect_delay * (2 ** (self._reconnect_attempts - 1))

        logger.info(f"Scheduling reconnect in {delay}s (attempt {self._reconnect_attempts})")

        await asyncio.sleep(delay)

        if not self._stop_reconnect:
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
                await self._schedule_reconnect()

    async def _establish_communication(self) -> None:
        """Establish GEM communication.

        Sends S1F13 and waits for acknowledgment.
        """
        from myeap.secs.gem.messages import GemMessages

        # Create communication request
        msg = GemMessages.create_s1f13(self.config.mdln, self.config.softrev)

        try:
            reply = await self.send_command(msg, timeout=10.0)

            # Parse reply
            if reply:
                accepted, error = GemMessages.parse_s1f14(reply)
                if accepted:
                    await self._gem_handler.state_machine.post_event(
                        GemEvent.COMMUNICATION_ESTABLISHED
                    )
                    logger.info("GEM communication established")
                else:
                    logger.warning(f"GEM communication refused: {error}")

        except Exception as e:
            logger.warning(f"Communication establishment error: {e}")

    async def send_command(
        self,
        message: SecsMessage,
        timeout: Optional[float] = None,
    ) -> Optional[SecsMessage]:
        """Send a SECS command and wait for reply.

        Args:
            message: SECS message to send
            timeout: Reply timeout (uses default if None)

        Returns:
            Reply message, or None if no reply expected

        Raises:
            ConnectionError: If not connected
            TimeoutError: If reply timeout
        """
        if not self._connected or not self._connection:
            raise ConnectionError("Not connected")

        timeout = timeout or self.config.recv_timeout
        start_time = time.perf_counter()

        # 创建追踪span
        with SecsMessageSpan(
            equipment_id=self.config.host,
            message_id=message.sf,
            stream=message.header.s_number,
            function=message.header.f_number,
            direction="send",
            session_id=self.config.device_id,
        ) as span:
            try:
                # 设置设备ID
                message.header.device_id = self.config.device_id

                # 发送并等待回复
                reply = await self._connection.send_and_wait(message, timeout=timeout)

                self._stats["messages_sent"] += 1

                # 记录指标
                duration = time.perf_counter() - start_time
                metrics.record_secs_message_sent(
                    self.config.host,
                    message.sf,
                    message.header.s_number,
                    message.header.f_number,
                )
                metrics.observe_secs_message_duration(
                    self.config.host,
                    message.sf,
                    "send_command",
                    duration,
                )
                metrics.record_secs_message_received(
                    self.config.host,
                    reply.sf if reply else "none",
                    reply.header.s_number if reply else 0,
                    reply.header.f_number if reply else 0,
                )

                logger.info(
                    "secs_message_sent",
                    equipment_id=self.config.host,
                    message_id=message.sf,
                    stream=message.header.s_number,
                    function=message.header.f_number,
                    duration_ms=duration * 1000,
                    has_reply=reply is not None,
                )

                return reply

            except asyncio.TimeoutError:
                metrics.record_secs_message_error(self.config.host, "timeout")
                span.add_event("timeout", {"timeout_seconds": timeout})
                logger.warning(
                    "secs_message_timeout",
                    equipment_id=self.config.host,
                    message_id=message.sf,
                    timeout_seconds=timeout,
                )
                raise TimeoutError(f"Timeout waiting for reply to {message.sf}")

            except Exception as e:
                metrics.record_secs_message_error(self.config.host, "error")
                logger.error(
                    "secs_message_error",
                    equipment_id=self.config.host,
                    message_id=message.sf,
                    error=str(e),
                )
                raise

    async def send_message(
        self,
        message: SecsMessage,
    ) -> None:
        """Send a SECS message without waiting for reply.

        Args:
            message: SECS message to send

        Raises:
            ConnectionError: If not connected
        """
        if not self._connected or not self._connection:
            raise ConnectionError("Not connected")

        try:
            message.header.device_id = self.config.device_id
            await self._connection.send(message)
            self._stats["messages_sent"] += 1

            logger.debug(f"Sent {message.sf} (no reply)")

        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Send message error: {e}")
            raise

    async def _handle_message(self, message: SecsMessage) -> None:
        """Handle received SECS message.

        Args:
            message: Received SECS message
        """
        self._stats["messages_received"] += 1

        # 创建追踪span
        with SecsMessageSpan(
            equipment_id=self.config.host,
            message_id=message.sf,
            stream=message.header.s_number,
            function=message.header.f_number,
            direction="receive",
            session_id=self.config.device_id,
        ) as span:
            try:
                # Let GEM handler process the message
                reply = await self._gem_handler.handle_message(message)

                # Send reply if needed
                if reply and message.header.requires_response:
                    await self.send_message(reply)

                # Call user callback
                if self._on_message:
                    await self._on_message(message)

                logger.debug(
                    "secs_message_received",
                    equipment_id=self.config.host,
                    message_id=message.sf,
                    stream=message.header.s_number,
                    function=message.header.f_number,
                    has_reply=reply is not None,
                )

            except Exception as e:
                logger.error(
                    "secs_message_handling_error",
                    equipment_id=self.config.host,
                    message_id=message.sf,
                    error=str(e),
                )
                self._stats["errors"] += 1
                metrics.record_secs_message_error(self.config.host, "handling_error")

                if self._on_error:
                    await self._on_error(e)

    async def _handle_state_change(self, state: HSMSConnectionState) -> None:
        """Handle HSMS connection state change.

        Args:
            state: New connection state
        """
        logger.debug(f"HSMS state: {state.value}")

        if state == HSMSConnectionState.NOT_CONNECTED:
            self._connected = False

            if self.config.reconnect_enabled and not self._stop_reconnect:
                await self._schedule_reconnect()

            await self._gem_handler.state_machine.post_event(GemEvent.CONNECTION_LOST)

    # Abstract methods for custom driver implementations

    @abstractmethod
    async def send_raw(self, data: bytes) -> None:
        """Send raw bytes to equipment.

        Override this method for custom transport implementations.

        Args:
            data: Raw bytes to send
        """
        raise NotImplementedError

    @abstractmethod
    async def receive_raw(self, length: int, timeout: float) -> bytes:
        """Receive raw bytes from equipment.

        Override this method for custom transport implementations.

        Args:
            length: Number of bytes to receive
            timeout: Receive timeout

        Returns:
            Received bytes
        """
        raise NotImplementedError

    # Convenience methods for equipment control

    async def go_online(self, remote: bool = True) -> bool:
        """Set equipment to online state.

        Args:
            remote: True for REMOTE, False for LOCAL

        Returns:
            True if successful
        """
        from myeap.secs.gem.messages import GemMessages

        msg = GemMessages.create_s1f17(remote)

        try:
            reply = await self.send_command(msg, timeout=10.0)
            if reply and len(reply.body) > 0:
                mode = reply.body[0].get_single_value()
                return mode == (1 if remote else 0)
        except Exception as e:
            logger.error(f"Go online failed: {e}")

        return False

    async def go_offline(self) -> bool:
        """Set equipment to offline state.

        Returns:
            True if successful
        """
        from myeap.secs.gem.messages import GemMessages

        msg = SecsMessage.create(
            s_number=1,
            f_number=15,
            requires_response=True,
            wait_for_reply=True,
        )

        try:
            await self.send_command(msg, timeout=10.0)
            return True
        except Exception as e:
            logger.error(f"Go offline failed: {e}")
            return False

    async def get_status_variables(self) -> Dict[int, Any]:
        """Get equipment status variables.

        Returns:
            Dict of VID -> value
        """
        variables = {}
        for vid, var in self._gem_handler._data_variables.items():
            variables[vid] = var.value
        return variables

    async def set_equipment_constant(self, ecid: int, value: Any) -> bool:
        """Set an equipment constant.

        Args:
            ecid: Constant ID
            value: New value

        Returns:
            True if successful
        """
        from myeap.secs.gem.messages import GemMessages

        msg = GemMessages.create_s2f15([(ecid, value)])

        try:
            reply = await self.send_command(msg, timeout=10.0)
            if reply and len(reply.body) > 0:
                ack = reply.body[0].get_single_value()
                return ack == 0
        except Exception as e:
            logger.error(f"Set EC failed: {e}")

        return False

    # Context manager support

    async def __aenter__(self) -> "SecsDriver":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


__all__ = [
    "SecsDriver",
    "DriverConfig",
]
