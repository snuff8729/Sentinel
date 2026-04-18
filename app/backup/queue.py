from __future__ import annotations
import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlparse
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

@dataclass
class DomainConfig:
    concurrency: int = 2
    delay: float = 1.0

_DEFAULT_CONFIGS: dict[str, DomainConfig] = {
    "arca.live": DomainConfig(
        concurrency=int(os.environ.get("DOWNLOAD_ARCA_LIVE_CONCURRENCY", "1")),
        delay=float(os.environ.get("DOWNLOAD_ARCA_LIVE_DELAY", "3")),
    ),
    "namu.la": DomainConfig(
        concurrency=int(os.environ.get("DOWNLOAD_NAMU_LA_CONCURRENCY", "3")),
        delay=float(os.environ.get("DOWNLOAD_NAMU_LA_DELAY", "1")),
    ),
}

_DEFAULT_FALLBACK = DomainConfig(
    concurrency=int(os.environ.get("DOWNLOAD_DEFAULT_CONCURRENCY", "2")),
    delay=float(os.environ.get("DOWNLOAD_DEFAULT_DELAY", "1")),
)

class DownloadQueue:
    def __init__(self, domain_overrides: dict[str, DomainConfig] | None = None):
        self._configs: dict[str, DomainConfig] = {**_DEFAULT_CONFIGS}
        if domain_overrides:
            self._configs.update(domain_overrides)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    def get_domain_config(self, domain: str) -> DomainConfig:
        if domain in self._configs:
            return self._configs[domain]
        for key, cfg in self._configs.items():
            if domain.endswith(f".{key}") or domain == key:
                return cfg
        return _DEFAULT_FALLBACK

    def _get_semaphore(self, domain_key: str, concurrency: int) -> asyncio.Semaphore:
        if domain_key not in self._semaphores:
            self._semaphores[domain_key] = asyncio.Semaphore(concurrency)
        return self._semaphores[domain_key]

    def _domain_key(self, domain: str) -> str:
        for key in self._configs:
            if domain.endswith(f".{key}") or domain == key:
                return key
        return domain

    async def submit(
        self,
        url: str,
        dest: str,
        download_fn: Callable[[str, str], Awaitable[None]],
        *,
        pause_event: asyncio.Event | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        domain = urlparse(url).netloc
        domain_key = self._domain_key(domain)
        config = self.get_domain_config(domain)
        sem = self._get_semaphore(domain_key, config.concurrency)

        async def _run():
            async with sem:
                if cancel_check and cancel_check():
                    return
                if pause_event is not None:
                    await pause_event.wait()
                async with self._lock:
                    last = self._last_request[domain_key]
                    now = time.monotonic()
                    wait = config.delay - (now - last)
                    if wait > 0:
                        self._last_request[domain_key] = now + wait
                    else:
                        self._last_request[domain_key] = now
                if wait > 0:
                    logger.debug("[queue] %s — waiting %.1fs (domain: %s)", url.split("/")[-1][:20], wait, domain_key)
                    await asyncio.sleep(wait)
                if cancel_check and cancel_check():
                    return
                await download_fn(url, dest)

        task = asyncio.create_task(_run())
        self._tasks.append(task)
        await asyncio.sleep(0)

    async def wait_all(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks)
            self._tasks.clear()
