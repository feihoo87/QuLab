"""Asynchronous message bus implementation.

Provides decoupled communication between AutoLab components using
an async event-driven architecture.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine

from loguru import logger


class EventType(Enum):
    """Core event types for the AutoLab system.

    These events are used for communication between different
    components of the system.
    """

    # Agent lifecycle events
    AGENT_START = auto()
    AGENT_THINKING = auto()
    AGENT_PLAN_CREATED = auto()
    AGENT_COMPLETE = auto()
    AGENT_ERROR = auto()
    AGENT_PAUSED = auto()  # For human interaction

    # Tool events
    TOOL_CALL = auto()
    TOOL_RESULT = auto()
    TOOL_ERROR = auto()

    # Skill events
    SKILL_START = auto()
    SKILL_COMPLETE = auto()
    SKILL_ERROR = auto()
    SKILL_CODE_GENERATED = auto()

    # Execution events
    EXECUTION_START = auto()
    EXECUTION_PROGRESS = auto()
    EXECUTION_COMPLETE = auto()
    EXECUTION_ERROR = auto()

    # Analysis events
    ANALYSIS_START = auto()
    ANALYSIS_COMPLETE = auto()
    ANALYSIS_ERROR = auto()

    # World Model events
    PARAMETER_UPDATED = auto()
    STATE_CHANGED = auto()
    HISTORY_RECORDED = auto()

    # Human interaction events
    HUMAN_QUERY = auto()
    HUMAN_RESPONSE = auto()
    CONFIG_REQUEST = auto()
    CONFIG_UPDATED = auto()

    # Memory events
    MEMORY_CONSOLIDATED = auto()
    LESSON_SAVED = auto()

    # System events
    SYSTEM_ERROR = auto()
    SYSTEM_SHUTDOWN = auto()


@dataclass
class Event:
    """Event dataclass representing a system event.

    Attributes:
        type: The type of event
        payload: Event-specific data
        session_id: Session identifier
        timestamp: Unix timestamp when event was created
        event_id: Unique event identifier
        source: Source component that generated the event
    """

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation.

        Returns:
            Dictionary representation of the event
        """
        return {
            "event_id": self.event_id,
            "type": self.type.name,
            "payload": self.payload,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "source": self.source,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class MessageBus:
    """Asynchronous message bus for event-driven communication.

    The MessageBus provides a decoupled way for components to communicate
    through events. It supports:

    - Subscribing to specific event types
    - Publishing events asynchronously
    - Filtering and routing events
    - Event history for debugging

    Example:
        ```python
        bus = MessageBus()

        # Subscribe to events
        async def on_skill_start(event: Event):
            print(f"Skill started: {event.payload['skill_name']}")

        bus.subscribe(EventType.SKILL_START, on_skill_start)

        # Publish events
        await bus.publish(Event(
            type=EventType.SKILL_START,
            payload={"skill_name": "rabi_measurement"},
            session_id="session_123"
        ))

        # Start the bus
        await bus.start()
        ```
    """

    def __init__(self, max_queue_size: int = 1000, max_history: int = 10000):
        """Initialize the message bus.

        Args:
            max_queue_size: Maximum number of events in the queue
            max_history: Maximum number of events to keep in history
        """
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._history: list[Event] = []
        self._max_history = max_history
        self._running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async callback function to handle events
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.name}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> bool:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: Type of event
            handler: Handler to remove

        Returns:
            True if handler was found and removed
        """
        if event_type not in self._subscribers:
            return False

        try:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed handler from {event_type.name}")
            return True
        except ValueError:
            return False

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all event types.

        Args:
            handler: Async callback function to handle all events
        """
        for event_type in EventType:
            self.subscribe(event_type, handler)

    async def publish(self, event: Event) -> bool:
        """Publish an event to the bus.

        Args:
            event: Event to publish

        Returns:
            True if event was queued successfully, False if queue is full
        """
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Event queue full, dropping event: {event.type.name}")
            return False

    async def start(self) -> None:
        """Start the message bus event loop.

        This begins processing events from the queue and dispatching
them to subscribers.
        """
        if self._running:
            logger.warning("Message bus already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._event_loop())
        logger.info("Message bus started")

    async def stop(self) -> None:
        """Stop the message bus event loop.

        Waits for remaining events in the queue to be processed
        before stopping.
        """
        if not self._running:
            return

        self._running = False

        # Wait for queue to empty
        await self._queue.join()

        # Cancel the event loop task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Message bus stopped")

    async def _event_loop(self) -> None:
        """Main event processing loop.

        Continuously processes events from the queue and dispatches
them to subscribers.
        """
        while self._running:
            try:
                # Get event from queue with timeout to allow checking _running
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                # Add to history
                await self._add_to_history(event)

                # Dispatch to subscribers
                await self._dispatch(event)

                # Mark as done
                self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event loop: {e}")

    async def _dispatch(self, event: Event) -> None:
        """Dispatch an event to all subscribed handlers.

        Args:
            event: Event to dispatch
        """
        handlers = self._subscribers.get(event.type, [])

        # Also dispatch to wildcard subscribers
        # (we could add a special EventType.ALL for this)

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.type.name}: {e}")

    async def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining max size.

        Args:
            event: Event to add
        """
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                # Remove oldest events
                self._history = self._history[-self._max_history :]

    def get_history(
        self,
        event_type: EventType | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history with optional filtering.

        Args:
            event_type: Filter by event type
            session_id: Filter by session ID
            limit: Maximum number of events to return

        Returns:
            List of matching events
        """
        events = self._history

        if event_type:
            events = [e for e in events if e.type == event_type]

        if session_id:
            events = [e for e in events if e.session_id == session_id]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()

    @property
    def is_running(self) -> bool:
        """Check if the bus is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    @property
    def subscriber_count(self) -> dict[EventType, int]:
        """Get number of subscribers per event type."""
        return {et: len(handlers) for et, handlers in self._subscribers.items()}


class FilteredBus:
    """Wrapper around MessageBus that filters events.

    Useful for creating scoped event streams where components
    only receive events they're interested in.

    Example:
        ```python
        bus = MessageBus()
        filtered = FilteredBus(bus, session_id="session_123")

        # Only receives events for session_123
        async def handler(event):
            print(f"Received: {event.type}")

        filtered.subscribe(EventType.SKILL_START, handler)
        ```
    """

    def __init__(
        self,
        bus: MessageBus,
        session_id: str | None = None,
        event_types: list[EventType] | None = None,
        source_filter: str | None = None,
    ):
        """Initialize filtered bus.

        Args:
            bus: Parent message bus
            session_id: Filter by session ID
            event_types: Filter by event types
            source_filter: Filter by event source
        """
        self._bus = bus
        self._session_id = session_id
        self._event_types = set(event_types) if event_types else None
        self._source_filter = source_filter
        self._handlers: list[tuple[EventType, EventHandler]] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to events with filtering applied.

        Args:
            event_type: Type of event
            handler: Handler callback
        """

        async def filtered_handler(event: Event) -> None:
            # Apply filters
            if self._session_id and event.session_id != self._session_id:
                return
            if self._event_types and event.type not in self._event_types:
                return
            if self._source_filter and event.source != self._source_filter:
                return

            await handler(event)

        self._handlers.append((event_type, filtered_handler))
        self._bus.subscribe(event_type, filtered_handler)

    def unsubscribe_all(self) -> None:
        """Unsubscribe all handlers from this filtered bus."""
        for event_type, handler in self._handlers:
            self._bus.unsubscribe(event_type, handler)
        self._handlers.clear()
