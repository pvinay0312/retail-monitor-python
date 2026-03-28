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
from monitors.amazon_outlet  import AmazonOutletMonitor
from monitors.woot           import WootMonitor
from monitors.bestbuy        import BestBuyMonitor
from monitors.walmart        import WalmartMonitor
from monitors.target         import TargetMonitor
from monitors.nike_snkrs     import NikeSnkrsMonitor
from monitors.footsites      import FootsitesMonitor


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    # On Railway: write to stdout so the log ingester correctly classifies severity.
    # stderr output is always tagged as error by Railway regardless of content.
    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))
    if on_railway:
        import sys
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
    else:
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
    try:
        from aiohttp import web
    except ImportError:
        logging.getLogger(__name__).warning("aiohttp not installed — health-check server disabled")
        return

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

    # Startup webhook audit — shows which channels are configured in Railway env vars
    from config.settings import (
        AMAZON_WEBHOOK_URL, BESTBUY_WEBHOOK_URL, WALMART_WEBHOOK_URL,
        TARGET_WEBHOOK_URL, FOOTSITES_WEBHOOK_URL, NIKE_SNKRS_WEBHOOK_URL,
        UPCOMING_DROPS_WEBHOOK_URL, WOOT_WEBHOOK_URL,
    )
    webhooks = {
        "AMAZON":         AMAZON_WEBHOOK_URL,
        "BESTBUY":        BESTBUY_WEBHOOK_URL,
        "WALMART":        WALMART_WEBHOOK_URL,
        "TARGET":         TARGET_WEBHOOK_URL,
        "FOOTSITES":      FOOTSITES_WEBHOOK_URL,
        "NIKE_SNKRS":     NIKE_SNKRS_WEBHOOK_URL,
        "UPCOMING_DROPS": UPCOMING_DROPS_WEBHOOK_URL,
        "WOOT":           WOOT_WEBHOOK_URL,
    }
    for name, url in webhooks.items():
        if url:
            log.info("  Webhook %-16s CONFIGURED", name)
        else:
            log.error("  Webhook %-16s NOT SET — alerts for this channel will be silenced!", name)

    monitors = [
        AmazonMonitor(),
        AmazonCouponsMonitor(),   # auto-scans amazon.com/coupons hub
        AmazonDealsMonitor(),     # auto-scans amazon.com/deals page
        AmazonOutletMonitor(),    # auto-scans amazon.com/outlet/deals (overstock)
        WootMonitor(),            # woot.com daily deals + Woot-Off flash sales
        BestBuyMonitor(),
        # WalmartMonitor(),       # disabled — Akamai blocks _abck cookie even from home IP
        TargetMonitor(),
        NikeSnkrsMonitor(),
        # FootsitesMonitor(),     # disabled — Kasada blocks even from home IP
    ]

    tasks = [asyncio.create_task(m.run(), name=m.name) for m in monitors]

    # Start health-check server only on Railway (keeps the dyno alive)
    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))
    if on_railway:
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
