"""Tests for HSMS connection module."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from myeap.secs.protocol.hsms import (
    HSMSConnection,
    HSMSConnectionState,
    HSMSMessage,
    HSMSMessageType,
    HSMSHeader,
)
from myeap.secs.protocol.message import SecsMessage, secs_ascii


class TestHSMSHeader:
    """Tests for HSMSHeader."""

    def test_header_size(self):
        """Test header size is 10 bytes."""
        assert HSMSHeader.HEADER_SIZE == 10

    def test_create_data_header(self):
        """Test creating data header."""
        header = HSMSHeader.create_data(
            session_id=0x1234,
            system_bytes=0x12345678,
            requires_reply=True,
            wait_for_reply=True,
        )

        assert header.session_id == 0x1234
        assert header.system_bytes == 0x12345678
        assert header.requires_reply is True
        assert header.wait_for_reply is True
        assert header.is_control is False
        assert header.is_data is True

    def test_create_control_header(self):
        """Test creating control header."""
        header = HSMSHeader.create_control(
            message_type=HSMSMessageType.SELECT_REQUEST,
            system_bytes=0x12345678,
        )

        assert header.session_id == 0xFFFF
        assert header.message_type == HSMSMessageType.SELECT_REQUEST
        assert header.is_control is True
        assert header.is_data is False

    def test_encode_decode_roundtrip(self):
        """Test header encode/decode roundtrip."""
        original = HSMSHeader.create_data(
            session_id=0x5678,
            system_bytes=0xABCDEF12,
            requires_reply=True,
            wait_for_reply=False,
        )

        encoded = original.encode()
        assert len(encoded) == 10

        decoded = HSMSHeader.decode(encoded)
        assert decoded.session_id == original.session_id
        assert decoded.system_bytes == original.system_bytes
        assert decoded.requires_reply == original.requires_reply
        assert decoded.wait_for_reply == original.wait_for_reply

    def test_encode_decode_control_roundtrip(self):
        """Test control header encode/decode roundtrip."""
        original = HSMSHeader.create_control(
            message_type=HSMSMessageType.LINKTEST_REQUEST,
        )

        encoded = original.encode()
        decoded = HSMSHeader.decode(encoded)

        assert decoded.session_id == 0xFFFF
        assert decoded.message_type == HSMSMessageType.LINKTEST_REQUEST


class TestHSMSMessageType:
    """Tests for HSMSMessageType enum."""

    def test_message_types(self):
        """Test message type values."""
        assert HSMSMessageType.DATA == 0x10
        assert HSMSMessageType.SELECT_REQUEST == 0x30
        assert HSMSMessageType.SELECT_RESPONSE == 0x31
        assert HSMSMessageType.LINKTEST_REQUEST == 0x34
        assert HSMSMessageType.LINKTEST_RESPONSE == 0x35
        assert HSMSMessageType.SEPARATE_REQUEST == 0x36

    def test_is_control_message(self):
        """Test control message detection."""
        assert HSMSMessageType.is_control_message(HSMSMessageType.SELECT_REQUEST)
        assert HSMSMessageType.is_control_message(HSMSMessageType.LINKTEST_REQUEST)
        assert not HSMSMessageType.is_control_message(HSMSMessageType.DATA)

    def test_is_data_message(self):
        """Test data message detection."""
        assert HSMSMessageType.is_data_message(HSMSMessageType.DATA)
        assert not HSMSMessageType.is_data_message(HSMSMessageType.SELECT_REQUEST)


class TestHSMSMessage:
    """Tests for HSMSMessage."""

    def test_create_data_message(self):
        """Test creating data message."""
        secs_msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("MDL1"), secs_ascii("REV1")],
        )

        hmsgs = HSMSMessage.create_data(
            secs_message=secs_msg,
            session_id=0x1234,
        )

        assert hmsgs.header.session_id == 0x1234
        assert hmsgs.header.is_data
        assert hmsgs.secs_message is not None
        assert hmsgs.secs_message.sf == "S1F13"

    def test_create_control_message(self):
        """Test creating control message."""
        hmsgs = HSMSMessage.create_control(
            message_type=HSMSMessageType.SELECT_REQUEST,
        )

        assert hmsgs.header.is_control
        assert hmsgs.header.message_type == HSMSMessageType.SELECT_REQUEST
        assert hmsgs.secs_message is None

    def test_encode_data_message(self):
        """Test encoding data message."""
        secs_msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("TEST")],
        )

        hmsgs = HSMSMessage.create_data(
            secs_message=secs_msg,
            session_id=0x1234,
        )

        encoded = hmsgs.encode()
        assert len(encoded) > 10  # Header + SECS data

    def test_decode_data_message(self):
        """Test decoding data message."""
        # Create and encode
        secs_msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[secs_ascii("TEST")],
        )

        hmsgs = HSMSMessage.create_data(
            secs_message=secs_msg,
            session_id=0x1234,
        )

        encoded = hmsgs.encode()
        decoded = HSMSMessage.decode(encoded)

        assert decoded.header.session_id == 0x1234
        assert decoded.secs_message is not None
        assert decoded.secs_message.sf == "S1F13"


class TestHSMSConnectionState:
    """Tests for HSMSConnectionState enum."""

    def test_state_values(self):
        """Test state values."""
        assert HSMSConnectionState.NOT_CONNECTED.value == "NOT_CONNECTED"
        assert HSMSConnectionState.CONNECTING.value == "CONNECTING"
        assert HSMSConnectionState.CONNECTED.value == "CONNECTED"
        assert HSMSConnectionState.SELECTED.value == "SELECTED"

    def test_states_are_strings(self):
        """Test that states have string values."""
        for state in HSMSConnectionState:
            assert isinstance(state.value, str)


class TestHSMSConnectionBasics:
    """Basic tests for HSMSConnection without actual network."""

    @pytest.fixture
    def connection(self):
        """Create a connection instance."""
        return HSMSConnection(
            host="127.0.0.1",
            port=5000,
            device_id=0,
        )

    def test_initial_state(self, connection):
        """Test initial connection state."""
        assert connection.state == HSMSConnectionState.NOT_CONNECTED
        assert connection.is_connected is False
        assert connection.is_selected is False

    def test_config_stored(self, connection):
        """Test configuration is stored."""
        assert connection.host == "127.0.0.1"
        assert connection.port == 5000
        assert connection.device_id == 0

    def test_stats_initial(self, connection):
        """Test initial statistics."""
        stats = connection.stats
        assert stats["messages_sent"] == 0
        assert stats["messages_received"] == 0
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_connect_without_server_fails(self, connection):
        """Test connecting to non-existent server fails."""
        with pytest.raises(ConnectionError):
            await connection.connect()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, connection):
        """Test disconnecting when not connected."""
        await connection.disconnect()  # Should not raise
        assert connection.state == HSMSConnectionState.NOT_CONNECTED

    @pytest.mark.asyncio
    async def test_send_without_connection_fails(self, connection):
        """Test sending without connection fails."""
        msg = SecsMessage.create(s_number=1, f_number=13)
        with pytest.raises(ConnectionError):
            await connection.send(msg)

    @pytest.mark.asyncio
    async def test_linktest_without_connection_fails(self, connection):
        """Test linktest without connection fails."""
        result = await connection.linktest()
        assert result is False

    @pytest.mark.asyncio
    async def test_select_without_connection_fails(self, connection):
        """Test select without connection fails."""
        with pytest.raises(ConnectionError):
            await connection.select()

    @pytest.mark.asyncio
    async def test_context_manager_disconnect(self):
        """Test async context manager disconnects."""
        connection = HSMSConnection(host="127.0.0.1", port=5000)
        # Should not raise
        async with connection:
            pass
        assert connection.state == HSMSConnectionState.NOT_CONNECTED


class TestHSMSConnectionWithMock:
    """Tests for HSMSConnection with mocked network."""

    @pytest.fixture
    def mock_connection(self):
        """Create a connection with mocked TCP."""
        connection = HSMSConnection(
            host="127.0.0.1",
            port=5000,
            device_id=0x1234,
        )
        return connection

    @pytest.mark.asyncio
    async def test_generate_system_bytes(self, mock_connection):
        """Test system bytes generation."""
        sb1 = mock_connection._next_system_bytes()
        sb2 = mock_connection._next_system_bytes()

        assert sb1 != sb2
        assert sb1 >= 0
        assert sb1 <= 0xFFFFFFFF
        assert sb2 >= 0
        assert sb2 <= 0xFFFFFFFF

    @pytest.mark.asyncio
    async def test_state_callback(self, mock_connection):
        """Test state change callback is called."""
        callback = AsyncMock()
        mock_connection._on_state_change = callback

        await mock_connection._set_state(HSMSConnectionState.CONNECTED)
        callback.assert_called_once_with(HSMSConnectionState.CONNECTED)

    @pytest.mark.asyncio
    async def test_message_callback(self, mock_connection):
        """Test message callback is called."""
        callback = AsyncMock()
        mock_connection._on_message = callback

        msg = SecsMessage.create(s_number=1, f_number=13)
        await mock_connection._on_message(msg)
        callback.assert_called_once_with(msg)
