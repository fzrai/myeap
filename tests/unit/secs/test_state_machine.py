"""Tests for GEM state machine."""
import pytest
import asyncio

from myeap.secs.gem.state_machine import (
    GemState,
    GemEvent,
    GemStateMachine,
    GemTransition,
)


class TestGemState:
    """Tests for GemState enum."""

    def test_state_values(self):
        """Test state values."""
        assert GemState.OFFLINE.value == "OFFLINE"
        assert GemState.COMMUNICATING_OFFLINE.value == "COMMUNICATING_OFFLINE"
        assert GemState.ATTEMPT_ONLINE.value == "ATTEMPT_ONLINE"
        assert GemState.LOCAL.value == "LOCAL"
        assert GemState.REMOTE.value == "REMOTE"

    def test_online_states(self):
        """Test online state detection."""
        assert GemState.LOCAL.is_online
        assert GemState.REMOTE.is_online
        assert not GemState.OFFLINE.is_online
        assert not GemState.COMMUNICATING_OFFLINE.is_online

    def test_offline_states(self):
        """Test offline state detection."""
        assert GemState.OFFLINE.is_offline
        assert GemState.COMMUNICATING_OFFLINE.is_offline
        assert GemState.EQUIPMENT_OFFLINE.is_offline
        assert not GemState.LOCAL.is_offline
        assert not GemState.REMOTE.is_offline

    def test_can_communicate(self):
        """Test communication capability."""
        assert GemState.COMMUNICATING_OFFLINE.can_communicate
        assert GemState.ATTEMPT_ONLINE.can_communicate
        assert GemState.LOCAL.can_communicate
        assert GemState.REMOTE.can_communicate
        assert not GemState.OFFLINE.can_communicate


class TestGemEvent:
    """Tests for GemEvent enum."""

    def test_event_values(self):
        """Test event values."""
        assert GemEvent.COMMUNICATION_REQUEST.value == "COMMUNICATION_REQUEST"
        assert GemEvent.ONLINE_REQUEST.value == "ONLINE_REQUEST"
        assert GemEvent.GO_LOCAL.value == "GO_LOCAL"
        assert GemEvent.GO_REMOTE.value == "GO_REMOTE"


class TestGemStateMachine:
    """Tests for GemStateMachine."""

    @pytest.fixture
    def state_machine(self):
        """Create a state machine instance."""
        return GemStateMachine()

    def test_initial_state(self, state_machine):
        """Test initial state is OFFLINE."""
        assert state_machine.state == GemState.OFFLINE
        assert state_machine.is_offline
        assert not state_machine.is_online

    def test_initial_state_custom(self):
        """Test initial state can be customized."""
        sm = GemStateMachine(initial_state=GemState.LOCAL)
        assert sm.state == GemState.LOCAL

    @pytest.mark.asyncio
    async def test_offline_to_communicating(self, state_machine):
        """Test OFFLINE -> COMMUNICATING_OFFLINE transition."""
        result = await state_machine.post_event(GemEvent.CONNECTION_ESTABLISHED)
        assert result is True
        assert state_machine.state == GemState.COMMUNICATING_OFFLINE

    @pytest.mark.asyncio
    async def test_communicating_to_attempt_online(self, state_machine):
        """Test COMMUNICATING_OFFLINE -> ATTEMPT_ONLINE transition."""
        state_machine._state = GemState.COMMUNICATING_OFFLINE
        result = await state_machine.post_event(GemEvent.COMMUNICATION_REQUEST)
        assert result is True
        assert state_machine.state == GemState.ATTEMPT_ONLINE

    @pytest.mark.asyncio
    async def test_attempt_online_to_remote(self, state_machine):
        """Test ATTEMPT_ONLINE -> REMOTE transition."""
        state_machine._state = GemState.ATTEMPT_ONLINE
        result = await state_machine.post_event(GemEvent.ONLINE_SUCCESS)
        assert result is True
        assert state_machine.state == GemState.REMOTE
        assert state_machine.is_online

    @pytest.mark.asyncio
    async def test_attempt_online_to_communicating_on_failure(self, state_machine):
        """Test ATTEMPT_ONLINE -> COMMUNICATING_OFFLINE on failure."""
        state_machine._state = GemState.ATTEMPT_ONLINE
        result = await state_machine.post_event(GemEvent.ONLINE_FAILED)
        assert result is True
        assert state_machine.state == GemState.COMMUNICATING_OFFLINE

    @pytest.mark.asyncio
    async def test_remote_to_local(self, state_machine):
        """Test REMOTE -> LOCAL transition."""
        state_machine._state = GemState.REMOTE
        result = await state_machine.post_event(GemEvent.GO_LOCAL)
        assert result is True
        assert state_machine.state == GemState.LOCAL

    @pytest.mark.asyncio
    async def test_local_to_remote(self, state_machine):
        """Test LOCAL -> REMOTE transition."""
        state_machine._state = GemState.LOCAL
        result = await state_machine.post_event(GemEvent.GO_REMOTE)
        assert result is True
        assert state_machine.state == GemState.REMOTE

    @pytest.mark.asyncio
    async def test_local_to_communicating_offline(self, state_machine):
        """Test LOCAL -> COMMUNICATING_OFFLINE transition."""
        state_machine._state = GemState.LOCAL
        result = await state_machine.post_event(GemEvent.OFFLINE_REQUEST)
        assert result is True
        assert state_machine.state == GemState.COMMUNICATING_OFFLINE
        assert state_machine.is_offline

    @pytest.mark.asyncio
    async def test_remote_to_communicating_offline(self, state_machine):
        """Test REMOTE -> COMMUNICATING_OFFLINE transition."""
        state_machine._state = GemState.REMOTE
        result = await state_machine.post_event(GemEvent.OFFLINE_REQUEST)
        assert result is True
        assert state_machine.state == GemState.COMMUNICATING_OFFLINE

    @pytest.mark.asyncio
    async def test_online_to_host_offline_on_disconnect(self, state_machine):
        """Test online state -> HOST_OFFLINE on disconnect."""
        state_machine._state = GemState.REMOTE
        result = await state_machine.post_event(GemEvent.CONNECTION_LOST)
        assert result is True
        assert state_machine.state == GemState.HOST_OFFLINE

    @pytest.mark.asyncio
    async def test_invalid_event_no_transition(self, state_machine):
        """Test invalid event does not cause transition."""
        original_state = state_machine.state
        result = await state_machine.post_event(GemEvent.ONLINE_SUCCESS)
        assert result is False
        assert state_machine.state == original_state

    @pytest.mark.asyncio
    async def test_event_callback(self, state_machine):
        """Test event callback is called."""
        callback = AsyncMock()
        state_machine._on_state_change = callback

        state_machine._state = GemState.COMMUNICATING_OFFLINE
        await state_machine.post_event(GemEvent.COMMUNICATION_REQUEST)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == GemState.COMMUNICATING_OFFLINE
        assert args[1] == GemState.ATTEMPT_ONLINE

    @pytest.mark.asyncio
    async def test_state_history(self, state_machine):
        """Test state history is recorded."""
        # Do some transitions
        state_machine._state = GemState.COMMUNICATING_OFFLINE
        await state_machine.post_event(GemEvent.COMMUNICATION_REQUEST)

        history = state_machine.history
        assert len(history) == 1
        assert history[0][0] == GemState.COMMUNICATING_OFFLINE
        assert history[0][1] == GemEvent.COMMUNICATION_REQUEST
        assert history[0][2] == GemState.ATTEMPT_ONLINE

    @pytest.mark.asyncio
    async def test_history_limit(self, state_machine):
        """Test history has maximum limit."""
        # Fill history
        for _ in range(150):
            state_machine._state = GemState.COMMUNICATING_OFFLINE
            await state_machine.post_event(GemEvent.COMMUNICATION_REQUEST)
            state_machine._state = GemState.ATTEMPT_ONLINE
            await state_machine.post_event(GemEvent.ONLINE_FAILED)

        assert len(state_machine.history) <= 100

    def test_enable_disable(self, state_machine):
        """Test enabling and disabling state machine."""
        state_machine.disable()
        assert state_machine._enabled is False

        state_machine.enable()
        assert state_machine._enabled is True

    @pytest.mark.asyncio
    async def test_disabled_ignores_events(self, state_machine):
        """Test disabled state machine ignores events."""
        state_machine.disable()
        result = await state_machine.post_event(GemEvent.CONNECTION_ESTABLISHED)
        assert result is False

    def test_reset(self, state_machine):
        """Test reset functionality."""
        state_machine._state = GemState.REMOTE
        state_machine._history.append((GemState.LOCAL, GemEvent.GO_REMOTE, GemState.REMOTE))

        state_machine.reset()

        assert state_machine.state == GemState.OFFLINE
        assert len(state_machine.history) == 0

    def test_reset_to_custom_state(self, state_machine):
        """Test reset to custom state."""
        state_machine._state = GemState.REMOTE
        state_machine.reset(GemState.LOCAL)
        assert state_machine.state == GemState.LOCAL

    def test_get_allowed_events(self, state_machine):
        """Test getting allowed events for state."""
        state_machine._state = GemState.OFFLINE
        allowed = state_machine.get_allowed_events()
        assert GemEvent.CONNECTION_ESTABLISHED in allowed

        state_machine._state = GemState.LOCAL
        allowed = state_machine.get_allowed_events()
        assert GemEvent.GO_REMOTE in allowed
        assert GemEvent.OFFLINE_REQUEST in allowed

    def test_can_handle_s1_always(self, state_machine):
        """Test S1 messages can always be handled."""
        state_machine._state = GemState.OFFLINE
        assert state_machine.can_handle(1, 13) is True

        state_machine._state = GemState.COMMUNICATING_OFFLINE
        assert state_machine.can_handle(1, 1) is True

    def test_can_handle_other_streams_requires_online(self, state_machine):
        """Test non-S1 streams require online state."""
        state_machine._state = GemState.OFFLINE
        assert state_machine.can_handle(2, 13) is False

        state_machine._state = GemState.LOCAL
        assert state_machine.can_handle(2, 13) is True

        state_machine._state = GemState.REMOTE
        assert state_machine.can_handle(6, 1) is True


class TestGemStateMachineFlow:
    """Test complete state machine flow."""

    @pytest.mark.asyncio
    async def test_full_online_flow(self):
        """Test complete flow from OFFLINE to REMOTE."""
        sm = GemStateMachine()

        # OFFLINE -> CONNECTED
        assert sm.state == GemState.OFFLINE
        await sm.post_event(GemEvent.CONNECTION_ESTABLISHED)
        assert sm.state == GemState.COMMUNICATING_OFFLINE

        # COMMUNICATING -> ATTEMPT_ONLINE
        await sm.post_event(GemEvent.COMMUNICATION_REQUEST)
        assert sm.state == GemState.ATTEMPT_ONLINE

        # ATTEMPT_ONLINE -> REMOTE
        await sm.post_event(GemEvent.ONLINE_SUCCESS)
        assert sm.state == GemState.REMOTE
        assert sm.is_online

        # REMOTE -> LOCAL
        await sm.post_event(GemEvent.GO_LOCAL)
        assert sm.state == GemState.LOCAL

        # LOCAL -> OFFLINE
        await sm.post_event(GemEvent.OFFLINE_REQUEST)
        assert sm.state == GemState.COMMUNICATING_OFFLINE
        await sm.post_event(GemEvent.CONNECTION_LOST)
        assert sm.state == GemState.OFFLINE

    @pytest.mark.asyncio
    async def test_online_failed_flow(self):
        """Test flow when online attempt fails."""
        sm = GemStateMachine()

        await sm.post_event(GemEvent.CONNECTION_ESTABLISHED)
        await sm.post_event(GemEvent.COMMUNICATION_REQUEST)
        assert sm.state == GemState.ATTEMPT_ONLINE

        await sm.post_event(GemEvent.ONLINE_FAILED)
        assert sm.state == GemState.COMMUNICATING_OFFLINE

        # Can retry
        await sm.post_event(GemEvent.COMMUNICATION_REQUEST)
        assert sm.state == GemState.ATTEMPT_ONLINE

        await sm.post_event(GemEvent.ONLINE_SUCCESS)
        assert sm.state == GemState.REMOTE

    @pytest.mark.asyncio
    async def test_connection_lost_flow(self):
        """Test flow when connection is lost."""
        sm = GemStateMachine()

        # Go online
        await sm.post_event(GemEvent.CONNECTION_ESTABLISHED)
        await sm.post_event(GemEvent.COMMUNICATION_REQUEST)
        await sm.post_event(GemEvent.ONLINE_SUCCESS)
        assert sm.state == GemState.REMOTE

        # Lose connection
        await sm.post_event(GemEvent.CONNECTION_LOST)
        assert sm.state == GemState.HOST_OFFLINE

        # Reconnect
        await sm.post_event(GemEvent.CONNECTION_ESTABLISHED)
        assert sm.state == GemState.REMOTE
