"""Base class shared by all monitor modules."""
import asyncio
import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class BaseMonitor(ABC):
    """
    Run self.check() on a fixed interval, catching and logging all exceptions
    so a single product scrape error never kills the whole monitor loop.
    """

    name: str = "monitor"
    interval: int = 300  # seconds between full cycles

    async def run(self) -> None:
        log.info("[%s] Starting (interval=%ds)", self.name, self.interval)
        while True:
            try:
                await self.check()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("[%s] Unhandled error in check() — will retry in %ds",
                              self.name, self.interval)
            await asyncio.sleep(self.interval)

    @abstractmethod
    async def check(self) -> None:
        """Override to implement one full monitoring cycle."""
        ...
