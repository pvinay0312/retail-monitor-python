"""
Footsites monitor — Foot Locker, Kids Foot Locker, Champs Sports.

These sites use Kasada bot protection, which injects JS challenges that inspect:
  - navigator.webdriver flag
  - Chrome plugin / mimeType lists
  - WebGL fingerprint
  - CDP (DevTools Protocol) presence

We use Playwright with playwright-stealth to patch all of these at the browser level.
"""
import asyncio
import json
import logging
import re
import time

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PWTimeout

from config.products import FOOTSITES_PRODUCTS
from config.settings import FOOTSITES_WEBHOOK_URL, FOOTSITES_INTERVAL, CHROMIUM_PATH
from monitors.base import BaseMonitor
from utils.discord_client import send_restock_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

NOTIFY_COOLDOWN = 3600   # 1 hour per product

_STOCK  = "fl_stock.json"
_NOTIFY = "fl_notify.json"

AVAILABLE_STATUSES = {"IN_STOCK", "AVAILABLE", "PURCHASABLE"}

# Headers that mimic a real Chrome request on Windows
EXTRA_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control":   "no-cache",
    "Pragma":          "no-cache",
    "sec-ch-ua":       '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "cross-site",
    "Sec-Fetch-User":  "?1",
    "Upgrade-Insecure-Requests": "1",
}


class FootsitesMonitor(BaseMonitor):
    name = "Footsites"
    interval = FOOTSITES_INTERVAL

    async def check(self) -> None:
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        async with async_playwright() as pw:
            browser = await _launch_browser(pw)
            context = await _new_context(browser)
            try:
                page = await context.new_page()
                await _apply_stealth(page)

                for url in FOOTSITES_PRODUCTS:
                    try:
                        await self._check_product(url, page, stock, notify)
                    except Exception:
                        log.exception("[Footsites] Error on %s", url)
                        # Restart the page to clear any bad state
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = await context.new_page()
                        await _apply_stealth(page)
                    await asyncio.sleep(2)

                await page.close()
            finally:
                await context.close()
                await browser.close()

        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)

    async def _check_product(self, url: str, page: Page, stock: dict, notify: dict) -> None:
        sku = _sku(url)

        # Block images, fonts and media to speed up load while keeping scripts
        await page.route("**/*", _block_unnecessary)
        await page.set_extra_http_headers(EXTRA_HEADERS)

        html = await _fetch_page(page, url)
        if not html:
            return

        product = _parse_next_data(html)
        if not product:
            log.debug("[Footsites] No product data for %s", sku)
            return

        name     = product.get("name", "Unknown")[:200]
        in_stock = product.get("in_stock", False)
        price    = product.get("price")
        image    = product.get("image", "")
        sizes    = product.get("sizes", [])

        if price is None:
            return

        price_str = f"${price:.2f}"

        # ── Restock detection ─────────────────────────────────────────────────
        prev_in_stock = stock.get(sku, {}).get("in_stock", True)
        prev_oos_cnt  = stock.get(sku, {}).get("oos_count", 0)

        if in_stock and not prev_in_stock and prev_oos_cnt >= 1:
            on_cool = (time.time() - notify.get(sku, 0)) < NOTIFY_COOLDOWN
            if not on_cool:
                log.info("[Footsites] RESTOCK: %s | %s", name, sku)
                fields = [{"name": "🔑 SKU",    "value": sku,          "inline": True}]
                if sizes:
                    fields.append({"name": "📐 Sizes", "value": ", ".join(sizes[:20]), "inline": False})
                await send_restock_alert(
                    FOOTSITES_WEBHOOK_URL, store="footsites",
                    name=name, url=url, price=price_str, image=image,
                    extra_fields=fields,
                )
                notify[sku] = time.time()

        stock[sku] = {
            "in_stock":  in_stock,
            "oos_count": 0 if in_stock else prev_oos_cnt + 1,
        }


# ── Browser helpers ───────────────────────────────────────────────────────────

async def _launch_browser(pw) -> Browser:
    launch_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
    ]
    executable = CHROMIUM_PATH or None
    return await pw.chromium.launch(
        headless=True,
        args=launch_args,
        executable_path=executable or None,
    )


async def _new_context(browser: Browser) -> BrowserContext:
    return await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        ignore_https_errors=False,
        extra_http_headers=EXTRA_HEADERS,
    )


async def _apply_stealth(page: Page) -> None:
    """Patch JS properties that Kasada checks to detect headless browsers."""
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        # Manual stealth if playwright-stealth is unavailable
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)


async def _fetch_page(page: Page, url: str) -> str | None:
    """Navigate to url and return page HTML, or None on failure."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await asyncio.sleep(4)   # let Kasada JS complete
        # Race content extraction against a 30s wall
        content_task = asyncio.ensure_future(page.content())
        await asyncio.wait_for(content_task, timeout=30)
        return content_task.result()
    except (PWTimeout, asyncio.TimeoutError):
        log.debug("[Footsites] Page timeout for %s", url)
    except Exception as exc:
        log.debug("[Footsites] Page error %s: %s", url, exc)
    return None


async def _block_unnecessary(route):
    """Block images, fonts, and media to speed up page loads."""
    if route.request.resource_type in ("image", "media", "font", "stylesheet"):
        await route.abort()
    else:
        await route.continue_()


# ── Data extraction ───────────────────────────────────────────────────────────

def _sku(url: str) -> str:
    m = re.search(r"/([A-Z0-9]+)\.html", url, re.I)
    return m.group(1).upper() if m else url


def _parse_next_data(html: str) -> dict | None:
    m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        raw = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    # Navigate Foot Locker / Champs __NEXT_DATA__ structure
    try:
        product_node = _dig(raw, "props", "pageProps", "initialData", "data", "product")
        if not product_node:
            product_node = _deep_find_product(raw)
        if not product_node:
            return None

        name      = product_node.get("name", "")
        price_raw = product_node.get("currentPrice") or product_node.get("price")
        price     = float(price_raw) if price_raw else None

        # Availability from variants / skus
        variants = (product_node.get("skus") or product_node.get("variants")
                    or product_node.get("productVariants", []))
        in_stock  = False
        sizes     = []
        for v in variants:
            avail = (v.get("availabilityStatus") or v.get("availability") or "").upper()
            size  = v.get("size") or v.get("localizedSize") or ""
            if avail in AVAILABLE_STATUSES:
                in_stock = True
                if size:
                    sizes.append(size)

        # Image
        imgs  = product_node.get("images") or product_node.get("colorways", [{}])[0].get("images", [])
        image = ""
        if isinstance(imgs, list) and imgs:
            image = imgs[0].get("src") or imgs[0].get("url") or ""
        elif isinstance(imgs, dict):
            image = imgs.get("src") or imgs.get("url") or ""

        return {"name": name, "price": price, "in_stock": in_stock,
                "sizes": sizes, "image": image}
    except Exception:
        return None


def _dig(obj: dict, *keys):
    """Safely traverse nested dicts."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _deep_find_product(obj, depth: int = 0) -> dict | None:
    if depth > 10:
        return None
    if isinstance(obj, dict):
        if "name" in obj and ("currentPrice" in obj or "price" in obj):
            return obj
        for v in obj.values():
            r = _deep_find_product(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _deep_find_product(item, depth + 1)
            if r:
                return r
    return None
