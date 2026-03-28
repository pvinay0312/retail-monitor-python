"""
Footsites monitor — Foot Locker, Champs Sports, Kids Foot Locker.

APPROACH: Direct JSON API calls via curl_cffi instead of Playwright.
Kasada only protects browser page loads with a JS challenge.
The backend product API at /api/products/pdp/{SKU} is server-side and
returns plain JSON without any JS challenge — curl_cffi Chrome TLS
impersonation is sufficient to access it.

API endpoint:  https://www.{domain}/api/products/pdp/{SKU}
SKU extracted from product URL:  .../product/{name}/{SKU}.html
"""
import asyncio
import logging
import random
import re
import time
import uuid

from config.products import FOOTSITES_PRODUCTS
from config.settings import FOOTSITES_WEBHOOK_URL, FOOTSITES_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_restock_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

NOTIFY_COOLDOWN = 3600   # 1 hour per SKU
BOT_BACKOFF     = 3600   # 1 hr per SKU on 403/429 — datacenter IPs stay blocked longer
_STOCK          = "fl_stock.json"
_NOTIFY         = "fl_notify.json"

AVAILABLE_STATUSES = {"IN_STOCK", "AVAILABLE", "PURCHASABLE", "ACTIVE", "STOCKED"}

# Domain → API base URL
_API = {
    "footlocker.com":     "https://www.footlocker.com/api/products/pdp",
    "champssports.com":   "https://www.champssports.com/api/products/pdp",
    "kidsfootlocker.com": "https://www.kidsfootlocker.com/api/products/pdp",
}


class FootsitesMonitor(BaseMonitor):
    name     = "Footsites"
    interval = FOOTSITES_INTERVAL

    def __init__(self):
        super().__init__()
        self._sku_blocked: dict[str, float] = {}

    async def check(self) -> None:
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)
        session = make_session("chrome120")
        try:
            # Session warmup — visit the homepage to pick up session + Kasada cookies.
            # Without a warmup the very first API request comes from a "cold" session
            # which is easier for Kasada to flag as bot traffic.
            try:
                warmup_ua = random_ua()
                warmup_h  = base_headers(warmup_ua, referer="https://www.google.com/")
                await session.get("https://www.footlocker.com/", headers=warmup_h, timeout=15)
                await asyncio.sleep(random.uniform(2.0, 4.0))
            except Exception:
                pass  # warmup failure is non-fatal

            for url in FOOTSITES_PRODUCTS:
                sku = _sku(url)
                if not sku:
                    continue
                blocked_until = self._sku_blocked.get(sku, 0)
                if time.time() < blocked_until:
                    mins = (blocked_until - time.time()) / 60
                    log.debug("[Footsites] SKU %s in backoff — %.0fm remaining", sku, mins)
                    continue
                await self._check_product(url, sku, session, stock, notify)
                await asyncio.sleep(random.uniform(1.5, 3.0))
        finally:
            await session.close()

        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)

    async def _check_product(self, url: str, sku: str, session, stock: dict, notify: dict) -> None:
        domain  = _domain(url)
        api_url = f"{_API.get(domain, _API['footlocker.com'])}/{sku}"
        headers = _api_headers(url, sku)

        try:
            resp = await session.get(api_url, headers=headers, timeout=15)
        except Exception as exc:
            log.debug("[Footsites] Request error %s: %s", sku, exc)
            return

        if resp.status_code in (403, 429):
            log.warning("[Footsites] Bot-blocked (%d) on %s — backing off %ds", resp.status_code, sku, BOT_BACKOFF)
            self._sku_blocked[sku] = time.time() + BOT_BACKOFF
            return
        if resp.status_code == 404:
            log.debug("[Footsites] %s → 404, skipping", sku)
            return
        if resp.status_code != 200:
            log.debug("[Footsites] %s → HTTP %d", sku, resp.status_code)
            return

        try:
            data = resp.json()
        except Exception:
            log.debug("[Footsites] JSON parse error for %s", sku)
            return

        product = _parse_api(data)
        if not product:
            return

        name      = product["name"]
        price     = product["price"]
        in_stock  = product["in_stock"]
        sizes     = product["sizes"]
        image     = product["image"]
        price_str = f"${price:.2f}" if price else "N/A"

        prev_in_stock = stock.get(sku, {}).get("in_stock", True)
        prev_oos_cnt  = stock.get(sku, {}).get("oos_count", 0)

        log.info("[Footsites] %s | %s | in_stock=%s | sizes=%d",
                 sku, name[:50], in_stock, len(sizes))

        if in_stock and not prev_in_stock and prev_oos_cnt >= 1:
            on_cool = (time.time() - notify.get(sku, 0)) < NOTIFY_COOLDOWN
            if not on_cool:
                log.info("[Footsites] RESTOCK: %s | %s", sku, name)
                fields = [{"name": "🔑 SKU", "value": sku, "inline": True}]
                if sizes:
                    fields.append({
                        "name":   f"📐 Available Sizes ({len(sizes)})",
                        "value":  ", ".join(sizes[:25]),
                        "inline": False,
                    })
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sku(url: str) -> str:
    """Extract SKU from Foot Locker product URL: .../product/{name}/{SKU}.html"""
    m = re.search(r"/([A-Za-z0-9]+)\.html$", url)
    return m.group(1).upper() if m else ""


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else "footlocker.com"


def _api_headers(product_url: str, sku: str) -> dict:
    """Build headers that mimic a real XHR from the product page."""
    from urllib.parse import urlparse
    ua     = random_ua()
    h      = base_headers(ua, referer=product_url)
    parsed = urlparse(product_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    h.update({
        "Accept":             "application/json, text/plain, */*",
        "Origin":             origin,
        "x-fl-request-id":    str(uuid.uuid4()),
        "Sec-Fetch-Dest":     "empty",
        "Sec-Fetch-Mode":     "cors",
        "Sec-Fetch-Site":     "same-origin",
        "X-Requested-With":   "XMLHttpRequest",
    })
    h.pop("Upgrade-Insecure-Requests", None)
    h.pop("Sec-Fetch-User", None)
    return h


def _parse_api(data: dict) -> dict | None:
    """Parse Foot Locker /api/products/pdp JSON into a normalised product dict."""
    if not isinstance(data, dict):
        return None

    # Name
    name = (data.get("name") or data.get("productName") or "")[:200]
    if not name:
        return None

    # Price — try several field names FL has used
    price_raw = (
        data.get("currentPrice") or
        data.get("salePrice") or
        data.get("regularPrice") or
        data.get("price")
    )
    price: float | None = None
    try:
        price = float(price_raw) if price_raw else None
    except (ValueError, TypeError):
        pass

    # Variants / SKUs — FL uses "variants", "skus", or "productVariants"
    variants = (
        data.get("variants") or
        data.get("skus") or
        data.get("productVariants") or
        []
    )

    in_stock = False
    sizes: list[str] = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        avail = (
            v.get("availabilityStatus") or
            v.get("availability") or
            v.get("stockStatus") or
            ""
        ).upper()
        # Size can live at top level or nested under "attributes"
        attrs = v.get("attributes") or {}
        size  = (
            v.get("size") or
            v.get("localizedSize") or
            attrs.get("size") or
            ""
        )
        oos = {"OUT_OF_STOCK", "UNAVAILABLE", "NOT_AVAILABLE", "SOLD_OUT"}
        if avail not in oos and (avail in AVAILABLE_STATUSES or avail == ""):
            if size:
                in_stock = True
                sizes.append(str(size))
        # Also flag in_stock if any variant is explicitly available
        if avail in AVAILABLE_STATUSES:
            in_stock = True

    # Image
    images = data.get("images") or data.get("colorways") or []
    image  = ""
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            image = (
                first.get("src") or
                first.get("url") or
                first.get("imageUrl") or
                first.get("imageId") or
                ""
            )
            # FL sometimes gives just an imageId — build the CDN URL
            if image and not image.startswith("http"):
                image = f"https://images.footlocker.com/is/image/FLUS/{image}?wid=500"
    elif isinstance(images, dict):
        image = images.get("src") or images.get("url") or ""

    # Sort sizes numerically
    sizes = _sort_sizes(list(set(sizes)))

    return {"name": name, "price": price, "in_stock": in_stock,
            "sizes": sizes, "image": image}


def _sort_sizes(sizes: list[str]) -> list[str]:
    def key(s: str) -> float:
        m = re.search(r"[\d.]+", s)
        return float(m.group()) if m else 99.0
    return sorted(sizes, key=key)