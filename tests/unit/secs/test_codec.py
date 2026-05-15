"""Tests for SECS-II codec."""
import pytest
import struct

from myeap.secs.protocol.codec import SecsCodec, SecsCodecError
from myeap.secs.protocol.message import (
    SecsMessage,
    SecsItem,
    SecsFormat,
    secs_list,
    secs_binary,
    secs_ascii,
    secs_uint1,
    secs_uint2,
    secs_uint4,
    secs_uint8,
    secs_int1,
    secs_int2,
    secs_int4,
    secs_int8,
    secs_float4,
    secs_float8,
    secs_boolean,
)


class TestSecsCodec:
    """Tests for SecsCodec."""

    @pytest.fixture
    def codec(self):
        """Create codec instance."""
        return SecsCodec()

    # Binary encoding tests

    def test_encode_binary(self, codec):
        """Test encoding binary data."""
        item = secs_binary(b"\x01\x02\x03")
        encoded = codec.encode_item(item)

        # Should have format byte + length byte + data
        assert len(encoded) == 5
        assert encoded[0] == SecsFormat.BINARY | 3  # Format with length 3

    def test_decode_binary(self, codec):
        """Test decoding binary data."""
        # Manually create encoded binary
        data = bytes([SecsFormat.BINARY | 3, 0x01, 0x02, 0x03])
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.BINARY
        assert item.value == b"\x01\x02\x03"
        assert consumed == 4

    def test_encode_decode_binary_roundtrip(self, codec):
        """Test binary encode/decode roundtrip."""
        original = secs_binary(b"\x00\xFF\xAB\xCD")
        encoded = codec.encode_item(original)
        decoded, consumed = codec.decode_item(encoded)

        assert item.value == b"\x00\xFF\xAB\xCD" for item in [decoded]
        assert consumed == len(encoded)

    # ASCII encoding tests

    def test_encode_ascii(self, codec):
        """Test encoding ASCII strings."""
        item = secs_ascii("HELLO")
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.ASCII | 5  # Format with length 5
        assert encoded[1:6] == b"HELLO"

    def test_decode_ascii(self, codec):
        """Test decoding ASCII strings."""
        data = bytes([SecsFormat.ASCII | 5]) + b"HELLO"
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.ASCII
        assert item.value == "HELLO"
        assert consumed == 6

    def test_encode_decode_ascii_roundtrip(self, codec):
        """Test ASCII encode/decode roundtrip."""
        original = secs_ascii("Test String 123")
        encoded = codec.encode_item(original)
        decoded, consumed = codec.decode_item(encoded)

        assert decoded.value == "Test String 123"

    # Integer encoding tests

    def test_encode_uint1(self, codec):
        """Test encoding UINT1."""
        item = secs_uint1(255)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.UINT1 | 1
        assert encoded[1] == 0xFF

    def test_decode_uint1(self, codec):
        """Test decoding UINT1."""
        data = bytes([SecsFormat.UINT1 | 1, 0x42])
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.UINT1
        assert item.get_single_value() == 0x42

    def test_encode_uint2(self, codec):
        """Test encoding UINT2."""
        item = secs_uint2(0x1234)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.UINT2 | 2
        assert struct.unpack(">H", encoded[1:3])[0] == 0x1234

    def test_decode_uint2(self, codec):
        """Test decoding UINT2."""
        data = bytes([SecsFormat.UINT2 | 2, 0x12, 0x34])
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.UINT2
        assert item.get_single_value() == 0x1234

    def test_encode_uint4(self, codec):
        """Test encoding UINT4."""
        item = secs_uint4(0x12345678)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.UINT4 | 4
        assert struct.unpack(">I", encoded[1:5])[0] == 0x12345678

    def test_decode_uint4(self, codec):
        """Test decoding UINT4."""
        data = bytes([SecsFormat.UINT4 | 4]) + struct.pack(">I", 0x12345678)
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.UINT4
        assert item.get_single_value() == 0x12345678

    def test_encode_uint8(self, codec):
        """Test encoding UINT8."""
        item = secs_uint8(0x123456789ABCDEF0)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.UINT8 | 8
        assert struct.unpack(">Q", encoded[1:9])[0] == 0x123456789ABCDEF0

    def test_encode_int1_negative(self, codec):
        """Test encoding INT1 with negative value."""
        item = secs_int1(-1)
        encoded = codec.encode_item(item)

        # Negative values use INT1 format
        assert encoded[0] & 0xF0 == 0x60  # INT1 format
        assert encoded[1] == 0xFF  # -1 in signed byte

    def test_encode_int2(self, codec):
        """Test encoding INT2."""
        item = secs_int2(-1000)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.INT2 | 2
        assert struct.unpack(">h", encoded[1:3])[0] == -1000

    def test_encode_int4(self, codec):
        """Test encoding INT4."""
        item = secs_int4(-2147483648)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.INT4 | 4
        assert struct.unpack(">i", encoded[1:5])[0] == -2147483648

    def test_encode_int8(self, codec):
        """Test encoding INT8."""
        item = secs_int8(-9223372036854775808)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.INT8 | 8
        assert struct.unpack(">q", encoded[1:9])[0] == -9223372036854775808

    # Float encoding tests

    def test_encode_float4(self, codec):
        """Test encoding FLOAT4."""
        item = secs_float4(3.14)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.FLOAT4 | 4
        packed = struct.unpack(">f", encoded[1:5])[0]
        assert abs(packed - 3.14) < 0.001

    def test_decode_float4(self, codec):
        """Test decoding FLOAT4."""
        import struct
        data = bytes([SecsFormat.FLOAT4 | 4]) + struct.pack(">f", 2.718)
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.FLOAT4
        assert abs(item.get_single_value() - 2.718) < 0.001

    def test_encode_float8(self, codec):
        """Test encoding FLOAT8."""
        item = secs_float8(3.14159265358979)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.FLOAT8 | 8
        packed = struct.unpack(">d", encoded[1:9])[0]
        assert abs(packed - 3.14159265358979) < 1e-10

    # Boolean encoding tests

    def test_encode_boolean_true(self, codec):
        """Test encoding boolean true."""
        item = secs_boolean(True)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.Boolean | 1
        assert encoded[1] == 0x01

    def test_encode_boolean_false(self, codec):
        """Test encoding boolean false."""
        item = secs_boolean(False)
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.Boolean | 1
        assert encoded[1] == 0x00

    def test_decode_boolean(self, codec):
        """Test decoding boolean."""
        data = bytes([SecsFormat.Boolean | 1, 0x01])
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.Boolean
        assert item.get_single_value() is True

    # List encoding tests

    def test_encode_empty_list(self, codec):
        """Test encoding empty list."""
        item = secs_list([])
        encoded = codec.encode_item(item)

        assert encoded[0] == SecsFormat.LIST | 0

    def test_encode_nested_list(self, codec):
        """Test encoding nested list."""
        inner = secs_list([secs_uint4(1), secs_uint4(2)])
        outer = secs_list([secs_ascii("header"), inner])

        encoded = codec.encode_item(outer)

        # First byte is LIST format with length
        assert encoded[0] == SecsFormat.LIST

    def test_decode_list(self, codec):
        """Test decoding list."""
        # Create a list: [ASCII("A"), UINT4(1)]
        inner = secs_list([secs_ascii("A"), secs_uint4(1)])
        encoded = codec.encode_item(inner)
        item, consumed = codec.decode_item(encoded)

        assert item.format == SecsFormat.LIST
        assert len(item.value) == 2
        assert item.value[0].value == "A"
        assert item.value[1].value == [1]

    # Multi-item encoding tests

    def test_encode_multiple_uint4(self, codec):
        """Test encoding multiple UINT4 values."""
        item = secs_uint4([100, 200, 300])
        encoded = codec.encode_item(item)

        # Should encode all three 4-byte values
        assert len(encoded) == 1 + 12  # Format byte + 3 * 4 bytes

    def test_decode_multiple_uint4(self, codec):
        """Test decoding multiple UINT4 values."""
        data = bytes([SecsFormat.UINT4 | 3]) + struct.pack(">III", 100, 200, 300)
        item, consumed = codec.decode_item(data)

        assert item.format == SecsFormat.UINT4
        values = item.get_single_value()
        assert values == [100, 200, 300]

    # Error handling tests

    def test_decode_invalid_length(self, codec):
        """Test decoding with invalid length."""
        # Format byte says 10 bytes but only 2 provided
        data = bytes([SecsFormat.BINARY | 10, 0x01])

        with pytest.raises(SecsCodecError):
            codec.decode_item(data)

    def test_decode_empty_data(self, codec):
        """Test decoding empty data."""
        with pytest.raises(SecsCodecError):
            codec.decode_item(b"")

    def test_encode_unknown_format(self, codec):
        """Test encoding with unknown format."""
        item = SecsItem(0xFF, b"test")  # Invalid format

        with pytest.raises(SecsCodecError):
            codec.encode_item(item)

    # Roundtrip tests

    def test_roundtrip_message(self, codec):
        """Test full message encode/decode roundtrip."""
        msg = SecsMessage.create(
            s_number=1,
            f_number=13,
            device_id=0,
            body=[
                secs_ascii("MDL1"),
                secs_ascii("REV1"),
                secs_uint4(100),
                secs_list([
                    secs_uint2(1),
                    secs_uint2(2),
                ]),
            ],
        )

        encoded = msg.encode()
        decoded = SecsMessage.decode(encoded)

        assert decoded.stream == 1
        assert decoded.function == 13
        assert decoded.body[0].value == "MDL1"
        assert decoded.body[1].value == "REV1"
        assert decoded.body[2].value == [100]
        assert decoded.body[3].is_list
        assert decoded.body[3].value[0].value == [1]
        assert decoded.body[3].value[1].value == [2]

    def test_roundtrip_large_binary(self, codec):
        """Test encoding large binary data."""
        large_data = bytes(range(256))  # 256 bytes
        item = secs_binary(large_data)

        encoded = codec.encode_item(item)
        decoded, consumed = codec.decode_item(encoded)

        assert decoded.value == large_data
        assert consumed == len(encoded)
