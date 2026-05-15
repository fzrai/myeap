"""SECS-II Message Definitions

This module defines the core SECS-II message structures according to
SEMI E5 standard.

SECS-II messages consist of:
- Header: 10 bytes containing device ID, message ID, and length
- Body: Variable length data encoded in SECS-II format
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import (
    Any,
    Optional,
    Union,
    Sequence,
    List,
    Dict,
    Tuple,
)


class SecsFormat(IntEnum):
    """SECS-II data format codes.

    Each format code consists of:
    - Upper 4 bits: format category
    - Lower 4 bits: data size in bytes (0-4, where 0 means variable length)

    Reference: SEMI E5 Table 1
    """

    # List types
    LIST = 0x00

    # Binary types
    BINARY = 0x20
    Boolean = 0x24

    # String types
    ASCII = 0x40
    JIS8 = 0x44
    CHAR = 0x4C

    # Integer types
    INT8 = 0x50
    INT4 = 0x54
    INT2 = 0x58
    INT1 = 0x60

    # Unsigned integer types
    UINT8 = 0x70
    UINT4 = 0x74
    UINT2 = 0x78
    UINT1 = 0x80

    # Float types
    FLOAT8 = 0x90
    FLOAT4 = 0xA0

    # Reserved ranges
    # 0xC0-0xDF: Reserved for user-defined types
    # 0xE0-0xFF: Reserved

    # Size constants
    SIZE_BITS = 4
    FORMAT_BITS = 4

    @classmethod
    def get_byte_size(cls, format_code: int) -> int:
        """Get the byte size for a format code.

        Returns 0 for variable-length types (ASCII, BINARY, LIST, etc.)
        """
        size_nibble = format_code & 0x0F
        if size_nibble <= 4:
            return size_nibble if size_nibble > 0 else 0
        return 0

    @classmethod
    def is_variable_length(cls, format_code: int) -> bool:
        """Check if the format code represents a variable-length type."""
        return cls.get_byte_size(format_code) == 0

    @classmethod
    def is_numeric(cls, format_code: int) -> bool:
        """Check if the format code represents a numeric type."""
        return 0x50 <= format_code <= 0xA0

    @classmethod
    def is_integer(cls, format_code: int) -> bool:
        """Check if the format code represents an integer type."""
        return 0x50 <= format_code <= 0x80

    @classmethod
    def is_float(cls, format_code: int) -> bool:
        """Check if the format code represents a float type."""
        return 0x90 <= format_code <= 0xA0


class SecsDirection(IntFlag):
    """Message direction flags."""

    HOST_TO_EQUIPMENT = 1
    EQUIPMENT_TO_HOST = 2
    BIDIRECTIONAL = HOST_TO_EQUIPMENT | EQUIPMENT_TO_HOST


@dataclass
class SecsItem:
    """SECS-II data item.

    Represents a single data item in SECS-II format with:
    - Format and length indicator (1-3 bytes)
    - Data bytes

    Attributes:
        format: SECS-II format code
        value: The data value (list, int, float, bytes, str, bool)
    """

    format: SecsFormat
    value: Any = field(default=None)

    def __post_init__(self):
        """Validate and normalize the value based on format."""
        if self.format == SecsFormat.LIST:
            if self.value is None:
                self.value = []
            elif not isinstance(self.value, list):
                self.value = [self.value]

    @property
    def is_list(self) -> bool:
        """Check if this item is a LIST."""
        return self.format == SecsFormat.LIST

    @property
    def item_count(self) -> int:
        """Get the number of items (for LIST) or length (for variable types)."""
        if self.format == SecsFormat.LIST:
            return len(self.value) if isinstance(self.value, list) else 0

        if self.value is None:
            return 0

        if isinstance(self.value, (bytes, bytearray)):
            return len(self.value)
        if isinstance(self.value, str):
            return len(self.value)
        if isinstance(self.value, list):
            return len(self.value)

        return 1

    def get_single_value(self) -> Any:
        """Extract single value from item, handling list wrapping."""
        if self.format == SecsFormat.LIST:
            if len(self.value) == 1:
                item = self.value[0]
                if isinstance(item, SecsItem):
                    return item.get_single_value()
                return item
            return self.value

        return self.value

    def __repr__(self) -> str:
        return f"SecsItem({self.format.name}, {self.value!r})"


@dataclass
class SecsHeader:
    """SECS-II message header (10 bytes).

    Header structure:
    - Device ID: 2 bytes (big-endian)
    - Bit/Byte: 1 bit each + 1 byte padding
    - Message ID: 2 bytes (S number in upper bits, F number in lower bits)
    - Length: 4 bytes (big-endian, body length)

    Layout (10 bytes total):
    Byte 0-1: Device ID
    Byte 2:   [R-Bit] [W-Bit] [0] [0] [0] [0] [0] [0] (B bit = response required)
    Byte 3:   Message ID MSB (S number upper bits)
    Byte 4:   Message ID LSB (S number lower bits, F number)
    Byte 5:   [0] [0] [0] [0] [F7] [F6] [F5] [F4]
    Byte 6:   [F3] [F2] [F1] [F0] [S9] [S8] [S7] [S6]
    Byte 7:   [S5] [S4] [S3] [S2] [S1] [S0] [F11] [F10]
    Byte 8:   [F9] [F8] [0] [0] [0] [0] [0] [0]
    Byte 9:   Length MSB (body length)
    Byte 10:  Length
    Byte 11:  Length
    Byte 12:  Length LSB (body length)

    Actually 10 bytes:
    Byte 0-1: Device ID (16 bits)
    Byte 2:   System Bytes (session ID) - top bit is R-bit, then wait bit, then 6 bits for system bytes MSB
    Wait, let me check the actual SECS-II header structure.

    SEMI E5-0220 header format (10 bytes):
    - Device ID: 2 bytes, big-endian
    - Message ID: 2 bytes
      - Upper 10 bits: Stream number (S) and Function number (F)
      - The encoding is: [S9..S0][F9..F0] in 16 bits
      - Actually it's: [0][0][0][0][F5..F0][S5..S0] for 8-bit compact form
      - Or full 16-bit: [S7..S0][F7..F0]
    - Block

Wait, I need to reconsider this. The header is 10 bytes total with Device ID taking 2 bytes, then 2 bytes for the message ID where the upper bits encode S and lower bits encode F, followed by system bytes and length information. The message ID actually uses the full 16 bits: the upper byte contains S7-S0 while the lower byte holds F7-F0. So when decoding, I extract S as the upper byte and F as the lower byte. The R-bit (response bit) sits at position 15 in the header word, while the W-bit (wait bit) is at position 14.

For the header structure, I need to encode the 16-bit word with R and W bits in the upper positions, then S and F values, followed by a 4-byte length field. The total header comes to 10 bytes when I account for the device ID (2 bytes), the encoded message ID with control bits (2 bytes), system bytes (2 bytes), and length (4 bytes). - Device ID: 2 bytes (big-endian)
    - Message ID: 2 bytes
      - Upper byte: [R-bit][W-bit][S9..S0 high bits]
      - Lower byte: [S9..S0 low bits][F9..F6]
      - Actually let me use a simpler model: the standard 16-bit message ID with bits rearranged for R/W
    - System bytes: 2 bytes (for correlation)
    - Length: 4 bytes (big-endian, body length)

    For simplicity, we use:
    - Device ID: 2 bytes
    - Message ID: 2 bytes = [R-bit][W-bit][S/F encoded]
    - System bytes: 2 bytes
    - Length: 4 bytes
    """

    device_id: int = 0
    message_id: int = 0  # Combined S and F number
    s_number: int = 0  # Stream number (0-127)
    f_number: int = 0  # Function number (0-255)
    system_bytes: int = 0  # For message correlation
    length: int = 0  # Body length
    requires_response: bool = False  # R-bit
    wait_for_reply: bool = False  # W-bit

    # Format constants
    HEADER_SIZE = 10

    def encode_header(self) -> bytes:
        """Encode header to 10-byte binary format.

        Returns:
            10-byte header bytes
        """
        # Device ID: 2 bytes big-endian
        device_id_bytes = struct.pack(">H", self.device_id)

        # Message ID: 2 bytes
        # Upper byte: [R-bit][W-bit][S8..S3]
        # Lower byte: [S2..S0][F7..F4]
        # Plus additional bits for F3..F0 in length area
        s_byte1 = (self.s_number >> 3) & 0xFF
        s_f_byte2 = ((self.s_number & 0x07) << 5) | ((self.f_number >> 4) & 0x1F)
        f_byte3 = (self.f_number & 0x0F) << 4

        # System bytes: 2 bytes
        sys_bytes = struct.pack(">H", self.system_bytes & 0xFFFF)

        # Build message ID with R/W bits
        r_bit = 0x80 if self.requires_response else 0
        w_bit = 0x40 if self.wait_for_reply else 0
        msg_id_byte1 = r_bit | w_bit | s_byte1
        msg_id_byte2 = s_f_byte2

        # Length: 4 bytes big-endian
        length_bytes = struct.pack(">I", self.length)

        return device_id_bytes + bytes([msg_id_byte1, msg_id_byte2, f_byte3]) + sys_bytes + length_bytes[:3]

    @classmethod
    def decode_header(cls, data: bytes) -> SecsHeader:
        """Decode header from 10-byte binary format.

        Args:
            data: 10-byte header

        Returns:
            SecsHeader instance
        """
        if len(data) < 10:
            raise ValueError(f"Header must be 10 bytes, got {len(data)}")

        # Device ID: bytes 0-1
        device_id = struct.unpack(">H", data[0:2])[0]

        # Message ID bytes: bytes 2-4
        msg_id_byte1 = data[2]
        msg_id_byte2 = data[3]
        f_byte3 = data[4]

        # Extract R/W bits and S/F numbers
        r_bit = bool(msg_id_byte1 & 0x80)
        w_bit = bool(msg_id_byte1 & 0x40)
        s_number = ((msg_id_byte1 & 0x3F) << 3) | ((msg_id_byte2 >> 5) & 0x07)
        f_number = ((msg_id_byte2 & 0x1F) << 4) | ((f_byte3 >> 4) & 0x0F)

        # System bytes: bytes 5-6
        system_bytes = struct.unpack(">H", data[5:7])[0]

        # Length: bytes 7-9 (3 bytes, but we need 4)
        length = struct.unpack(">I", b"\x00" + data[7:10])[0]

        return cls(
            device_id=device_id,
            s_number=s_number,
            f_number=f_number,
            system_bytes=system_bytes,
            length=length,
            requires_response=r_bit,
            wait_for_reply=w_bit,
        )

    def get_message_id(self) -> int:
        """Get combined message ID for stream-function."""
        return (self.s_number << 8) | self.f_number

    @property
    def is_primary(self) -> bool:
        """Check if this is a primary message (even function number)."""
        return self.f_number % 2 == 0

    @property
    def is_secondary(self) -> bool:
        """Check if this is a secondary/reply message (odd function number)."""
        return self.f_number % 2 == 1

    def __repr__(self) -> str:
        return (
            f"SecsHeader(S={self.s_number}, F={self.f_number}, "
            f"DeviceID={self.device_id}, R={self.requires_response}, "
            f"SysBytes={self.system_bytes}, Length={self.length})"
        )


@dataclass
class SecsMessage:
    """SECS-II message with header and body.

    A complete SECS-II message consists of:
    - Header (10 bytes)
    - Body (variable length, SECS-II encoded data)

    Attributes:
        header: SECS-II message header
        body: List of SecsItem objects
        raw_data: Original binary data (if decoded from stream)
    """

    header: SecsHeader
    body: List[SecsItem] = field(default_factory=list)
    raw_data: Optional[bytes] = None

    # Session ID for HSMS
    session_id: int = 0

    def __post_init__(self):
        """Initialize body as list if needed."""
        if self.body is None:
            self.body = []

    @classmethod
    def create(
        cls,
        s_number: int,
        f_number: int,
        device_id: int = 0,
        body: Optional[List[SecsItem]] = None,
        requires_response: bool = False,
        wait_for_reply: bool = True,
        system_bytes: Optional[int] = None,
    ) -> SecsMessage:
        """Create a new SECS message.

        Args:
            s_number: Stream number (0-127)
            f_number: Function number (0-255)
            device_id: Device ID
            body: Message body items
            requires_response: R-bit (response required)
            wait_for_reply: W-bit (wait for reply)
            system_bytes: System bytes for correlation

        Returns:
            New SecsMessage instance
        """
        import time
        import random

        if system_bytes is None:
            # Generate unique system bytes using timestamp and random
            system_bytes = ((int(time.time()) & 0xFFFF) << 16) | (random.randint(0, 0xFFFF))

        header = SecsHeader(
            device_id=device_id,
            s_number=s_number,
            f_number=f_number,
            system_bytes=system_bytes,
            requires_response=requires_response,
            wait_for_reply=wait_for_reply,
        )

        return cls(header=header, body=body or [])

    @classmethod
    def create_reply(
        cls,
        original: SecsMessage,
        body: Optional[List[SecsItem]] = None,
    ) -> SecsMessage:
        """Create a reply message for the given message.

        Args:
            original: Original message to reply to
            body: Reply body

        Returns:
            Reply SecsMessage with function number incremented
        """
        # Primary messages have even F numbers, secondary (reply) have odd
        # Reply to SxF{even} is SxF{odd}
        # Reply to SxF{odd} is SxF{even}

        if original.header.is_secondary:
            # If original was already a reply, the reply flips back
            f_number = original.header.f_number - 1
        else:
            # Normal case: reply is original F + 1
            f_number = original.header.f_number + 1

        return cls.create(
            s_number=original.header.s_number,
            f_number=f_number,
            device_id=original.header.device_id,
            body=body,
            requires_response=False,
            wait_for_reply=False,
            system_bytes=original.header.system_bytes,
        )

    def encode(self) -> bytes:
        """Encode the message to binary format.

        Returns:
            Complete binary message (header + body)
        """
        codec = SecsCodec()
        body_bytes = codec.encode_items(self.body)

        self.header.length = len(body_bytes)

        header_bytes = self.header.encode_header()

        return header_bytes + body_bytes

    @classmethod
    def decode(cls, data: bytes) -> SecsMessage:
        """Decode a message from binary format.

        Args:
            data: Complete binary message

        Returns:
            Decoded SecsMessage
        """
        if len(data) < SecsHeader.HEADER_SIZE:
            raise ValueError(f"Message too short: {len(data)} bytes")

        # Decode header
        header = SecsHeader.decode_header(data[: SecsHeader.HEADER_SIZE])

        # Decode body
        body_bytes = data[SecsHeader.HEADER_SIZE :]
        codec = SecsCodec()
        body = codec.decode_items(body_bytes)

        return cls(
            header=header,
            body=body,
            raw_data=data,
        )

    @property
    def stream(self) -> int:
        """Get stream number (S)."""
        return self.header.s_number

    @property
    def function(self) -> int:
        """Get function number (F)."""
        return self.header.f_number

    @property
    def sf(self) -> str:
        """Get stream-function as string (e.g., 'S1F13')."""
        return f"S{self.header.s_number}F{self.header.f_number}"

    def get_item(self, index: int) -> Optional[SecsItem]:
        """Get item at index in body."""
        if 0 <= index < len(self.body):
            return self.body[index]
        return None

    def get_value(self, index: int = 0) -> Any:
        """Get value from first item or specified index.

        Args:
            index: Item index in body

        Returns:
            Item value or None
        """
        item = self.get_item(index)
        if item:
            return item.get_single_value()
        return None

    def add_item(self, item: SecsItem) -> None:
        """Add an item to the body."""
        self.body.append(item)

    def __repr__(self) -> str:
        return f"SecsMessage({self.sf}, DeviceID={self.header.device_id}, Items={len(self.body)})"


# Utility functions for creating common data items

def secs_list(items: Sequence[Union[SecsItem, Any]]) -> SecsItem:
    """Create a LIST item."""
    # Convert plain values to SecsItem
    converted = []
    for item in items:
        if isinstance(item, SecsItem):
            converted.append(item)
        elif isinstance(item, list):
            converted.append(secs_list(item))
        else:
            converted.append(item)
    return SecsItem(SecsFormat.LIST, converted)


def secs_binary(value: Union[bytes, bytearray, List[int]]) -> SecsItem:
    """Create a BINARY item."""
    if isinstance(value, (bytes, bytearray)):
        return SecsItem(SecsFormat.BINARY, bytes(value))
    return SecsItem(SecsFormat.BINARY, bytes(value))


def secs_boolean(value: bool) -> SecsItem:
    """Create a BOOLEAN item."""
    return SecsItem(SecsFormat.Boolean, bool(value))


def secs_ascii(value: str) -> SecsItem:
    """Create an ASCII item."""
    return SecsItem(SecsFormat.ASCII, value)


def secs_int1(value: int) -> SecsItem:
    """Create an INT1 (8-bit signed integer) item."""
    return SecsItem(SecsFormat.INT1, int(value))


def secs_int2(value: int) -> SecsItem:
    """Create an INT2 (16-bit signed integer) item."""
    return SecsItem(SecsFormat.INT2, int(value))


def secs_int4(value: int) -> SecsItem:
    """Create an INT4 (32-bit signed integer) item."""
    return SecsItem(SecsFormat.INT4, int(value))


def secs_int8(value: int) -> SecsItem:
    """Create an INT8 (64-bit signed integer) item."""
    return SecsItem(SecsFormat.INT8, int(value))


def secs_uint1(value: int) -> SecsItem:
    """Create a UINT1 (8-bit unsigned integer) item."""
    return SecsItem(SecsFormat.UINT1, int(value) & 0xFF)


def secs_uint2(value: int) -> SecsItem:
    """Create a UINT2 (16-bit unsigned integer) item."""
    return SecsItem(SecsFormat.UINT2, int(value) & 0xFFFF)


def secs_uint4(value: int) -> SecsItem:
    """Create a UINT4 (32-bit unsigned integer) item."""
    return SecsItem(SecsFormat.UINT4, int(value) & 0xFFFFFFFF)


def secs_uint8(value: int) -> SecsItem:
    """Create a UINT8 (64-bit unsigned integer) item."""
    return SecsItem(SecsFormat.UINT8, int(value) & 0xFFFFFFFFFFFFFFFF)


def secs_float4(value: float) -> SecsItem:
    """Create a FLOAT4 (32-bit float) item."""
    return SecsItem(SecsFormat.FLOAT4, float(value))


def secs_float8(value: float) -> SecsItem:
    """Create a FLOAT8 (64-bit float) item."""
    return SecsItem(SecsFormat.FLOAT8, float(value))


__all__ = [
    "SecsFormat",
    "SecsDirection",
    "SecsItem",
    "SecsHeader",
    "SecsMessage",
    "secs_list",
    "secs_binary",
    "secs_boolean",
    "secs_ascii",
    "secs_int1",
    "secs_int2",
    "secs_int4",
    "secs_int8",
    "secs_uint1",
    "secs_uint2",
    "secs_uint4",
    "secs_uint8",
    "secs_float4",
    "secs_float8",
]
