"""Message bus for decoupled inter-module communication.

This module provides an asynchronous message bus for event-driven communication
between components of the AutoLab system.
"""

from .queue import Event, EventType, MessageBus

__all__ = ["Event", "EventType", "MessageBus"]
