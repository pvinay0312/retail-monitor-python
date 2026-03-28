"""
Target monitor — uses Target's Redsky API for accurate pricing.
Falls back to JSON-LD / __NEXT_DATA__ HTML scraping if the API fails.

Alerts on ≥10% price drops and restocks.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import time

from bs4 import BeautifulSoup

from config.products import TARGET_PRODUCTS
from config.settings import TARGET_WEBHOOK_URL, TARGET_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_THRESHOLD = 0.10   # 10% off
DEAL_COOLDOWN  = 6 * 3600
BOT_BACKOFF    = 2700   # 45 min

REDSKY_KEY      = "9f36aeafbe60771e321a7cc95a78140772ab3e96"
REDSKY_STORE_ID = "1108"

_PRICES = "target_prices.json"
_STOCK  = "target_stock.json"
_NOTIFY = "target_notify.json"


def _tcin(url: str) -> str:
    m = re.search(r"/A-(\d+)", url)
    return m.group(1) if m else ""


class TargetMonitor(BaseMonitor):
    name = "Target"
    interval = TARGET_INTERVAL

    def __init__(self):
        self._blocked_until: float = 0.0

    async def check(self) -> None:
        if time.time() < self._blocked_until:
            log.warning("[Target] Bot-block backoff — %ds remaining",
                        int(self._blocked_until - time.time()))
            return

        prices = await load(_PRICES)
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        checked = deals_found = restocks_found = 0

        session = make_session("chrome120")
        try:
            for url in TARGET_PRODUCTS:
                result = await self._check_product(url, session, prices, stock, notify)
                if result:
                    c, d, r = result
                    checked        += c
                    deals_found    += d
                    restocks_found += r
                await asyncio.sleep(2)
        finally:
            await session.close()

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)
        log.info("[Target] Cycle complete — %d/%d TCINs fetched | %d deals | %d restocks",
                 checked, len(TARGET_PRODUCTS), deals_found, restocks_found)

    async def _check_product(self, url, session, prices, stock, notify) -> tuple[int, int, int] | None:
        """Returns (checked, deals_found, restocks_found) or None on parse failure."""
        tcin = _tcin(url)
        if not tcin:
            return None

        product = await self._fetch_redsky(tcin, session)
        if not product:
            product = await self._fetch_html(url, session)
        if not product:
            log.debug("[Target] No data for TCIN %s — Redsky and HTML both failed", tcin)
            return None

        name      = product.get("name", "Unknown")[:200]
        price     = product.get("price")
        was_price = product.get("was_price")
        in_stock  = product.get("in_stock", False)
        image     = product.get("image", "")

        if price is None:
            return None

        price_str = f"${price:.2f}"
        was_str   = f"${was_price:.2f}" if was_price else "N/A"

        log.debug("[Target] %s | %s | was=%s | in_stock=%s",
                  name[:40], price_str, was_str, in_stock)

        deals_found = restocks_found = 0

        # ── Restock ───────────────────────────────────────────────────────────
        prev_in_stock = stock.get(tcin, {}).get("in_stock", True)
        prev_oos_cnt  = stock.get(tcin, {}).get("oos_count", 0)
        if in_stock and not prev_in_stock and prev_oos_cnt >= 1:
            log.info("[Target] RESTOCK: %s", name)
            await send_restock_alert(
                TARGET_WEBHOOK_URL, store="target",
                name=name, url=url, price=price_str, image=image,
                extra_fields=[{"name": "🔑 TCIN", "value": tcin, "inline": True}],
            )
            restocks_found = 1

        stock[tcin] = {
            "in_stock":  in_stock,
            "oos_count": 0 if in_stock else prev_oos_cnt + 1,
        }

        # ── Deal detection ────────────────────────────────────────────────────
        compare  = was_price if (was_price and was_price > price) else prices.get(tcin, price)
        discount = (compare - price) / compare if compare > 0 else 0.0

        cooldown_key = f"deal_{tcin}"
        on_cool = (time.time() - notify.get(cooldown_key, 0)) < DEAL_COOLDOWN

        if discount >= DEAL_THRESHOLD and not on_cool:
            pct_str = f"{discount * 100:.0f}% off"
            log.info("[Target] DEAL: %s | %s | %s", name, price_str, pct_str)
            await send_deal_alert(
                TARGET_WEBHOOK_URL, store="target",
                name=name, url=url,
                price=price_str, original_price=was_str,
                discount_pct=pct_str, image=image,
                extra_fields=[{"name": "🔑 TCIN", "value": tcin, "inline": True}],
            )
            notify[cooldown_key] = time.time()
            deals_found = 1

        prices[tcin] = price
        return 1, deals_found, restocks_found

    # ── Data sources ──────────────────────────────────────────────────────────

    async def _fetch_redsky(self, tcin: str, session) -> dict | None:
        api_url = (
            f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
            f"?key={REDSKY_KEY}&tcin={tcin}&store_id={REDSKY_STORE_ID}&pricing_store_id={REDSKY_STORE_ID}"
        )
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.target.com/")
        headers["Accept"] = "application/json"
        try:
            resp = await session.get(api_url, headers=headers, timeout=15)
            if resp.status_code == 429:
                self._blocked_until = time.time() + BOT_BACKOFF
                return None
            if resp.status_code in (401, 403):
                log.warning("[Target] Redsky API key rejected (HTTP %d) for TCIN %s — key may be expired",
                            resp.status_code, tcin)
                return None
            if resp.status_code != 200:
                log.debug("[Target] Redsky HTTP %d for TCIN %s", resp.status_code, tcin)
                return None
            data = resp.json()
            p = data.get("data", {}).get("product", {})
            pricing = p.get("price", {})
            inventory = p.get("inventory", {})
            desc_node = p.get("item", {}).get("product_description", {})
            name = desc_node.get("title", "")
            price = pricing.get("current_retail")
            was_price = pricing.get("reg_retail") or pricing.get("comparable_price")
            in_stock = inventory.get("availability_status", "") in ("IN_STOCK", "AVAILABLE")
            image_url = ""
            imgs = p.get("item", {}).get("enrichment", {}).get("images", {})
            if imgs:
                image_url = imgs.get("base_url", "") + (imgs.get("primary_image_url") or "")
            return {"name": name, "price": price, "was_price": was_price,
                    "in_stock": in_stock, "image": image_url}
        except Exception as exc:
            log.debug("[Target] Redsky error for %s: %s", tcin, exc)
            return None

    async def _fetch_html(self, url: str, session) -> dict | None:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.target.com/")
        try:
            resp = await session.get(url, headers=headers, timeout=20, allow_redirects=True)
            if resp.status_code in (429, 503):
                self._blocked_until = time.time() + BOT_BACKOFF
                return None
            if resp.status_code == 404:
                tcin = _tcin(url)
                log.debug("[Target] 404 for TCIN %s — product no longer exists", tcin)
                return None
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "lxml")
            return _parse_target_html(soup)
        except Exception as exc:
            exc_str = str(exc)
            # Target injects JS into some pages that raises "Assignment to constant
            # variable" at runtime when parsed by BeautifulSoup / lxml.  This is a
            # known non-actionable error for certain TCINs — log at debug level and
            # skip rather than counting as a scrape error.
            if "Assignment to constant variable" in exc_str or "assignment to constant" in exc_str.lower():
                tcin = _tcin(url)
                log.debug("[Target] JS constant-assignment error for TCIN %s — skipping", tcin)
                return None
            log.debug("[Target] HTML scrape error: %s", exc)
            return None


def _parse_target_html(soup: BeautifulSoup) -> dict | None:
    # Try JSON-LD structured data first
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(tag.string or "")
            if isinstance(obj, list):
                obj = next((x for x in obj if x.get("@type") == "Product"), {})
            if obj.get("@type") == "Product":
                offers = obj.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price")
                name  = obj.get("name", "")
                in_stock = "InStock" in offers.get("availability", "")
                image = obj.get("image", "")
                if isinstance(image, list):
                    image = image[0] if image else ""
                if price:
                    return {"name": name, "price": float(price),
                            "was_price": None, "in_stock": in_stock, "image": image}
        except Exception:
            pass

    # Fallback: __NEXT_DATA__
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag:
        try:
            raw = json.loads(tag.string or "")
            product = _deep_find(raw, "name", "price")
            if product:
                return {
                    "name":      product.get("name", ""),
                    "price":     product.get("price"),
                    "was_price": product.get("wasPrice"),
                    "in_stock":  product.get("availabilityStatus", "") == "IN_STOCK",
                    "image":     "",
                }
        except Exception:
            pass
    return None


def _deep_find(obj, *required_keys, depth: int = 0) -> dict | None:
    if depth > 12:
        return None
    if isinstance(obj, dict):
        if all(k in obj for k in required_keys):
            return obj
        for v in obj.values():
            r = _deep_find(v, *required_keys, depth=depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for item in obj:
            r = _deep_find(item, *required_keys, depth=depth + 1)
            if r:
                return r
    return None
