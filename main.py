"""
Retail Monitor — main async entry point.

Launches all monitors concurrently using asyncio.  Each monitor runs its own
independent loop and never blocks the others.  A crash in one monitor is logged
and that monitor restarts after its normal interval — it never takes down the
rest of the system.
"""
import asyncio
import logging
import os
import sys

import colorlog

from monitors.amazon         import AmazonMonitor
from monitors.amazon_coupons import AmazonCouponsMonitor
from monitors.amazon_deals   import AmazonDealsMonitor
from monitors.bestbuy        import BestBuyMonitor
from monitors.walmart        import WalmartMonitor
from monitors.target         import TargetMonitor
from monitors.nike_snkrs     import NikeSnkrsMonitor
from monitors.footsites      import FootsitesMonitor


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


# ── Health-check HTTP server (keeps Railway from terminating the dyno) ────────

async def _health_server(port: int = 8080) -> None:
    from aiohttp import web  # optional dep — skip if not installed

    async def _handler(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", _handler)
    app.router.add_get("/health", _handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.getLogger(__name__).info("Health-check server running on port %d", port)


# ── Main ──────────────────────────────────────────────────────────────────────

async def _main() -> None:
    _setup_logging()
    log = logging.getLogger(__name__)
    log.info("=== Retail Monitor starting ===")

    monitors = [
        AmazonMonitor(),
        AmazonCouponsMonitor(),   # auto-scans amazon.com/coupons hub
        AmazonDealsMonitor(),     # auto-scans amazon.com/deals page
        BestBuyMonitor(),
        WalmartMonitor(),
        TargetMonitor(),
        NikeSnkrsMonitor(),
        FootsitesMonitor(),
    ]

    tasks = [asyncio.create_task(m.run(), name=m.name) for m in monitors]

    # Start health-check server (ignore ImportError if aiohttp isn't installed)
    try:
        tasks.append(asyncio.create_task(_health_server()))
    except Exception:
        pass

    log.info("All %d monitors launched.", len(monitors))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nShutting down.")
        sys.exit(0)
