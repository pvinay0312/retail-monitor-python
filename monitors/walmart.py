"""
Walmart monitor — fetches product data via an in-browser session.

Instead of extracting cookies and replaying them with curl_cffi (which fails
because Akamai ties _abck to the browser's TLS fingerprint), we keep the
patchright browser open through the entire product-fetch cycle.  After the
Akamai challenge is solved on the homepage, all terra-firma API calls are made
with fetch() inside that same browser context — consistent session, no mismatch.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from bs4 import BeautifulSoup

from config.products import WALMART_PRODUCTS
from config.settings import WALMART_WEBHOOK_URL, WALMART_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.playwright_session import fetch_products_via_page_navigation
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_THRESHOLD = 0.15   # 15% off
DEAL_COOLDOWN  = 3600
BOT_BACKOFF    = 3600

BLOCK_STATUSES = {412, 429, 503, 521}
BLOCK_TITLES   = {"robot", "blocked", "access denied", "captcha", "unavailable"}

_PRICES = "wm_prices.json"
_STOCK  = "wm_stock.json"
_NOTIFY = "wm_notify.json"


def _item_id(url: str) -> str:
    m = re.search(r"/ip/[^/]+/(\d+)", url)
    return m.group(1) if m else url


class WalmartMonitor(BaseMonitor):
    name = "Walmart"
    interval = WALMART_INTERVAL

    def __init__(self):
        self._url_blocked: dict[str, float] = {}

    async def check(self) -> None:
        prices = await load(_PRICES)
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        # Build product list — navigate to each page, intercept terra-firma response
        products: list[dict] = []
        for url in WALMART_PRODUCTS:
            item_id = _item_id(url)
            if time.time() < self._url_blocked.get(item_id, 0):
                log.debug("[Walmart] Skipping %s (backoff)", item_id)
                continue
            products.append({
                "key": item_id,
                "url": url,
                # No api_pattern — extract __NEXT_DATA__ embedded in the page HTML
                # (terra-firma is only called on SPA navigation, not cold page loads)
            })

        if not products:
            log.info("[Walmart] All products in backoff — skipping cycle")
            return

        # Navigate to each product page; browser intercepts the terra-firma call
        raw_results = await fetch_products_via_page_navigation(
            "https://www.walmart.com/",
            products,
            delay_between=3.0,
        )

        # Fall back to HTML scraping for anything the browser fetch missed
        html_needed = [url for url in WALMART_PRODUCTS
                       if _item_id(url) not in raw_results
                       and time.time() >= self._url_blocked.get(_item_id(url), 0)]

        html_results: dict[str, dict] = {}
        if html_needed:
            session = make_session("chrome120")
            try:
                for url in html_needed:
                    item_id = _item_id(url)
                    product = await self._fetch_html(url, item_id, session)
                    if product:
                        html_results[item_id] = product
                    await asyncio.sleep(2.0)
            finally:
                await session.close()

        all_results = {**raw_results, **html_results}

        for url in WALMART_PRODUCTS:
            item_id = _item_id(url)
            raw = all_results.get(item_id)
            if not raw:
                continue
            # raw is the full __NEXT_DATA__ blob — extract the product node
            product = _product_from_next_data(raw)
            if not product:
                continue
            await self._process_product(item_id, url, product, prices, stock, notify)

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)
        log.info("[Walmart] Cycle complete — %d/%d fetched",
                 len(all_results), len(WALMART_PRODUCTS))

    async def _fetch_html(self, url: str, item_id: str, session) -> dict | None:
        ua      = random_ua()
        headers = base_headers(ua, referer="https://www.walmart.com/")
        try:
            resp = await session.get(url, headers=headers, timeout=20, allow_redirects=True)
        except Exception as exc:
            log.debug("[Walmart] HTML request error %s: %s", item_id, exc)
            self._url_blocked[item_id] = time.time() + (BOT_BACKOFF // 2)
            return None

        if resp.status_code in BLOCK_STATUSES:
            log.warning("[Walmart] HTML blocked (%d) %s — backoff %ds",
                        resp.status_code, item_id, BOT_BACKOFF)
            self._url_blocked[item_id] = time.time() + BOT_BACKOFF
            return None
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        if any(t in (soup.title.string or "").lower() for t in BLOCK_TITLES):
            self._url_blocked[item_id] = time.time() + BOT_BACKOFF
            return None
        return _extract_next_data(soup)

    async def _process_product(self, item_id: str, url: str, product: dict,
                                prices: dict, stock: dict, notify: dict) -> None:
        name      = product.get("name", "Unknown Product")[:200]
        price     = product.get("price")
        was_price = product.get("wasPrice") or product.get("listPrice")
        in_stock  = product.get("availabilityStatus", "").upper() in ("IN_STOCK", "AVAILABLE")
        image     = (product.get("image") or {}).get("url", "") \
                    if isinstance(product.get("image"), dict) else ""

        if price is None:
            return

        price_str = f"${price:.2f}"
        was_str   = f"${was_price:.2f}" if was_price else "N/A"

        log.debug("[Walmart] %s | %s | was=%s | in_stock=%s",
                  name[:40], price_str, was_str, in_stock)

        prev_in_stock = stock.get(item_id, {}).get("in_stock", True)
        prev_oos_cnt  = stock.get(item_id, {}).get("oos_count", 0)
        if in_stock and not prev_in_stock and prev_oos_cnt >= 1:
            log.info("[Walmart] RESTOCK: %s", name)
            await send_restock_alert(
                WALMART_WEBHOOK_URL, store="walmart",
                name=name, url=url, price=price_str, image=image,
                extra_fields=[{"name": "🔑 Item ID", "value": item_id, "inline": True}],
            )

        stock[item_id] = {
            "in_stock":  in_stock,
            "oos_count": 0 if in_stock else prev_oos_cnt + 1,
        }

        compare  = was_price if was_price and was_price > price else prices.get(item_id, price)
        discount = (compare - price) / compare if compare > 0 else 0.0

        cooldown_key = f"deal_{item_id}"
        on_cool = (time.time() - notify.get(cooldown_key, 0)) < DEAL_COOLDOWN

        if discount >= DEAL_THRESHOLD and not on_cool:
            pct_str = f"{discount * 100:.0f}% off"
            log.info("[Walmart] DEAL: %s | %s | %s", name, price_str, pct_str)
            await send_deal_alert(
                WALMART_WEBHOOK_URL, store="walmart",
                name=name, url=url,
                price=price_str, original_price=was_str,
                discount_pct=pct_str, image=image,
                extra_fields=[{"name": "🔑 Item ID", "value": item_id, "inline": True}],
            )
            notify[cooldown_key] = time.time()

        prices[item_id] = price


def _product_from_next_data(raw: dict) -> dict | None:
    """Extract the product node from a parsed __NEXT_DATA__ JSON object."""
    pdp = (
        raw.get("props", {}).get("pageProps", {}).get("initialData", {})
           .get("data", {}).get("product", {})
    )
    if pdp and pdp.get("name"):
        return pdp
    return _deep_find_product(raw)


def _extract_next_data(soup: BeautifulSoup) -> dict | None:
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        raw = json.loads(tag.string or "")
        pdp = (
            raw.get("props", {}).get("pageProps", {}).get("initialData", {})
               .get("data", {}).get("product", {})
        )
        return pdp or _deep_find_product(raw)
    except (json.JSONDecodeError, AttributeError):
        return None


def _deep_find_product(obj, depth: int = 0) -> dict | None:
    if depth > 10:
        return None
    if isinstance(obj, dict):
        if "name" in obj and "price" in obj:
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