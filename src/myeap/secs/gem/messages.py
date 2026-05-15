"""Standard GEM Message Definitions

This module provides standard GEM message structures and builders
according to SEMI E5 and E30 standards.

Message Categories:
- S1: Communications
- S2: Equipment Status
- S3: Equipment Control
- S4: Material Status
- S5: Alarm Management
- S6: Data Collection
- S7: Process Program Management
- S9: Exception
- S12: Terminal Services
- S13: System Errors
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from myeap.secs.protocol.message import (
    SecsMessage,
    SecsItem,
    SecsFormat,
    secs_list,
    secs_binary,
    secs_boolean,
    secs_ascii,
    secs_int1,
    secs_int2,
    secs_int4,
    secs_int8,
    secs_uint1,
    secs_uint2,
    secs_uint4,
    secs_uint8,
    secs_float4,
    secs_float8,
)


class GemMessages:
    """Standard GEM Message Builders.

    Provides static methods to create standard GEM/SECS messages.

    Reference: SEMI E5, E30
    """

    # Message format: (stream, function, requires_response, wait_for_reply)
    # Stream 1 - Communications
    S1F1 = (1, 1, False, False)  # Are You There Request
    S1F2 = (1, 2, False, False)  # On Line Data
    S1F3 = (1, 3, False, True)  # Online/Offline Request
    S1F4 = (1, 4, False, False)  # Online/Offline Acknowledge
    S1F13 = (1, 13, True, True)  # Establish Communication Request
    S1F14 = (1, 14, False, False)  # Establish Communication Acknowledge
    S1F15 = (1, 15, True, True)  # Request Offline
    S1F16 = (1, 16, False, False)  # Request Offline Acknowledge
    S1F17 = (1, 17, True, True)  # Request Online
    S1F18 = (1, 18, False, False)  # Request Online Acknowledge

    # Stream 2 - Equipment Status
    S2F15 = (2, 15, True, True)  # Equipment Constant Update
    S2F16 = (2, 16, False, False)  # Equipment Constant Update Acknowledge
    S2F29 = (2, 29, True, True)  # Date and Time Request
    S2F30 = (2, 30, False, False)  # Date and Time Data
    S2F31 = (2, 31, True, True)  # Date and Time Set Request
    S2F32 = (2, 32, False, False)  # Date and Time Set Acknowledge
    S2F41 = (2, 41, True, True)  # Process Program Names List Request
    S2F42 = (2, 42, False, False)  # Process Program Names List Data
    S2F49 = (2, 49, True, True)  # Equipment Constant Request List
    S2F50 = (2, 50, False, False)  # Equipment Constant Data

    # Stream 5 - Alarm Management
    S5F1 = (5, 1, True, True)  # Alarm Report Request
    S5F2 = (5, 2, False, False)  # Alarm Report Data
    S5F3 = (5, 3, True, True)  # Enable/Disable Alarm Request
    S5F4 = (5, 4, False, False)  # Enable/Disable Alarm Acknowledge
    S5F5 = (5, 5, True, True)  # List Alarm Request
    S5F6 = (5, 6, False, False)  # List Alarm Data
    S5F7 = (5, 7, True, True)  # List Enabled Alarms Request
    S5F8 = (5, 8, False, False)  # List Enabled Alarms Data

    # Stream 6 - Data Collection
    S6F1 = (6, 1, True, True)  # Data Collection Request
    S6F2 = (6, 2, False, False)  # Data Collection Data
    S6F3 = (6, 3, True, True)  # Data Collection Request List
    S6F4 = (6, 4, False, False)  # Data Collection Data
    S6F11 = (6, 11, True, True)  # Data Variable Request
    S6F12 = (6, 12, False, False)  # Data Variable Data
    S6F13 = (6, 13, True, True)  # Multi Data Variable Request
    S6F14 = (6, 14, False, False)  # Multi Data Variable Data
    S6F15 = (6, 15, True, True)  # Formatted Variable Request
    S6F16 = (6, 16, False, False)  # Formatted Variable Data
    S6F19 = (6, 19, True, True)  # Event Report Request
    S6F20 = (6, 20, False, False)  # Event Report Data

    # Stream 7 - Process Program Management
    S7F1 = (7, 1, True, True)  # Process Program Request
    S7F2 = (7, 2, False, False)  # Process Program Data
    S7F3 = (7, 3, True, True)  # Process Program Send
    S7F4 = (7, 4, False, False)  # Process Program Acknowledge
    S7F5 = (7, 5, True, True)  # Process Program Inquire
    S7F6 = (7, 6, False, False)  # Process Program Inquire Grant
    S7F17 = (7, 17, True, True)  # Current PP Request
    S7F18 = (7, 18, False, False)  # Current PP Data
    S7F19 = (7, 19, True, True)  # PP Inquire
    S7F20 = (7, 20, False, False)  # PP Inquire Grant
    S7F23 = (7, 23, True, True)  # Delete PP Request
    S7F24 = (7, 24, False, False)  # Delete PP Acknowledge
    S7F25 = (7, 25, True, True)  # Current PP Modified
    S7F26 = (7, 26, False, False)  # Current PP Modified Acknowledge

    # Stream 9 - Exception
    S9F1 = (9, 1, False, False)  # Unrecognized Device ID
    S9F3 = (9, 3, False, False)  # Unrecognized Stream
    S9F5 = (9, 5, False, False)  # Unrecognized Function
    S9F7 = (9, 7, False, False)  # Unrecognized Transaction Type

    # Stream 12 - Terminal Services
    S12F1 = (12, 1, True, True)  # Terminal Display
    S12F2 = (12, 2, False, False)  # Terminal Display Acknowledge
    S12F3 = (12, 3, True, True)  # Terminal Display Multi
    S12F4 = (12, 4, False, False)  # Terminal Display Multi Acknowledge
    S12F5 = (12, 5, True, True)  # Terminal Clear
    S12F6 = (12, 6, False, False)  # Terminal Clear Acknowledge

    # Stream 13 - System Errors
    S13F1 = (13, 1, True, True)  # Command Error Notification
    S13F2 = (13, 2, False, False)  # Command Error Acknowledge
    S13F3 = (13, 3, False, False)  # Transaction ID Error
    S13F5 = (13, 5, True, True)  # Data Error Notification
    S13F6 = (13, 6, False, False)  # Data Error Acknowledge

    # Stream 17 - Object Collection
    S17F1 = (17, 1, True, True)  # Object Request
    S17F2 = (17, 2, False, False)  # Object Data

    @staticmethod
    def create_s1f1() -> SecsMessage:
        """Create S1F1 - Are You There Request."""
        return SecsMessage.create(
            s_number=1,
            f_number=1,
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s1f2(mdln: str, softrev: str) -> SecsMessage:
        """Create S1F2 - On Line Data."""
        return SecsMessage.create(
            s_number=1,
            f_number=2,
            body=[
                secs_ascii(mdln),
                secs_ascii(softrev),
            ],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s1f3() -> SecsMessage:
        """Create S1F3 - Online/Offline Request."""
        return SecsMessage.create(
            s_number=1,
            f_number=3,
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s1f4(online: bool) -> SecsMessage:
        """Create S1F4 - Online/Offline Acknowledge.

        Args:
            online: True for online, False for offline
        """
        return SecsMessage.create(
            s_number=1,
            f_number=4,
            body=[secs_uint1(0 if online else 1)],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s1f13(mdln: str, softrev: str) -> SecsMessage:
        """Create S1F13 - Establish Communication Request.

        Args:
            mdln: Equipment model
            softrev: Software revision
        """
        return SecsMessage.create(
            s_number=1,
            f_number=13,
            body=[
                secs_ascii(mdln),
                secs_ascii(softrev),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s1f14(commack: int) -> SecsMessage:
        """Create S1F14 - Establish Communication Acknowledge.

        Args:
            commack: 0=Accepted, 1=Refused
        """
        return SecsMessage.create(
            s_number=1,
            f_number=14,
            body=[secs_uint1(commack)],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s1f17(remote: bool) -> SecsMessage:
        """Create S1F17 - Request Online.

        Args:
            remote: True for REMOTE, False for LOCAL
        """
        return SecsMessage.create(
            s_number=1,
            f_number=17,
            body=[secs_uint1(1 if remote else 0)],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s1f18(mode: int) -> SecsMessage:
        """Create S1F18 - Request Online Acknowledge.

        Args:
            mode: 0=LOCAL, 1=REMOTE
        """
        return SecsMessage.create(
            s_number=1,
            f_number=18,
            body=[secs_uint1(mode)],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s2f15(ec_list: List[Tuple[int, Any]]) -> SecsMessage:
        """Create S2F15 - Equipment Constant Update.

        Args:
            ec_list: List of (ECID, value) tuples
        """
        body = []
        for ecid, value in ec_list:
            body.extend([
                secs_uint4(ecid),
                secs_uint4(value) if isinstance(value, int) else secs_float8(value),
            ])

        return SecsMessage.create(
            s_number=2,
            f_number=15,
            body=[secs_list(body)],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s2f29() -> SecsMessage:
        """Create S2F29 - Date and Time Request."""
        return SecsMessage.create(
            s_number=2,
            f_number=29,
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s2f30(timestamp: int) -> SecsMessage:
        """Create S2F30 - Date and Time Data.

        Args:
            timestamp: Unix timestamp
        """
        return SecsMessage.create(
            s_number=2,
            f_number=30,
            body=[secs_binary(timestamp.to_bytes(8, "big"))],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s5f1(active_alarms: List[Dict[str, Any]]) -> SecsMessage:
        """Create S5F1 - Alarm Report Request.

        Args:
            active_alarms: List of alarm dicts with ALCD, ALID, ALTX
        """
        body = []
        for alarm in active_alarms:
            body.extend([
                secs_uint2(alarm.get("ALCD", 0)),
                secs_uint2(alarm.get("ALID", 0)),
                secs_ascii(alarm.get("ALTX", "")),
            ])

        return SecsMessage.create(
            s_number=5,
            f_number=1,
            body=[secs_list(body)],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s5f2(ack5: int) -> SecsMessage:
        """Create S5F2 - Alarm Report Acknowledge.

        Args:
            ack5: 0=Accepted
        """
        return SecsMessage.create(
            s_number=5,
            f_number=2,
            body=[secs_uint1(ack5)],
            requires_response=False,
            wait_for_reply=False,
        )

    @staticmethod
    def create_s5f3(enable: bool, alarm_ids: List[str]) -> SecsMessage:
        """Create S5F3 - Enable/Disable Alarm Request.

        Args:
            enable: True to enable, False to disable
            alarm_ids: List of alarm IDs
        """
        return SecsMessage.create(
            s_number=5,
            f_number=3,
            body=[
                secs_uint1(0 if enable else 1),
                secs_list([secs_ascii(aid) for aid in alarm_ids]),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s6f1(ceids: List[int]) -> SecsMessage:
        """Create S6F1 - Data Collection Request.

        Args:
            ceids: List of collection event IDs
        """
        return SecsMessage.create(
            s_number=6,
            f_number=1,
            body=[secs_list([secs_uint4(ceid) for ceid in ceids])],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s6f11(vids: List[int]) -> SecsMessage:
        """Create S6F11 - Data Variable Request.

        Args:
            vids: List of variable IDs
        """
        return SecsMessage.create(
            s_number=6,
            f_number=11,
            body=[secs_list([secs_uint2(vid) for vid in vids])],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s6f19(ceid: int) -> SecsMessage:
        """Create S6F19 - Event Report Request.

        Args:
            ceid: Collection event ID
        """
        return SecsMessage.create(
            s_number=6,
            f_number=19,
            body=[secs_uint4(ceid)],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s7f1(ppid: str) -> SecsMessage:
        """Create S7F1 - Process Program Request.

        Args:
            ppid: Process program ID
        """
        return SecsMessage.create(
            s_number=7,
            f_number=1,
            body=[secs_ascii(ppid)],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s7f3(ppid: str, ppbody: bytes) -> SecsMessage:
        """Create S7F3 - Process Program Send.

        Args:
            ppid: Process program ID
            ppbody: Process program data
        """
        return SecsMessage.create(
            s_number=7,
            f_number=3,
            body=[
                secs_ascii(ppid),
                secs_binary(ppbody),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s7f5(ppid: str, byte_count: int) -> SecsMessage:
        """Create S7F5 - Process Program Inquire.

        Args:
            ppid: Process program ID
            byte_count: Size of process program in bytes
        """
        return SecsMessage.create(
            s_number=7,
            f_number=5,
            body=[
                secs_ascii(ppid),
                secs_uint4(byte_count),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s12f1(text: str, tid: int = 0) -> SecsMessage:
        """Create S12F1 - Terminal Display.

        Args:
            text: Terminal text
            tid: Terminal ID (0-7)
        """
        return SecsMessage.create(
            s_number=12,
            f_number=1,
            body=[
                secs_uint1(tid),
                secs_ascii(text),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    @staticmethod
    def create_s12f3(texts: List[str], tid: int = 0) -> SecsMessage:
        """Create S12F3 - Terminal Display Multi.

        Args:
            texts: List of terminal texts
            tid: Terminal ID (0-7)
        """
        return SecsMessage.create(
            s_number=12,
            f_number=3,
            body=[
                secs_uint1(tid),
                secs_list([secs_ascii(t) for t in texts]),
            ],
            requires_response=True,
            wait_for_reply=True,
        )

    # Message templates for parsing responses

    @staticmethod
    def parse_s1f14(msg: SecsMessage) -> Tuple[bool, str]:
        """Parse S1F14 - Establish Communication Acknowledge.

        Returns:
            Tuple of (accepted, error_message)
        """
        if not msg.body or len(msg.body) < 1:
            return False, "Missing COMMACK"

        commack = msg.body[0].get_single_value()
        if commack == 0:
            return True, ""
        return False, "Communication refused"

    @staticmethod
    def parse_s5f4(msg: SecsMessage) -> int:
        """Parse S5F4 - Enable/Disable Alarm Acknowledge.

        Returns:
            ACK5 value (0=Accepted)
        """
        if not msg.body:
            return 1
        return msg.body[0].get_single_value() or 1

    @staticmethod
    def parse_s7f4(msg: SecsMessage) -> int:
        """Parse S7F4 - Process Program Acknowledge.

        Returns:
            ACK7 value
        """
        if not msg.body:
            return 1
        return msg.body[0].get_single_value() or 1

    @staticmethod
    def parse_s12f2(msg: SecsMessage) -> int:
        """Parse S12F2 - Terminal Display Acknowledge.

        Returns:
            ACK12 value
        """
        if not msg.body:
            return 1
        return msg.body[0].get_single_value() or 1


# Message format registry
MESSAGE_REGISTRY: Dict[Tuple[int, int], Dict[str, Any]] = {
    # S1 messages
    (1, 1): {"name": "Are You There Request", "primary": True, "reply": 2},
    (1, 2): {"name": "On Line Data", "primary": False, "reply": None},
    (1, 3): {"name": "Online/Offline Request", "primary": True, "reply": 4},
    (1, 4): {"name": "Online/Offline Acknowledge", "primary": False, "reply": None},
    (1, 13): {"name": "Establish Communication Request", "primary": True, "reply": 14},
    (1, 14): {"name": "Establish Communication Acknowledge", "primary": False, "reply": None},
    (1, 15): {"name": "Request Offline", "primary": True, "reply": 16},
    (1, 16): {"name": "Request Offline Acknowledge", "primary": False, "reply": None},
    (1, 17): {"name": "Request Online", "primary": True, "reply": 18},
    (1, 18): {"name": "Request Online Acknowledge", "primary": False, "reply": None},

    # S2 messages
    (2, 13): {"name": "Equipment Constant Request", "primary": True, "reply": 14},
    (2, 14): {"name": "Equipment Constant Data", "primary": False, "reply": None},
    (2, 15): {"name": "Equipment Constant Update", "primary": True, "reply": 16},
    (2, 16): {"name": "Equipment Constant Update Acknowledge", "primary": False, "reply": None},
    (2, 29): {"name": "Date and Time Request", "primary": True, "reply": 30},
    (2, 30): {"name": "Date and Time Data", "primary": False, "reply": None},
    (2, 31): {"name": "Date and Time Set Request", "primary": True, "reply": 32},
    (2, 32): {"name": "Date and Time Set Acknowledge", "primary": False, "reply": None},

    # S5 messages
    (5, 1): {"name": "Alarm Report Request", "primary": True, "reply": 2},
    (5, 2): {"name": "Alarm Report Data", "primary": False, "reply": None},
    (5, 3): {"name": "Enable/Disable Alarm Request", "primary": True, "reply": 4},
    (5, 4): {"name": "Enable/Disable Alarm Acknowledge", "primary": False, "reply": None},
    (5, 5): {"name": "List Alarm Request", "primary": True, "reply": 6},
    (5, 6): {"name": "List Alarm Data", "primary": False, "reply": None},

    # S6 messages
    (6, 1): {"name": "Data Collection Request", "primary": True, "reply": 2},
    (6, 2): {"name": "Data Collection Data", "primary": False, "reply": None},
    (6, 11): {"name": "Data Variable Request", "primary": True, "reply": 12},
    (6, 12): {"name": "Data Variable Data", "primary": False, "reply": None},
    (6, 19): {"name": "Event Report Request", "primary": True, "reply": 20},
    (6, 20): {"name": "Event Report Data", "primary": False, "reply": None},

    # S7 messages
    (7, 1): {"name": "Process Program Request", "primary": True, "reply": 2},
    (7, 2): {"name": "Process Program Data", "primary": False, "reply": None},
    (7, 3): {"name": "Process Program Send", "primary": True, "reply": 4},
    (7, 4): {"name": "Process Program Acknowledge", "primary": False, "reply": None},
    (7, 5): {"name": "Process Program Inquire", "primary": True, "reply": 6},
    (7, 6): {"name": "Process Program Inquire Grant", "primary": False, "reply": None},
    (7, 17): {"name": "Current PP Request", "primary": True, "reply": 18},
    (7, 18): {"name": "Current PP Data", "primary": False, "reply": None},
    (7, 23): {"name": "Delete PP Request", "primary": True, "reply": 24},
    (7, 24): {"name": "Delete PP Acknowledge", "primary": False, "reply": None},

    # S9 messages
    (9, 1): {"name": "Unrecognized Device ID", "primary": False, "reply": None},
    (9, 3): {"name": "Unrecognized Stream", "primary": False, "reply": None},
    (9, 5): {"name": "Unrecognized Function", "primary": False, "reply": None},
    (9, 7): {"name": "Unrecognized Transaction Type", "primary": False, "reply": None},

    # S12 messages
    (12, 1): {"name": "Terminal Display", "primary": True, "reply": 2},
    (12, 2): {"name": "Terminal Display Acknowledge", "primary": False, "reply": None},
    (12, 3): {"name": "Terminal Display Multi", "primary": True, "reply": 4},
    (12, 4): {"name": "Terminal Display Multi Acknowledge", "primary": False, "reply": None},
    (12, 5): {"name": "Terminal Clear", "primary": True, "reply": 6},
    (12, 6): {"name": "Terminal Clear Acknowledge", "primary": False, "reply": None},
}


def get_message_info(stream: int, function: int) -> Optional[Dict[str, Any]]:
    """Get information about a message from the registry.

    Args:
        stream: Stream number
        function: Function number

    Returns:
        Message info dict or None
    """
    return MESSAGE_REGISTRY.get((stream, function))


def get_reply_stream_function(stream: int, function: int) -> Optional[Tuple[int, int]]:
    """Get the expected reply stream/function for a message.

    Args:
        stream: Stream number
        function: Function number

    Returns:
        Tuple of (stream, function) for reply, or None
    """
    info = get_message_info(stream, function)
    if info and info.get("reply"):
        return (stream, info["reply"])
    return None


def is_primary_message(stream: int, function: int) -> bool:
    """Check if a message is a primary message (needs reply).

    Args:
        stream: Stream number
        function: Function number

    Returns:
        True if this is a primary message
    """
    info = get_message_info(stream, function)
    return info.get("primary", True) if info else True


__all__ = [
    "GemMessages",
    "MESSAGE_REGISTRY",
    "get_message_info",
    "get_reply_stream_function",
    "is_primary_message",
]
