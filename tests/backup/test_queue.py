import asyncio
import time
from app.backup.queue import DomainConfig, DownloadQueue

def test_domain_config_defaults():
    q = DownloadQueue()
    cfg = q.get_domain_config("unknown.com")
    assert cfg.concurrency == 2
    assert cfg.delay == 1.0

def test_domain_config_arca():
    q = DownloadQueue()
    cfg = q.get_domain_config("arca.live")
    assert cfg.concurrency == 1
    assert cfg.delay == 3.0

def test_domain_config_namu():
    q = DownloadQueue()
    cfg = q.get_domain_config("ac-p3.namu.la")
    assert cfg.concurrency == 3
    assert cfg.delay == 1.0

def test_domain_config_custom():
    overrides = {"example.com": DomainConfig(concurrency=5, delay=0.5)}
    q = DownloadQueue(domain_overrides=overrides)
    cfg = q.get_domain_config("example.com")
    assert cfg.concurrency == 5
    assert cfg.delay == 0.5

def test_download_executes_task():
    q = DownloadQueue()
    results = []
    async def fake_download(url: str, dest: str):
        results.append((url, dest))
    async def run():
        await q.submit("https://ac-p3.namu.la/img.png", "/tmp/img.png", fake_download)
        await q.wait_all()
    asyncio.run(run())
    assert len(results) == 1
    assert results[0] == ("https://ac-p3.namu.la/img.png", "/tmp/img.png")

def test_download_respects_delay():
    q = DownloadQueue(domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.3)})
    timestamps = []
    async def timed_download(url: str, dest: str):
        timestamps.append(time.monotonic())
    async def run():
        for i in range(3):
            await q.submit(f"https://ac-p3.namu.la/{i}.png", f"/tmp/{i}.png", timed_download)
        await q.wait_all()
    asyncio.run(run())
    assert len(timestamps) == 3
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        assert gap >= 0.25, f"Gap {gap} too short, expected >= 0.25s"

def test_download_concurrency_limit():
    q = DownloadQueue(domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=2, delay=0.0)})
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()
    async def track_concurrency(url: str, dest: str):
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            if current > max_concurrent:
                max_concurrent = current
        await asyncio.sleep(0.1)
        async with lock:
            current -= 1
    async def run():
        for i in range(5):
            await q.submit(f"https://ac-p3.namu.la/{i}.png", f"/tmp/{i}.png", track_concurrency)
        await q.wait_all()
    asyncio.run(run())
    assert max_concurrent <= 2

def test_download_pauses_and_resumes():
    pause_event = asyncio.Event()
    pause_event.set()
    q = DownloadQueue(domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.0)})
    order = []
    async def tracked_download(url: str, dest: str):
        order.append(url)
    async def run():
        await q.submit("https://ac-p3.namu.la/1.png", "/tmp/1.png", tracked_download, pause_event=pause_event)
        pause_event.clear()
        await q.submit("https://ac-p3.namu.la/2.png", "/tmp/2.png", tracked_download, pause_event=pause_event)
        await asyncio.sleep(0.2)
        assert len(order) == 1
        pause_event.set()
        await q.wait_all()
        assert len(order) == 2
    asyncio.run(run())

def test_download_cancels():
    q = DownloadQueue(domain_overrides={"ac-p3.namu.la": DomainConfig(concurrency=1, delay=0.0)})
    order = []
    cancelled = False
    async def tracked_download(url: str, dest: str):
        order.append(url)
    async def run():
        nonlocal cancelled
        cancel_check = lambda: cancelled
        await q.submit("https://ac-p3.namu.la/1.png", "/tmp/1.png", tracked_download, cancel_check=cancel_check)
        cancelled = True
        await q.submit("https://ac-p3.namu.la/2.png", "/tmp/2.png", tracked_download, cancel_check=cancel_check)
        await q.wait_all()
        assert len(order) == 1
    asyncio.run(run())
