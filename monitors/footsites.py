"""
Footsites monitor — Foot Locker, Champs Sports, Kids Foot Locker.

APPROACH: All product API calls are made from inside the same patchright
browser that solved the Kasada/Akamai challenge.  curl_cffi is not used
for Footsites because the cookies cannot be transferred — Kasada ties its
tokens to the browser session's TLS fingerprint.

API endpoint:  https://www.{domain}/api/products/pdp/{SKU}
SKU extracted from product URL:  .../product/{name}/{SKU}.html
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import time

from config.products import FOOTSITES_PRODUCTS
from config.settings import FOOTSITES_WEBHOOK_URL, FOOTSITES_INTERVAL
from monitors.base import BaseMonitor
from utils.discord_client import send_restock_alert
from utils.playwright_session import fetch_products_via_page_navigation
from utils.storage import load, save

log = logging.getLogger(__name__)

NOTIFY_COOLDOWN = 3600
BOT_BACKOFF     = 3600
_STOCK          = "fl_stock.json"
_NOTIFY         = "fl_notify.json"

AVAILABLE_STATUSES = {"IN_STOCK", "AVAILABLE", "PURCHASABLE", "ACTIVE", "STOCKED"}

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

        # Build product list — navigate each page, intercept the PDP API response
        products: list[dict] = []
        sku_to_url: dict[str, str] = {}
        for url in FOOTSITES_PRODUCTS:
            sku = _sku(url)
            if not sku:
                continue
            if time.time() < self._sku_blocked.get(sku, 0):
                mins = (self._sku_blocked[sku] - time.time()) / 60
                log.debug("[Footsites] SKU %s in backoff — %.0fm remaining", sku, mins)
                continue
            products.append({
                "key":         sku,
                "url":         url,
                "api_pattern": "**/api/products/pdp/**",
            })
            sku_to_url[sku] = url

        if not products:
            log.info("[Footsites] All SKUs in backoff — skipping cycle")
            return

        # Navigate to each product page; browser intercepts the PDP API call
        results = await fetch_products_via_page_navigation(
            "https://www.footlocker.com/",
            products,
            delay_between=3.0,
        )

        for sku, raw in results.items():
            url     = sku_to_url.get(sku, "")
            product = _parse_api(raw)
            if not product:
                continue
            await self._process_product(sku, url, product, stock, notify)

        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)
        log.info("[Footsites] Cycle complete — %d/%d SKUs fetched",
                 len(results), len(api_calls))

    async def _process_product(self, sku: str, url: str, product: dict,
                                stock: dict, notify: dict) -> None:
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
    m = re.search(r"/([A-Za-z0-9]+)\.html$", url)
    return m.group(1).upper() if m else ""


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else "footlocker.com"


def _parse_api(data: dict) -> dict | None:
    if not isinstance(data, dict):
        return None

    name = (data.get("name") or data.get("productName") or "")[:200]
    if not name:
        return None

    price_raw = (
        data.get("currentPrice") or data.get("salePrice") or
        data.get("regularPrice") or data.get("price")
    )
    price: float | None = None
    try:
        price = float(price_raw) if price_raw else None
    except (ValueError, TypeError):
        pass

    variants = (
        data.get("variants") or data.get("skus") or
        data.get("productVariants") or []
    )

    in_stock = False
    sizes: list[str] = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        avail = (
            v.get("availabilityStatus") or v.get("availability") or
            v.get("stockStatus") or ""
        ).upper()
        attrs = v.get("attributes") or {}
        size  = (
            v.get("size") or v.get("localizedSize") or
            attrs.get("size") or ""
        )
        oos = {"OUT_OF_STOCK", "UNAVAILABLE", "NOT_AVAILABLE", "SOLD_OUT"}
        if avail not in oos and (avail in AVAILABLE_STATUSES or avail == ""):
            if size:
                in_stock = True
                sizes.append(str(size))
        if avail in AVAILABLE_STATUSES:
            in_stock = True

    images = data.get("images") or data.get("colorways") or []
    image  = ""
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            image = (
                first.get("src") or first.get("url") or
                first.get("imageUrl") or first.get("imageId") or ""
            )
            if image and not image.startswith("http"):
                image = f"https://images.footlocker.com/is/image/FLUS/{image}?wid=500"
    elif isinstance(images, dict):
        image = images.get("src") or images.get("url") or ""

    sizes = _sort_sizes(list(set(sizes)))
    return {"name": name, "price": price, "in_stock": in_stock,
            "sizes": sizes, "image": image}


def _sort_sizes(sizes: list[str]) -> list[str]:
    def key(s: str) -> float:
        m = re.search(r"[\d.]+", s)
        return float(m.group()) if m else 99.0
    return sorted(sizes, key=key)