"""
Best Buy monitor — uses Best Buy's internal priceBlocks API (same endpoint
their own React frontend calls). Alerts on ≥10% price drops and restocks.

Anti-bot: curl_cffi Chrome impersonation + 30-min backoff on 429.
"""
import asyncio
import logging
import random
import re
import time

from config.products import BESTBUY_PRODUCTS
from config.settings import BESTBUY_WEBHOOK_URL, BESTBUY_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_THRESHOLD  = 0.10   # 10% off
DEAL_COOLDOWN   = 6 * 3600
BOT_BACKOFF     = 600    # 10 min — priceBlocks API is lenient, short backoff is fine

_PRICES = "bb_prices.json"
_STOCK  = "bb_stock.json"
_NOTIFY = "bb_notify.json"


def _sku(url: str) -> str:
    m = re.search(r"/(\d+)\.p", url)
    return m.group(1) if m else url


class BestBuyMonitor(BaseMonitor):
    name = "BestBuy"
    interval = BESTBUY_INTERVAL

    def __init__(self):
        self._blocked_until: float = 0.0

    async def check(self) -> None:
        if time.time() < self._blocked_until:
            log.warning("[BestBuy] Bot-block backoff — %ds remaining",
                        int(self._blocked_until - time.time()))
            return

        skus = [_sku(u) for u in BESTBUY_PRODUCTS]
        url_map = {_sku(u): u for u in BESTBUY_PRODUCTS}

        prices = await load(_PRICES)
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        deals_found    = 0
        restocks_found = 0
        checked        = 0

        # Best Buy priceBlocks API accepts up to ~50 SKUs at once
        batch_size = 40
        session = make_session("chrome120")
        try:
            for i in range(0, len(skus), batch_size):
                batch = skus[i:i + batch_size]
                d, r, c = await self._check_batch(batch, url_map, session, prices, stock, notify)
                deals_found    += d
                restocks_found += r
                checked        += c
                if i + batch_size < len(skus):
                    await asyncio.sleep(random.uniform(1.5, 3.5))
        finally:
            await session.close()

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)
        log.info("[BestBuy] Cycle complete — %d/%d SKUs active | %d deals | %d restocks",
                 checked, len(skus), deals_found, restocks_found)

    async def _check_batch(self, skus, url_map, session, prices, stock, notify) -> tuple[int, int, int]:
        """Returns (deals_found, restocks_found, items_checked)."""
        api_url = "https://www.bestbuy.com/api/3.0/priceBlocks?skus=" + ",".join(skus)
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.bestbuy.com/")
        # API call — override Sec-Fetch headers to match XHR from within the site
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers.pop("Upgrade-Insecure-Requests", None)

        try:
            resp = await session.get(api_url, headers=headers, timeout=15)
        except Exception as exc:
            log.debug("[BestBuy] Request error: %s", exc)
            self._blocked_until = time.time() + BOT_BACKOFF
            return 0, 0, 0

        if resp.status_code == 429:
            log.warning("[BestBuy] Rate-limited — backing off %ds", BOT_BACKOFF)
            self._blocked_until = time.time() + BOT_BACKOFF
            return 0, 0, 0

        if resp.status_code != 200:
            log.warning("[BestBuy] HTTP %d for batch — API may be blocked or down", resp.status_code)
            return 0, 0, 0

        try:
            data = resp.json()
        except Exception:
            return 0, 0, 0

        deals_found = restocks_found = checked = 0

        for item in data:
            sku = str(item.get("sku", ""))
            if not sku:
                continue
            product_url = url_map.get(sku, f"https://www.bestbuy.com/site/p/{sku}.p")
            name        = item.get("names", {}).get("title", "Unknown Product")
            current     = item.get("priceBlock", {}).get("customerPrice", 0.0)
            reg_price   = item.get("priceBlock", {}).get("regularPrice", 0.0)
            purchasable = item.get("purchasable", False)

            if not current:
                continue

            checked  += 1
            in_stock  = bool(purchasable)
            price_str = f"${current:.2f}"
            reg_str   = f"${reg_price:.2f}" if reg_price else "N/A"

            log.debug("[BestBuy] %s | %s | reg=%s | in_stock=%s",
                      name[:40], price_str, reg_str, in_stock)

            # ── Restock ───────────────────────────────────────────────────────
            prev_in_stock = stock.get(sku, {}).get("in_stock", True)
            prev_oos_cnt  = stock.get(sku, {}).get("oos_count", 0)
            if in_stock and not prev_in_stock and prev_oos_cnt >= 1:
                log.info("[BestBuy] RESTOCK: %s", name)
                await send_restock_alert(
                    BESTBUY_WEBHOOK_URL, store="bestbuy",
                    name=name, url=product_url, price=price_str,
                    extra_fields=[{"name": "🔑 SKU", "value": sku, "inline": True}],
                )
                notify[f"restock_{sku}"] = time.time()
                restocks_found += 1

            stock[sku] = {
                "in_stock":  in_stock,
                "oos_count": 0 if in_stock else prev_oos_cnt + 1,
            }

            # ── Deal detection ────────────────────────────────────────────────
            compare = reg_price if reg_price > current else prices.get(sku, current)
            if compare > 0:
                discount = (compare - current) / compare
            else:
                discount = 0.0

            cooldown_key = f"deal_{sku}"
            on_cool = (time.time() - notify.get(cooldown_key, 0)) < DEAL_COOLDOWN

            if discount >= DEAL_THRESHOLD and not on_cool:
                pct_str = f"{discount * 100:.0f}% off"
                log.info("[BestBuy] DEAL: %s | %s | %s", name, price_str, pct_str)
                await send_deal_alert(
                    BESTBUY_WEBHOOK_URL, store="bestbuy",
                    name=name, url=product_url,
                    price=price_str, original_price=reg_str,
                    discount_pct=pct_str,
                    extra_fields=[{"name": "🔑 SKU", "value": sku, "inline": True}],
                )
                notify[cooldown_key] = time.time()
                deals_found += 1

            prices[sku] = current

        return deals_found, restocks_found, checked
