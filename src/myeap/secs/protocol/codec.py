"""SECS-II Codec Implementation

This module provides encoding and decoding of SECS-II data items
according to SEMI E5 standard.

SECS-II uses a compact binary encoding with format/length indicators:
- Single-byte indicator for items <= 255 bytes
- Two-byte indicator for items <= 65535 bytes
- Three-byte indicator for longer items (rarely used)
"""

from __future__ import annotations

import struct
from typing import List, Optional, Union, Any
import io

from myeap.secs.protocol.message import SecsFormat, SecsItem, SecsMessage


class SecsCodecError(ValueError):
    """Error during SECS-II encoding/decoding."""
    pass


class SecsCodec:
    """SECS-II data encoder and decoder.

    Handles encoding of Python values to SECS-II binary format and
    decoding of SECS-II binary format to Python values.

    Format/Length indicator encoding:
    - 1 byte: [Format][Length] for length <= 252
    - 2 bytes: 0xFF followed by [Length MSB][Length LSB] for length <= 65534
    - 3 bytes: 0xFE followed by 24-bit length for longer items
    """

    # Length indicator values
    LENGTH_1_BYTE = 0x01  # Single byte length
    LENGTH_2_BYTES = 0xFF  # Two byte length follows
    LENGTH_3_BYTES = 0xFE  # Three byte length follows

    # Maximum lengths
    MAX_1_BYTE_LENGTH = 252
    MAX_2_BYTE_LENGTH = 65534

    def __init__(self):
        """Initialize SECS-II codec."""
        pass

    def encode_items(self, items: List[SecsItem]) -> bytes:
        """Encode a list of SECS items to binary format.

        Args:
            items: List of SecsItem to encode

        Returns:
            Binary encoded data
        """
        result = bytearray()
        for item in items:
            result.extend(self.encode_item(item))
        return bytes(result)

    def encode_item(self, item: SecsItem) -> bytes:
        """Encode a single SECS item to binary format.

        Args:
            item: SecsItem to encode

        Returns:
            Binary encoded item
        """
        format_code = item.format
        value = item.value

        # Encode based on format
        if format_code == SecsFormat.LIST:
            return self._encode_list(value)

        elif format_code == SecsFormat.BINARY:
            return self._encode_binary(value)

        elif format_code == SecsFormat.Boolean:
            return self._encode_boolean(value)

        elif format_code == SecsFormat.ASCII:
            return self._encode_ascii(value)

        elif format_code == SecsFormat.JIS8:
            return self._encode_jis8(value)

        elif format_code == SecsFormat.INT1:
            return self._encode_int(value, 1, "b")

        elif format_code == SecsFormat.INT2:
            return self._encode_int(value, 2, ">h")

        elif format_code == SecsFormat.INT4:
            return self._encode_int(value, 4, ">i")

        elif format_code == SecsFormat.INT8:
            return self._encode_int(value, 8, ">q")

        elif format_code == SecsFormat.UINT1:
            return self._encode_int(value, 1, "B")

        elif format_code == SecsFormat.UINT2:
            return self._encode_int(value, 2, ">H")

        elif format_code == SecsFormat.UINT4:
            return self._encode_int(value, 4, ">I")

        elif format_code == SecsFormat.UINT8:
            return self._encode_int(value, 8, ">Q")

        elif format_code == SecsFormat.FLOAT4:
            return self._encode_float(value, 4, ">f")

        elif format_code == SecsFormat.FLOAT8:
            return self._encode_float(value, 8, ">d")

        else:
            raise SecsCodecError(f"Unsupported format: {format_code}")

    def _encode_length_header(self, length: int, format_code: int) -> bytes:
        """Encode length header for an item.

        Args:
            length: Length of data in bytes
            format_code: SECS-II format code

        Returns:
            Length header bytes
        """
        if length <= self.MAX_1_BYTE_LENGTH:
            # Single byte: [Format][Length]
            return bytes([format_code | length])

        elif length <= self.MAX_2_BYTE_LENGTH:
            # Two bytes: 0xFF + 2-byte length
            return bytes([self.LENGTH_2_BYTES, format_code | 0x01]) + struct.pack(">H", length)

        else:
            # Three bytes: 0xFE + 3-byte length
            return bytes([self.LENGTH_3_BYTES, format_code | 0x01]) + struct.pack(">I", length)[1:]

    def _encode_list(self, items: Union[List[SecsItem], List[Any]]) -> bytes:
        """Encode a LIST item.

        Args:
            items: List of items

        Returns:
            Encoded list
        """
        if not isinstance(items, list):
            items = [items]

        result = bytearray()
        for item in items:
            if isinstance(item, SecsItem):
                result.extend(self.encode_item(item))
            else:
                # Auto-detect type for primitive values
                encoded = self._auto_encode(item)
                result.extend(encoded)

        length = len(result)
        header = self._encode_length_header(length, SecsFormat.LIST)

        return bytes(header) + bytes(result)

    def _encode_binary(self, value: Union[bytes, bytearray, List[int]]) -> bytes:
        """Encode a BINARY item.

        Args:
            value: Binary data

        Returns:
            Encoded binary
        """
        if isinstance(value, bytearray):
            data = bytes(value)
        elif isinstance(value, list):
            data = bytes(value)
        elif isinstance(value, bytes):
            data = value
        else:
            data = bytes([value])

        header = self._encode_length_header(len(data), SecsFormat.BINARY)
        return header + data

    def _encode_boolean(self, value: Union[bool, List[bool]]) -> bytes:
        """Encode a BOOLEAN item.

        Args:
            value: Boolean value(s)

        Returns:
            Encoded boolean
        """
        if isinstance(value, bool):
            values = [value]
        else:
            values = list(value)

        data = bytes([0x01 if v else 0x00 for v in values])
        header = self._encode_length_header(len(data), SecsFormat.Boolean)

        return header + data

    def _encode_ascii(self, value: str) -> bytes:
        """Encode an ASCII item.

        Args:
            value: ASCII string

        Returns:
            Encoded ASCII
        """
        if isinstance(value, str):
            data = value.encode("ascii")
        else:
            data = bytes(value)

        header = self._encode_length_header(len(data), SecsFormat.ASCII)
        return header + data

    def _encode_jis8(self, value: str) -> bytes:
        """Encode a JIS8 item.

        Args:
            value: JIS8 string

        Returns:
            Encoded JIS8
        """
        if isinstance(value, str):
            data = value.encode("iso-2022-jp")
        else:
            data = bytes(value)

        header = self._encode_length_header(len(data), SecsFormat.JIS8)
        return header + data

    def _encode_int(
        self,
        value: Union[int, List[int]],
        byte_size: int,
        struct_format: str,
    ) -> bytes:
        """Encode an integer item.

        Args:
            value: Integer value(s)
            byte_size: Number of bytes per value
            struct_format: Struct format for packing

        Returns:
            Encoded integer
        """
        if isinstance(value, (int,)):
            values = [value]
        else:
            values = list(value)

        # Pack all values
        data = bytearray()
        for v in values:
            packed = struct.pack(struct_format, v)
            data.extend(packed)

        # Determine format based on byte size
        if byte_size == 1:
            format_code = SecsFormat.INT1 if values and values[0] < 0 else SecsFormat.UINT1
        elif byte_size == 2:
            format_code = SecsFormat.INT2 if values and values[0] < 0 else SecsFormat.UINT2
        elif byte_size == 4:
            format_code = SecsFormat.INT4 if values and values[0] < 0 else SecsFormat.UINT4
        else:
            format_code = SecsFormat.INT8 if values and values[0] < 0 else SecsFormat.UINT8

        header = self._encode_length_header(len(data), format_code)
        return header + bytes(data)

    def _encode_float(
        self,
        value: Union[float, List[float]],
        byte_size: int,
        struct_format: str,
    ) -> bytes:
        """Encode a float item.

        Args:
            value: Float value(s)
            byte_size: Number of bytes per value (4 or 8)
            struct_format: Struct format for packing

        Returns:
            Encoded float
        """
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values = [float(value)]
        else:
            values = [float(v) for v in value]

        # Pack all values
        data = bytearray()
        for v in values:
            packed = struct.pack(struct_format, v)
            data.extend(packed)

        format_code = SecsFormat.FLOAT4 if byte_size == 4 else SecsFormat.FLOAT8

        header = self._encode_length_header(len(data), format_code)
        return header + bytes(data)

    def _auto_encode(self, value: Any) -> bytes:
        """Auto-detect type and encode a value.

        Args:
            value: Value to encode

        Returns:
            Encoded data
        """
        if isinstance(value, bool):
            return self._encode_boolean(value)
        elif isinstance(value, int):
            if -128 <= value <= 127:
                return self._encode_int(value, 1, "b")
            elif -32768 <= value <= 32767:
                return self._encode_int(value, 2, ">h")
            elif -2147483648 <= value <= 2147483647:
                return self._encode_int(value, 4, ">i")
            else:
                return self._encode_int(value, 8, ">q")
        elif isinstance(value, float):
            return self._encode_float(value, 8, ">d")
        elif isinstance(value, str):
            return self._encode_ascii(value)
        elif isinstance(value, (bytes, bytearray)):
            return self._encode_binary(value)
        elif isinstance(value, list):
            # Assume it's a SECS list
            return self._encode_list(value)
        elif isinstance(value, SecsItem):
            return self.encode_item(value)
        else:
            raise SecsCodecError(f"Cannot encode value of type: {type(value)}")

    def decode_items(self, data: bytes) -> List[SecsItem]:
        """Decode binary data to a list of SECS items.

        Args:
            data: Binary data to decode

        Returns:
            List of decoded SecsItem objects
        """
        items = []
        offset = 0

        while offset < len(data):
            item, consumed = self.decode_item(data, offset)
            items.append(item)
            offset += consumed

        return items

    def decode_item(self, data: bytes, offset: int = 0) -> tuple[SecsItem, int]:
        """Decode a single SECS item from binary data.

        Args:
            data: Binary data
            offset: Starting offset

        Returns:
            Tuple of (decoded SecsItem, number of bytes consumed)

        Raises:
            SecsCodecError: If data is invalid
        """
        if offset >= len(data):
            raise SecsCodecError("No data to decode")

        # Read format/length indicator
        length, format_code, consumed = self._decode_length_header(data, offset)

        data_offset = offset + consumed

        # Check we have enough data
        if data_offset + length > len(data):
            raise SecsCodecError(
                f"Insufficient data: need {length} bytes, have {len(data) - data_offset}"
            )

        # Extract data portion
        item_data = data[data_offset : data_offset + length]

        # Decode based on format
        value = self._decode_value(format_code, item_data)

        item = SecsItem(SecsFormat(format_code), value)

        return item, consumed + length

    def _decode_length_header(
        self, data: bytes, offset: int
    ) -> tuple[int, int, int]:
        """Decode length header.

        Args:
            data: Binary data
            offset: Starting offset

        Returns:
            Tuple of (length, format_code, bytes_consumed)

        Raises:
            SecsCodecError: If header is invalid
        """
        if offset >= len(data):
            raise SecsCodecError("No header byte")

        first_byte = data[offset]

        # Check for multi-byte length
        if first_byte == self.LENGTH_2_BYTES:
            # 0xFF followed by format and 2-byte length
            if offset + 3 >= len(data):
                raise SecsCodecError("Incomplete 2-byte length header")
            format_code = data[offset + 1] & 0xE0
            length = struct.unpack(">H", data[offset + 2 : offset + 4])[0]
            return length, format_code, 4

        elif first_byte == self.LENGTH_3_BYTES:
            # 0xFE followed by format and 3-byte length
            if offset + 4 >= len(data):
                raise SecsCodecError("Incomplete 3-byte length header")
            format_code = data[offset + 1] & 0xE0
            length_bytes = b"\x00" + data[offset + 2 : offset + 5]
            length = struct.unpack(">I", length_bytes)[0]
            return length, format_code, 5

        else:
            # Single byte: [Format (upper 5 bits)][Length (lower 3 bits)]
            # Actually: [Format (upper 5 bits, bits 5-7)][Length (lower 8 bits, byte 1)]
            # Wait, the SECS-II format is:
            # [Format high bits][Length][Format low bits]
            # Let me reconsider...
            #
            # The format byte is: [F4 F3 F2 F1 F0][L3 L2 L1 L0]
            # Where F4-F0 is the format code without the length bits
            # and L3-L0 is the length for 1-byte encoding
            #
            # For values > 15, we use multi-byte encoding
            #
            # Actually, looking at SEMI E5 more carefully:
            # The format code uses the upper 5 bits
            # The lower bits are used differently:
            # - For 1-byte length: lower 3 bits (0-7) + carry to next byte
            # - For variable: format code indicates variable-length types
            #
            # Simpler model:
            # - If upper nibble matches a format code directly, use it
            # - Otherwise, combine with length info
            #
            # The standard approach:
            # Format = byte & 0xE0 (upper 3 bits of upper nibble)
            # Length = if format is variable-length type, it's in the data
            #          if format uses length encoding, length is byte & 0x1F

            # For standard SECS-II:
            # Upper 4 bits = format category
            # Lower 4 bits = length (0 = use next byte(s))

            upper_nibble = (first_byte & 0xF0)
            lower_nibble = (first_byte & 0x0F)

            # Check if this is a variable-length format
            if upper_nibble in [0x00, 0x20, 0x40, 0xC0, 0xE0]:
                # Variable length type
                if lower_nibble == 0:
                    # Length in next byte(s)
                    if offset + 1 >= len(data):
                        raise SecsCodecError("Incomplete variable-length header")
                    length = data[offset + 1]
                    return length, upper_nibble, 2
                else:
                    # Length is in the lower nibble
                    return lower_nibble, upper_nibble, 1
            else:
                # Fixed-length numeric format
                # Lower nibble indicates size (1-4 bytes per item)
                # Actually, for numeric types, the format code already
                # indicates the size. Lower nibble is length count.
                format_code = upper_nibble
                length = lower_nibble

                # For numeric types with length > 15, need additional bytes
                if length == 0 and offset + 1 < len(data):
                    length = data[offset + 1]
                    return length, format_code, 2

                return length, format_code, 1

    def _decode_value(self, format_code: int, data: bytes) -> Any:
        """Decode value bytes based on format.

        Args:
            format_code: SECS-II format code
            data: Raw value bytes

        Returns:
            Decoded Python value
        """
        if format_code == SecsFormat.LIST:
            # Decode list items
            return self.decode_items(data)

        elif format_code == SecsFormat.BINARY:
            return bytes(data)

        elif format_code == SecsFormat.Boolean:
            return [b != 0 for b in data]

        elif format_code == SecsFormat.ASCII:
            try:
                return data.decode("ascii")
            except UnicodeDecodeError:
                return data.decode("ascii", errors="replace")

        elif format_code == SecsFormat.JIS8:
            try:
                return data.decode("iso-2022-jp")
            except (UnicodeDecodeError, LookupError):
                return data.decode("utf-8", errors="replace")

        elif format_code == SecsFormat.INT1:
            return [struct.unpack("b", bytes([b]))[0] for b in data]

        elif format_code == SecsFormat.INT2:
            result = []
            for i in range(0, len(data), 2):
                if i + 2 <= len(data):
                    result.append(struct.unpack(">h", data[i : i + 2])[0])
            return result

        elif format_code == SecsFormat.INT4:
            result = []
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    result.append(struct.unpack(">i", data[i : i + 4])[0])
            return result

        elif format_code == SecsFormat.INT8:
            result = []
            for i in range(0, len(data), 8):
                if i + 8 <= len(data):
                    result.append(struct.unpack(">q", data[i : i + 8])[0])
            return result

        elif format_code == SecsFormat.UINT1:
            return list(data)

        elif format_code == SecsFormat.UINT2:
            result = []
            for i in range(0, len(data), 2):
                if i + 2 <= len(data):
                    result.append(struct.unpack(">H", data[i : i + 2])[0])
            return result

        elif format_code == SecsFormat.UINT4:
            result = []
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    result.append(struct.unpack(">I", data[i : i + 4])[0])
            return result

        elif format_code == SecsFormat.UINT8:
            result = []
            for i in range(0, len(data), 8):
                if i + 8 <= len(data):
                    result.append(struct.unpack(">Q", data[i : i + 8])[0])
            return result

        elif format_code == SecsFormat.FLOAT4:
            result = []
            for i in range(0, len(data), 4):
                if i + 4 <= len(data):
                    result.append(struct.unpack(">f", data[i : i + 4])[0])
            return result

        elif format_code == SecsFormat.FLOAT8:
            result = []
            for i in range(0, len(data), 8):
                if i + 8 <= len(data):
                    result.append(struct.unpack(">d", data[i : i + 8])[0])
            return result

        else:
            # Unknown format, return raw bytes
            return bytes(data)


__all__ = [
    "SecsCodec",
    "SecsCodecError",
]
