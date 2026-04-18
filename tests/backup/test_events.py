import asyncio
from app.backup.events import Event, EventBus

def test_publish_and_subscribe():
    bus = EventBus()
    received = []
    async def run():
        q = bus.subscribe()
        bus.publish(Event(type="test", data={"key": "value"}))
        event = await asyncio.wait_for(q.get(), timeout=1.0)
        received.append(event)
    asyncio.run(run())
    assert len(received) == 1
    assert received[0].type == "test"
    assert received[0].data == {"key": "value"}

def test_multiple_subscribers():
    bus = EventBus()
    async def run():
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish(Event(type="hello", data={}))
        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert e1.type == "hello"
        assert e2.type == "hello"
    asyncio.run(run())

def test_unsubscribe():
    bus = EventBus()
    async def run():
        q = bus.subscribe()
        bus.unsubscribe(q)
        bus.publish(Event(type="ignored", data={}))
        assert q.empty()
    asyncio.run(run())

def test_publish_no_subscribers():
    bus = EventBus()
    bus.publish(Event(type="orphan", data={}))
