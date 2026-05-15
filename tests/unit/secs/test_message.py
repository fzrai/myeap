"""Tests for SECS-II message definitions."""
import pytest
import struct

from myeap.secs.protocol.message import (
    SecsMessage,
    SecsItem,
    SecsHeader,
    SecsFormat,
    SecsDirection,
    secs_list,
    secs_binary,
    secs_ascii,
    secs_uint1,
    secs_uint2,
    secs_uint4,
    secs_int4,
    secs_float8,
    secs_boolean,
)


class TestSecsFormat:
    """Tests for SecsFormat enum."""

    def test_format_values(self):
        """Test that format codes have expected values."""
        assert SecsFormat.LIST == 0x00
        assert SecsFormat.BINARY == 0x20
        assert SecsFormat.Boolean == 0x24
        assert SecsFormat.ASCII == 0x40
        assert SecsFormat.INT1 == 0x60
        assert SecsFormat.INT2 == 0x58
        assert SecsFormat.INT4 == 0x54
        assert SecsFormat.INT8 == 0x50
        assert SecsFormat.UINT1 == 0x80
        assert SecsFormat.UINT2 == 0x78
        assert SecsFormat.UINT4 == 0x74
        assert SecsFormat.UINT8 == 0x70
        assert SecsFormat.FLOAT4 == 0xA0
        assert SecsFormat.FLOAT8 == 0x90

    def test_is_numeric(self):
        """Test numeric type detection."""
        assert SecsFormat.is_numeric(SecsFormat.INT1)
        assert SecsFormat.is_numeric(SecsFormat.INT2)
        assert SecsFormat.is_numeric(SecsFormat.INT4)
        assert SecsFormat.is_numeric(SecsFormat.UINT4)
        assert SecsFormat.is_numeric(SecsFormat.FLOAT4)
        assert not SecsFormat.is_numeric(SecsFormat.ASCII)
        assert not SecsFormat.is_numeric(SecsFormat.BINARY)

    def test_is_integer(self):
        """Test integer type detection."""
        assert SecsFormat.is_integer(SecsFormat.INT1)
        assert SecsFormat.is_integer(SecsFormat.UINT4)
        assert not SecsFormat.is_integer(SecsFormat.FLOAT4)

    def test_is_float(self):
        """Test float type detection."""
        assert SecsFormat.is_float(SecsFormat.FLOAT4)
        assert SecsFormat.is_float(SecsFormat.FLOAT8)
        assert not SecsFormat.is_float(SecsFormat.INT4)


class TestSecsHeader:
    """Tests for SecsHeader."""

    def test_header_size(self):
        """Test header size is 10 bytes."""
        assert SecsHeader.HEADER_SIZE == 10

    def test_create_header(self):
        """Test creating a header."""
        header = SecsHeader(
            device_id=1,
            s_number=1,
            f_number=13,
            system_bytes=0x123456,
            requires_response=True,
            wait_for_reply=True,
        )

        assert header.device_id == 1
        assert header.s_number == 1
        assert header.f_number == 13
        assert header.system_bytes == 0x123456
        assert header.requires_response is True
        assert header.wait_for_reply is True

    def test_encode_decode(self):
        """Test header encoding and decoding."""
        header = SecsHeader(
            device_id=0x1234,
            s_number=1,
            f_number=13,
            system_bytes=0x12345678,
            requires_response=True,
            wait_for_reply=True,
        )

        encoded = header.encode_header()
        assert len(encoded) == 10

        decoded = SecsHeader.decode_header(encoded)
        assert decoded.device_id == header.device_id
        assert decoded.s_number == header.s_number
        assert decoded.f_number == header.f_number
        assert decoded.system_bytes == header.system_bytes
        assert decoded.requires_response == header.requires_response
        assert decoded.wait_for_reply == header.wait_for_reply

    def test_primary_secondary(self):
        """Test primary/secondary message detection."""
        primary = SecsHeader(s_number=1, f_number=2)
        secondary = SecsHeader(s_number=1, f_number=3)

        assert primary.is_primary
        assert primary.is_secondary is False
        assert secondary.is_primary is False
        assert secondary.is_secondary


class TestSecsItem:
    """Tests for SecsItem."""

    def test_create_list(self):
        """Test creating a LIST item."""
        item = SecsItem(SecsFormat.LIST, [])
        assert item.is_list
        assert item.item_count == 0

        item = SecsItem(SecsFormat.LIST, [secs_ascii("test")])
        assert item.item_count == 1

    def test_create_binary(self):
        """Test creating a BINARY item."""
        item = secs_binary(b"\x01\x02\x03")
        assert item.format == SecsFormat.BINARY
        assert item.value == b"\x01\x02\x03"
        assert item.item_count == 3

    def test_create_ascii(self):
        """Test creating an ASCII item."""
        item = secs_ascii("HELLO")
        assert item.format == SecsFormat.ASCII
        assert item.value == "HELLO"
        assert item.item_count == 5

    def test_create_numeric(self):
        """Test creating numeric items."""
        item = secs_uint4(12345)
        assert item.format == SecsFormat.UINT4
        assert item.value == 12345

        item = secs_int4(-1000)
        assert item.format == SecsFormat.INT4
        assert item.value == -1000

    def test_get_single_value(self):
        """Test getting single value from item."""
        item = secs_uint4(42)
        assert item.get_single_value() == 42

        item = secs_ascii("test")
        assert item.get_single_value() == "test"


class TestSecsMessage:
    """Tests for SecsMessage."""

    def test_create_message(self):
        """Test creating a SECS message."""
        msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            device_id=0,
            body=[secs_ascii("MDL1"), secs_ascii("REV1")],
        )

        assert msg.stream == 1
        assert msg.function == 13
        assert msg.sf == "S1F13"
        assert len(msg.body) == 2

    def test_create_reply(self):
        """Test creating a reply message."""
        original = SecsMessage.create(
            s_number=1,
            f_number=13,
            device_id=0,
        )
        original.header.system_bytes = 0x123456

        reply = SecsMessage.create_reply(original)

        assert reply.stream == 1
        assert reply.function == 14  # Reply is F+1
        assert reply.header.system_bytes == 0x123456  # Same correlation

    def test_encode_decode(self):
        """Test message encoding and decoding."""
        original = SecsMessage.create(
            s_number=1,
            f_number=13,
            device_id=0,
            body=[secs_ascii("MDL1"), secs_ascii("REV1")],
        )

        encoded = original.encode()
        assert len(encoded) > SecsHeader.HEADER_SIZE

        decoded = SecsMessage.decode(encoded)
        assert decoded.stream == 1
        assert decoded.function == 13
        assert len(decoded.body) == 2
        assert decoded.body[0].value == "MDL1"
        assert decoded.body[1].value == "REV1"

    def test_encode_decode_numeric(self):
        """Test encoding and decoding numeric values."""
        original = SecsMessage.create(
            s_number=2,
            f_number=15,
            body=[
                secs_uint4(100),
                secs_int4(-500),
                secs_float8(3.14159),
            ],
        )

        encoded = original.encode()
        decoded = SecsMessage.decode(encoded)

        assert decoded.body[0].get_single_value() == 100
        assert decoded.body[1].get_single_value() == -500
        # Float comparison with tolerance
        assert abs(decoded.body[2].get_single_value() - 3.14159) < 0.0001

    def test_encode_decode_binary(self):
        """Test encoding and decoding binary data."""
        original = SecsMessage.create(
            s_number=7,
            f_number=3,
            body=[secs_ascii("PPID"), secs_binary(b"\x00\x01\x02\x03\xFF")],
        )

        encoded = original.encode()
        decoded = SecsMessage.decode(encoded)

        assert decoded.body[0].value == "PPID"
        assert decoded.body[1].value == b"\x00\x01\x02\x03\xFF"

    def test_encode_decode_list(self):
        """Test encoding and decoding nested lists."""
        inner = secs_list([secs_uint4(1), secs_uint4(2)])
        outer = secs_list([secs_ascii("header"), inner])

        original = SecsMessage.create(
            s_number=6,
            f_number=1,
            body=[outer],
        )

        encoded = original.encode()
        decoded = SecsMessage.decode(encoded)

        assert len(decoded.body) == 1
        outer_item = decoded.body[0]
        assert outer_item.is_list
        assert outer_item.value[0].value == "header"
        assert outer_item.value[1].value[0].value == 1
        assert outer_item.value[1].value[1].value == 2

    def test_get_value(self):
        """Test getting values from message."""
        msg = SecsMessage.create(
            s_number=1,
            f_number=2,
            body=[
                secs_ascii("MDL1"),
                secs_ascii("REV1"),
            ],
        )

        assert msg.get_value(0) == "MDL1"
        assert msg.get_value(1) == "REV1"
        assert msg.get_value(2) is None


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_secs_list(self):
        """Test secs_list helper."""
        item = secs_list([secs_ascii("a"), secs_uint4(1)])
        assert item.format == SecsFormat.LIST
        assert len(item.value) == 2

    def test_secs_binary(self):
        """Test secs_binary helper with different inputs."""
        assert secs_binary(b"\x01\x02").value == b"\x01\x02"
        assert secs_binary(bytearray([3, 4])).value == b"\x03\x04"
        assert secs_binary([5, 6]).value == b"\x05\x06"

    def test_secs_boolean(self):
        """Test secs_boolean helper."""
        assert secs_boolean(True).value is True
        assert secs_boolean(False).value is False

    def test_secs_ascii(self):
        """Test secs_ascii helper."""
        item = secs_ascii("HELLO")
        assert item.value == "HELLO"

    def test_secs_numeric_helpers(self):
        """Test numeric helper functions."""
        assert secs_uint1(255).value == 255
        assert secs_uint2(65535).value == 65535
        assert secs_uint4(4294967295).value == 4294967295
        assert secs_uint8(2**64 - 1).value == 2**64 - 1

        assert secs_int4(-1).value == -1
        assert secs_int4(-2147483648).value == -2147483648

    def test_secs_float_helpers(self):
        """Test float helper functions."""
        assert secs_float4(3.14).value == pytest.approx(3.14, rel=1e-6)
        assert secs_float8(2.718281828).value == pytest.approx(2.718281828, rel=1e-9)
