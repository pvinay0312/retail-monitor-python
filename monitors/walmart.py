"""
Walmart monitor — scrapes product pages and extracts pricing from __NEXT_DATA__.

Anti-bot: curl_cffi Chrome impersonation; 1-hour backoff on 429/503/412/521.
"""
import asyncio
import json
import logging
import random
import re
import time

from bs4 import BeautifulSoup

from config.products import WALMART_PRODUCTS
from config.settings import WALMART_WEBHOOK_URL, WALMART_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_THRESHOLD = 0.15   # 15% off
DEAL_COOLDOWN  = 3600
BOT_BACKOFF    = 1200   # 20 min per-URL backoff (was 1hr — too long, miss restocks)

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
        # Per-URL backoff dict: item_id → unblock_timestamp
        # Blocked URLs are skipped individually so the rest still run
        self._url_blocked: dict[str, float] = {}

    async def check(self) -> None:
        prices = await load(_PRICES)
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        # Rotate chrome version each cycle to vary TLS fingerprint
        impersonate = random.choice(["chrome110", "chrome120"])
        session = make_session(impersonate)
        try:
            for url in WALMART_PRODUCTS:
                item_id = _item_id(url)
                if time.time() < self._url_blocked.get(item_id, 0):
                    log.debug("[Walmart] Skipping %s (backoff)", item_id)
                    continue
                await self._check_product(url, session, prices, stock, notify)
                # Random delay 3–7s between products — mimics human browsing pace
                await asyncio.sleep(random.uniform(3.0, 7.0))
        finally:
            await session.close()

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)

    async def _check_product(self, url, session, prices, stock, notify) -> None:
        item_id = _item_id(url)
        ua      = random_ua()
        headers = base_headers(ua, referer="https://www.walmart.com/")

        try:
            resp = await session.get(url, headers=headers, timeout=20, allow_redirects=True)
        except Exception as exc:
            log.debug("[Walmart] Request error %s: %s", item_id, exc)
            self._url_blocked[item_id] = time.time() + (BOT_BACKOFF // 2)
            return

        if resp.status_code in BLOCK_STATUSES:
            log.warning("[Walmart] Blocked (HTTP %d) %s — backoff %ds", resp.status_code, item_id, BOT_BACKOFF)
            self._url_blocked[item_id] = time.time() + BOT_BACKOFF
            return

        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "lxml")
        page_title = (soup.title.string or "").lower()
        if any(t in page_title for t in BLOCK_TITLES):
            log.warning("[Walmart] Bot block detected %s — backoff %ds", item_id, BOT_BACKOFF)
            self._url_blocked[item_id] = time.time() + BOT_BACKOFF
            return

        product = _extract_next_data(soup)
        if not product:
            log.debug("[Walmart] No __NEXT_DATA__ for %s", item_id)
            return

        name      = product.get("name", "Unknown Product")[:200]
        price     = product.get("price")
        was_price = product.get("wasPrice") or product.get("listPrice")
        in_stock  = product.get("availabilityStatus", "").upper() in ("IN_STOCK", "AVAILABLE")
        image     = product.get("image", {}).get("url", "") if isinstance(product.get("image"), dict) else ""

        if price is None:
            return

        price_str  = f"${price:.2f}"
        was_str    = f"${was_price:.2f}" if was_price else "N/A"

        # ── Restock ───────────────────────────────────────────────────────────
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

        # ── Deal detection ────────────────────────────────────────────────────
        compare = was_price if was_price and was_price > price else prices.get(item_id, price)
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


def _extract_next_data(soup: BeautifulSoup) -> dict | None:
    """Parse product info from Walmart's __NEXT_DATA__ script tag."""
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        raw = json.loads(tag.string or "")
        # Path varies between page types; try both
        pdp = (
            raw.get("props", {}).get("pageProps", {}).get("initialData", {})
               .get("data", {}).get("product", {})
        )
        if pdp:
            return pdp
        # Fallback: search for productType == "REGULAR"
        return _deep_find_product(raw)
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
