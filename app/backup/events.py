from __future__ import annotations
import asyncio
from dataclasses import dataclass, field

@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)

class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    def publish(self, event: Event) -> None:
        for q in self._subscribers:
            q.put_nowait(event)
