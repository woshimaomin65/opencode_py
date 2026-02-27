"""
Bus module for OpenCode.

Provides event bus functionality for inter-module communication.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BusEvent:
    """Event definition for the bus system."""
    type: str
    properties: type
    
    @classmethod
    def define(cls, event_type: str, properties_class: type) -> 'BusEvent':
        """Define a new event type."""
        return cls(type=event_type, properties=properties_class)


class Bus:
    """
    Event bus for publishing and subscribing to events.
    
    Provides:
    - Event publishing
    - Subscription management
    - One-time subscriptions
    """
    
    _subscriptions: Dict[str, List[Callable]] = {}
    
    @classmethod
    def publish(cls, event: BusEvent, properties: Any) -> None:
        """
        Publish an event to the bus.
        
        Args:
            event: Event definition
            properties: Event properties
        """
        payload = {
            "type": event.type,
            "properties": properties,
        }
        
        # Call subscribers for this event type
        for callback in cls._subscriptions.get(event.type, []):
            try:
                callback(payload)
            except Exception as e:
                # Log error but don't fail the publish
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in event subscriber for {event.type}: {e}")
        
        # Call wildcard subscribers
        for callback in cls._subscriptions.get("*", []):
            try:
                callback(payload)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in wildcard event subscriber: {e}")
    
    @classmethod
    def subscribe(cls, event: BusEvent, callback: Callable[[dict], None]) -> Callable[[], None]:
        """
        Subscribe to an event.
        
        Args:
            event: Event definition
            callback: Callback function that receives the event payload
        
        Returns:
            Unsubscribe function
        """
        if event.type not in cls._subscriptions:
            cls._subscriptions[event.type] = []
        
        cls._subscriptions[event.type].append(callback)
        
        def unsubscribe():
            if event.type in cls._subscriptions:
                try:
                    cls._subscriptions[event.type].remove(callback)
                except ValueError:
                    pass
        
        return unsubscribe
    
    @classmethod
    def subscribe_all(cls, callback: Callable[[dict], None]) -> Callable[[], None]:
        """
        Subscribe to all events.
        
        Args:
            callback: Callback function that receives all event payloads
        
        Returns:
            Unsubscribe function
        """
        if "*" not in cls._subscriptions:
            cls._subscriptions["*"] = []
        
        cls._subscriptions["*"].append(callback)
        
        def unsubscribe():
            if "*" in cls._subscriptions:
                try:
                    cls._subscriptions["*"].remove(callback)
                except ValueError:
                    pass
        
        return unsubscribe
    
    @classmethod
    def once(cls, event: BusEvent, callback: Callable[[dict], Optional[str]]) -> None:
        """
        Subscribe to an event once.
        
        Args:
            event: Event definition
            callback: Callback function. Return "done" to unsubscribe.
        """
        def wrapper(payload: dict):
            result = callback(payload)
            if result == "done":
                unsubscribe()
        
        unsubscribe = cls.subscribe(event, wrapper)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all subscriptions."""
        cls._subscriptions.clear()
