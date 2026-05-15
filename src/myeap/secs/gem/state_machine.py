"""GEM Equipment State Machine

This module implements the GEM state machine according to SEMI E30 standard.

The GEM state machine defines the operational states of semiconductor equipment:
- Offline states: COMMUNICATING_OFFLINE, OFFLINE
- Online states: LOCAL, REMOTE, ATTEMPT_ONLINE

State transitions are triggered by:
- S1F1/F13 (Are You There / Establish Communication)
- S1F3/F17 (Online/Offline Request)
- S1F15/F23 (Request Off-line)

Diagram:
                    ┌──────────────────┐
                    │    OFFLINE       │
                    └────────┬─────────┘
                             │
              S1F1/F13       │       S1F1/F13
                             │
              ┌──────────────▼──────────────┐
              │   COMMUNICATING_OFFLINE     │
              └──────────────┬──────────────┘
                             │
                             │ S1F13
                             ▼
              ┌────────────────────────────┐
              │       ATTEMPT_ONLINE       │
              └──────────────┬─────────────┘
                             │
              Success        │       Failure
                             │
    ┌────────────────────────▼───────────────┐
    │                                    │   │
    │                                    ▼   │
    │  ┌──────────────┐    ┌──────────────┐ │
    │  │    LOCAL     │◄───┤   REMOTE     │ │
    │  └──────┬───────┘    └──────┬───────┘ │
    │         │                   │         │
    │         │ S1F3/F17          │ S1F3/F17 │
    │         │                   │         │
    │         │                   ▼         │
    │         └─────────────────────────────┘
    │                                     │
    │  S1F15/F23                          │
    └─────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable, Dict, Optional, Set, Any


logger = logging.getLogger(__name__)


class GemState(Enum):
    """GEM equipment states.

    Reference: SEMI E30 Table 1
    """

    # Offline states
    OFFLINE = "OFFLINE"
    COMMUNICATING_OFFLINE = "COMMUNICATING_OFFLINE"
    ATTEMPT_ONLINE = "ATTEMPT_ONLINE"

    # Online states
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"

    # Additional states
    HOST_OFFLINE = "HOST_OFFLINE"
    EQUIPMENT_OFFLINE = "EQUIPMENT_OFFLINE"

    @property
    def is_online(self) -> bool:
        """Check if state is an online state."""
        return self in [GemState.LOCAL, GemState.REMOTE]

    @property
    def is_offline(self) -> bool:
        """Check if state is an offline state."""
        return self in [
            GemState.OFFLINE,
            GemState.COMMUNICATING_OFFLINE,
            GemState.EQUIPMENT_OFFLINE,
            GemState.HOST_OFFLINE,
        ]

    @property
    def can_communicate(self) -> bool:
        """Check if equipment can exchange SECS messages in this state."""
        return self != GemState.OFFLINE


class GemEvent(Enum):
    """GEM state machine events."""

    # Communication events
    COMMUNICATION_REQUEST = "COMMUNICATION_REQUEST"  # S1F13
    COMMUNICATION_ESTABLISHED = "COMMUNICATION_ESTABLISHED"
    COMMUNICATION_LOST = "COMMUNICATION_LOST"

    # Online/Offline events
    ONLINE_REQUEST = "ONLINE_REQUEST"  # S1F3
    OFFLINE_REQUEST = "OFFLINE_REQUEST"  # S1F15
    GO_LOCAL = "GO_LOCAL"  # S1F17
    GO_REMOTE = "GO_REMOTE"  # S1F17

    # Connection events
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"
    CONNECTION_LOST = "CONNECTION_LOST"

    # Attempt events
    ONLINE_SUCCESS = "ONLINE_SUCCESS"
    ONLINE_FAILED = "ONLINE_FAILED"


@dataclass
class GemTransition:
    """State transition definition."""

    from_state: GemState
    to_state: GemState
    event: GemEvent
    condition: Optional[Callable[[], Awaitable[bool]]] = None
    action: Optional[Callable[[], Awaitable[None]]] = None


class GemStateMachine:
    """GEM Equipment State Machine.

    Manages equipment state according to SEMI E30.

    Features:
    - State tracking
    - Transition validation
    - Event handling
    - Notification callbacks

    Args:
        initial_state: Starting state (default: OFFLINE)
        on_state_change: Callback for state changes
    """

    # Valid state transitions
    TRANSITIONS: Dict[GemState, Dict[GemEvent, GemState]] = {
        GemState.OFFLINE: {
            GemEvent.CONNECTION_ESTABLISHED: GemState.COMMUNICATING_OFFLINE,
        },
        GemState.COMMUNICATING_OFFLINE: {
            GemEvent.COMMUNICATION_REQUEST: GemState.ATTEMPT_ONLINE,
            GemEvent.CONNECTION_LOST: GemState.OFFLINE,
        },
        GemState.ATTEMPT_ONLINE: {
            GemEvent.ONLINE_SUCCESS: GemState.REMOTE,
            GemEvent.ONLINE_FAILED: GemState.COMMUNICATING_OFFLINE,
            GemEvent.CONNECTION_LOST: GemState.OFFLINE,
        },
        GemState.LOCAL: {
            GemEvent.OFFLINE_REQUEST: GemState.COMMUNICATING_OFFLINE,
            GemEvent.GO_REMOTE: GemState.REMOTE,
            GemEvent.CONNECTION_LOST: GemState.HOST_OFFLINE,
        },
        GemState.REMOTE: {
            GemEvent.OFFLINE_REQUEST: GemState.COMMUNICATING_OFFLINE,
            GemEvent.GO_LOCAL: GemState.LOCAL,
            GemEvent.CONNECTION_LOST: GemState.HOST_OFFLINE,
        },
        GemState.HOST_OFFLINE: {
            GemEvent.CONNECTION_ESTABLISHED: GemState.REMOTE,
            GemEvent.CONNECTION_LOST: GemState.EQUIPMENT_OFFLINE,
        },
        GemState.EQUIPMENT_OFFLINE: {
            GemEvent.CONNECTION_ESTABLISHED: GemState.COMMUNICATING_OFFLINE,
        },
    }

    def __init__(
        self,
        initial_state: GemState = GemState.OFFLINE,
        on_state_change: Optional[Callable[[GemState, GemState], Awaitable[None]]] = None,
    ):
        self._state = initial_state
        self._on_state_change = on_state_change
        self._lock = asyncio.Lock()

        # State history for debugging
        self._history: list[tuple[GEM_STATE, GemEvent, GemState]] = []
        self._max_history = 100

        # Enable/disable
        self._enabled = True

        logger.info(f"GEM state machine initialized in state: {initial_state.value}")

    @property
    def state(self) -> GemState:
        """Get current state."""
        return self._state

    @property
    def is_online(self) -> bool:
        """Check if equipment is online."""
        return self._state.is_online

    @property
    def is_offline(self) -> bool:
        """Check if equipment is offline."""
        return self._state.is_offline

    @property
    def can_communicate(self) -> bool:
        """Check if equipment can communicate."""
        return self._state.can_communicate

    @property
    def history(self) -> list[tuple[GemState, GemEvent, GemState]]:
        """Get state transition history."""
        return self._history.copy()

    async def post_event(self, event: GemEvent) -> bool:
        """Post an event to the state machine.

        Args:
            event: Event to post

        Returns:
            True if transition occurred

        Raises:
            ValueError: If event is not valid for current state
        """
        async with self._lock:
            return await self._transition(event)

    async def _transition(self, event: GemEvent) -> bool:
        """Perform state transition.

        Args:
            event: Event causing transition

        Returns:
            True if transition occurred
        """
        if not self._enabled:
            logger.debug(f"State machine disabled, ignoring event: {event}")
            return False

        current_state = self._state

        # Check if transition is valid
        if current_state not in self.TRANSITIONS:
            logger.warning(f"No transitions defined for state: {current_state}")
            return False

        transitions = self.TRANSITIONS[current_state]

        if event not in transitions:
            logger.debug(f"No transition for event {event} in state {current_state}")
            return False

        new_state = transitions[event]

        # Log transition
        logger.info(f"GEM state transition: {current_state.value} --({event.value})--> {new_state.value}")

        # Record history
        self._history.append((current_state, event, new_state))
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Update state
        self._state = new_state

        # Notify callback
        if self._on_state_change:
            try:
                await self._on_state_change(current_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        return True

    def enable(self) -> None:
        """Enable the state machine."""
        self._enabled = True
        logger.info("GEM state machine enabled")

    def disable(self) -> None:
        """Disable the state machine."""
        self._enabled = False
        logger.info("GEM state machine disabled")

    def reset(self, state: GemState = GemState.OFFLINE) -> None:
        """Reset state machine to a state.

        Args:
            state: State to reset to
        """
        self._state = state
        self._history.clear()
        logger.info(f"GEM state machine reset to: {state.value}")

    def get_allowed_events(self) -> Set[GemEvent]:
        """Get events that are valid for current state.

        Returns:
            Set of allowed events
        """
        if self._state not in self.TRANSITIONS:
            return set()
        return set(self.TRANSITIONS[self._state].keys())

    def can_handle(self, stream: int, function: int) -> bool:
        """Check if a SECS message can be handled in current state.

        Args:
            stream: Stream number (S)
            function: Function number (F)

        Returns:
            True if message can be processed
        """
        # GEM defines which messages are allowed in which states
        # This is a simplified check

        # S1 messages (Communication) are always allowed if communicating
        if stream == 1:
            return True

        # Other streams require online state
        if not self.is_online:
            return False

        # Additional checks can be added here based on SEMI E30
        return True


# Type alias for state machine state type
GAS_STATE = GemState


__all__ = [
    "GemState",
    "GemEvent",
    "GemTransition",
    "GemStateMachine",
]
