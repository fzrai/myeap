"""Tests for GEM messages module."""
import pytest
import time

from myeap.secs.gem.messages import (
    GemMessages,
    get_message_info,
    get_reply_stream_function,
    is_primary_message,
    MESSAGE_REGISTRY,
)
from myeap.secs.protocol.message import SecsMessage, SecsFormat


class TestGemMessages:
    """Tests for GemMessages builders."""

    def test_create_s1f1(self):
        """Test creating S1F1 message."""
        msg = GemMessages.create_s1f1()
        assert msg.stream == 1
        assert msg.function == 1
        assert msg.sf == "S1F1"

    def test_create_s1f2(self):
        """Test creating S1F2 message."""
        msg = GemMessages.create_s1f2("MODEL", "1.0")
        assert msg.stream == 1
        assert msg.function == 2
        assert len(msg.body) == 2
        assert msg.body[0].value == "MODEL"
        assert msg.body[1].value == "1.0"

    def test_create_s1f4_online(self):
        """Test creating S1F4 with online."""
        msg = GemMessages.create_s1f4(online=True)
        assert msg.body[0].get_single_value() == 0  # Online = 0

    def test_create_s1f4_offline(self):
        """Test creating S1F4 with offline."""
        msg = GemMessages.create_s1f4(online=False)
        assert msg.body[0].get_single_value() == 1  # Offline = 1

    def test_create_s1f13(self):
        """Test creating S1F13 message."""
        msg = GemMessages.create_s1f13("MYEQP", "2.0")
        assert msg.stream == 1
        assert msg.function == 13
        assert msg.header.wait_for_reply is True
        assert len(msg.body) == 2
        assert msg.body[0].value == "MYEQP"
        assert msg.body[1].value == "2.0"

    def test_create_s1f14_commack_accepted(self):
        """Test creating S1F14 with accepted."""
        msg = GemMessages.create_s1f14(commack=0)
        assert msg.body[0].get_single_value() == 0

    def test_create_s1f14_commack_refused(self):
        """Test creating S1F14 with refused."""
        msg = GemMessages.create_s1f14(commack=1)
        assert msg.body[0].get_single_value() == 1

    def test_create_s1f17_remote(self):
        """Test creating S1F17 for REMOTE."""
        msg = GemMessages.create_s1f17(remote=True)
        assert msg.body[0].get_single_value() == 1

    def test_create_s1f17_local(self):
        """Test creating S1F17 for LOCAL."""
        msg = GemMessages.create_s1f17(remote=False)
        assert msg.body[0].get_single_value() == 0

    def test_create_s2f15(self):
        """Test creating S2F15 equipment constant update."""
        msg = GemMessages.create_s2f15([(1, 100), (2, 200)])
        assert msg.stream == 2
        assert msg.function == 15
        assert len(msg.body) == 1
        assert msg.body[0].is_list

    def test_create_s2f29(self):
        """Test creating S2F29."""
        msg = GemMessages.create_s2f29()
        assert msg.stream == 2
        assert msg.function == 29

    def test_create_s2f30(self):
        """Test creating S2F30 with timestamp."""
        now = int(time.time())
        msg = GemMessages.create_s2f30(now)
        assert msg.stream == 2
        assert msg.function == 30
        # Body should contain binary timestamp
        assert msg.body[0].format == SecsFormat.BINARY

    def test_create_s5f1(self):
        """Test creating S5F1 alarm report."""
        alarms = [
            {"ALCD": 0x8000, "ALID": 1, "ALTX": "High Temp"},
            {"ALCD": 0x4000, "ALID": 2, "ALTX": "Low Pressure"},
        ]
        msg = GemMessages.create_s5f1(alarms)
        assert msg.stream == 5
        assert msg.function == 1

    def test_create_s5f2_ack(self):
        """Test creating S5F2 acknowledgment."""
        msg = GemMessages.create_s5f2(ack5=0)
        assert msg.body[0].get_single_value() == 0

    def test_create_s5f3_enable(self):
        """Test creating S5F3 enable alarm."""
        msg = GemMessages.create_s5f3(enable=True, alarm_ids=["ALM1", "ALM2"])
        assert msg.stream == 5
        assert msg.function == 3

    def test_create_s5f3_disable(self):
        """Test creating S5F3 disable alarm."""
        msg = GemMessages.create_s5f3(enable=False, alarm_ids=["ALM1"])
        assert msg.body[0].get_single_value() == 1  # Disable code

    def test_create_s6f1(self):
        """Test creating S6F1 data collection request."""
        msg = GemMessages.create_s6f1([100, 200, 300])
        assert msg.stream == 6
        assert msg.function == 1

    def test_create_s6f11(self):
        """Test creating S6F11 data variable request."""
        msg = GemMessages.create_s6f11([1, 2, 3])
        assert msg.stream == 6
        assert msg.function == 11

    def test_create_s6f19(self):
        """Test creating S6F19 event report request."""
        msg = GemMessages.create_s6f19(ceid=100)
        assert msg.stream == 6
        assert msg.function == 19
        assert msg.body[0].get_single_value() == 100

    def test_create_s7f1(self):
        """Test creating S7F1 process program request."""
        msg = GemMessages.create_s7f1("RECIPE001")
        assert msg.stream == 7
        assert msg.function == 1
        assert msg.body[0].value == "RECIPE001"

    def test_create_s7f3(self):
        """Test creating S7F3 process program send."""
        ppdata = b"\x00\x01\x02\x03\x04"
        msg = GemMessages.create_s7f3("RECIPE001", ppdata)
        assert msg.stream == 7
        assert msg.function == 3
        assert msg.body[0].value == "RECIPE001"
        assert msg.body[1].value == ppdata

    def test_create_s7f5(self):
        """Test creating S7F5 process program inquire."""
        msg = GemMessages.create_s7f5("RECIPE001", 1024)
        assert msg.stream == 7
        assert msg.function == 5

    def test_create_s12f1(self):
        """Test creating S12F1 terminal display."""
        msg = GemMessages.create_s12f1("Hello Terminal", tid=0)
        assert msg.stream == 12
        assert msg.function == 1
        assert msg.body[0].get_single_value() == 0  # TID
        assert msg.body[1].value == "Hello Terminal"

    def test_create_s12f3(self):
        """Test creating S12F3 terminal display multi."""
        msg = GemMessages.create_s12f3(["Line 1", "Line 2"], tid=1)
        assert msg.stream == 12
        assert msg.function == 3


class TestGemMessageParsing:
    """Tests for parsing reply messages."""

    def test_parse_s1f14_accepted(self):
        """Test parsing S1F14 accepted."""
        msg = SecsMessage.create(
            s_number=1,
            f_number=14,
            body=[SecsMessage.create(s_number=0, f_number=0, body=[]).body.append(SecsItem(SecsFormat.UINT1, 0)) or SecsItem(SecsFormat.UINT1, 0)],
        )
        # Simplified test
        accepted, error = GemMessages.parse_s1f14(SecsMessage.create(s_number=1, f_number=14, body=[SecsItem(SecsFormat.UINT1, 0)]))
        assert accepted is True
        assert error == ""

    def test_parse_s1f14_refused(self):
        """Test parsing S1F14 refused."""
        msg = GemMessages.create_s1f14(commack=1)
        accepted, error = GemMessages.parse_s1f14(msg)
        assert accepted is False
        assert "refused" in error.lower()

    def test_parse_s5f4(self):
        """Test parsing S5F4 acknowledgment."""
        msg = SecsMessage.create(s_number=5, f_number=4, body=[SecsItem(SecsFormat.UINT1, 0)])
        ack = GemMessages.parse_s5f4(msg)
        assert ack == 0

    def test_parse_s7f4(self):
        """Test parsing S7F4 acknowledgment."""
        msg = SecsMessage.create(s_number=7, f_number=4, body=[SecsItem(SecsFormat.UINT1, 0)])
        ack = GemMessages.parse_s7f4(msg)
        assert ack == 0


class TestMessageRegistry:
    """Tests for message registry."""

    def test_registry_contains_standard_messages(self):
        """Test registry contains standard messages."""
        # S1 messages
        assert (1, 1) in MESSAGE_REGISTRY
        assert (1, 13) in MESSAGE_REGISTRY
        assert (1, 17) in MESSAGE_REGISTRY

        # S2 messages
        assert (2, 13) in MESSAGE_REGISTRY
        assert (2, 29) in MESSAGE_REGISTRY

        # S5 messages
        assert (5, 1) in MESSAGE_REGISTRY
        assert (5, 3) in MESSAGE_REGISTRY

        # S6 messages
        assert (6, 1) in MESSAGE_REGISTRY
        assert (6, 19) in MESSAGE_REGISTRY

        # S7 messages
        assert (7, 1) in MESSAGE_REGISTRY
        assert (7, 3) in MESSAGE_REGISTRY

        # S9 messages
        assert (9, 1) in MESSAGE_REGISTRY
        assert (9, 3) in MESSAGE_REGISTRY

        # S12 messages
        assert (12, 1) in MESSAGE_REGISTRY

    def test_get_message_info(self):
        """Test getting message info."""
        info = get_message_info(1, 13)
        assert info is not None
        assert info["name"] == "Establish Communication Request"
        assert info["primary"] is True
        assert info["reply"] == 14

    def test_get_message_info_not_found(self):
        """Test getting info for unknown message."""
        info = get_message_info(99, 99)
        assert info is None

    def test_get_reply_stream_function(self):
        """Test getting reply stream/function."""
        reply = get_reply_stream_function(1, 13)
        assert reply == (1, 14)

        reply = get_reply_stream_function(1, 14)
        assert reply is None  # No reply for reply messages

    def test_is_primary_message(self):
        """Test primary message detection."""
        assert is_primary_message(1, 1) is True
        assert is_primary_message(1, 13) is True
        assert is_primary_message(1, 2) is False  # S1F2 is reply
        assert is_primary_message(1, 14) is False  # S1F14 is reply

    def test_message_info_structure(self):
        """Test message info structure."""
        info = get_message_info(7, 1)
        assert "name" in info
        assert "primary" in info
        assert "reply" in info
