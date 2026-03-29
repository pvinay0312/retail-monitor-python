"""
Amazon monitor — detects coupon codes, price drops (≥15% off), freebies, and restocks.

Anti-bot strategy:
  • curl_cffi with Chrome TLS impersonation (JA3/JA4 fingerprint matches Chrome)
  • Rotating user-agents
  • 2-hour backoff on CAPTCHA detection to prevent IP banning
  • Realistic sec-ch-ua and Sec-Fetch-* headers
"""
from __future__ import annotations
import asyncio
import logging
import re
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from config.products import AMAZON_PRODUCTS
from config.settings import AMAZON_WEBHOOK_URL, AMAZON_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.affiliate import make_affiliate_url
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.storage import load, save, is_on_cooldown, mark_notified

log = logging.getLogger(__name__)

DEAL_THRESHOLD   = 0.15   # 15% off triggers a deal alert
COUPON_THRESHOLD = 0.01   # any coupon triggers an alert
DEAL_COOLDOWN    = 3600   # 1 hour
COUPON_COOLDOWN  = 1800   # 30 min
CAPTCHA_BACKOFF  = 7200   # 2 hours if CAPTCHA detected

CAPTCHA_TITLES   = {"robot check", "captcha", "sorry!", "we're sorry"}

# Filenames for persisted state
_PRICES  = "amazon_prices.json"
_STOCK   = "amazon_stock.json"
_NOTIFY  = "amazon_notify.json"


def _asin(url: str) -> str:
    """Extract ASIN from an Amazon product URL."""
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    return m.group(1) if m else url


class AmazonMonitor(BaseMonitor):
    name = "Amazon"
    interval = AMAZON_INTERVAL

    def __init__(self):
        self._captcha_until: float = 0.0

    async def check(self) -> None:
        if time.time() < self._captcha_until:
            remaining = int(self._captcha_until - time.time())
            log.warning("[Amazon] CAPTCHA backoff active — %ds remaining", remaining)
            return

        prices = await load(_PRICES)
        stock  = await load(_STOCK)
        notify = await load(_NOTIFY)

        session = make_session("chrome120")
        try:
            for url in AMAZON_PRODUCTS:
                await self._check_product(url, session, prices, stock, notify)
                await asyncio.sleep(1.5)   # small delay between requests
        finally:
            await session.close()

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)

    async def _check_product(self, url: str, session, prices: dict, stock: dict, notify: dict) -> None:
        asin = _asin(url)
        ua   = random_ua()
        headers = base_headers(ua, referer="https://www.amazon.com/")
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

        try:
            resp = await session.get(url, headers=headers, timeout=20, allow_redirects=True)
        except Exception as exc:
            log.debug("[Amazon] Request error for %s: %s", asin, exc)
            return

        if resp.status_code != 200:
            log.debug("[Amazon] %s → HTTP %d", asin, resp.status_code)
            return

        soup = BeautifulSoup(resp.text, "lxml")

        # CAPTCHA detection
        page_title = (soup.title.string or "").lower() if soup.title else ""
        if any(t in page_title for t in CAPTCHA_TITLES):
            log.warning("[Amazon] CAPTCHA detected — backing off %ds", CAPTCHA_BACKOFF)
            self._captcha_until = time.time() + CAPTCHA_BACKOFF
            return

        name         = _extract_name(soup)
        price        = _extract_price(soup)
        was_price    = _extract_was_price(soup)
        coupon_text  = _extract_coupon(soup)
        in_stock     = _is_in_stock(soup)
        image        = _extract_image(soup)

        if not name or price is None:
            log.debug("[Amazon] Could not parse %s — skipping", asin)
            return

        price_str = f"${price:.2f}"
        was_str   = f"${was_price:.2f}" if was_price else "N/A"

        # ── Restock detection ─────────────────────────────────────────────────
        prev_oos_count = stock.get(asin, {}).get("oos_count", 0)
        was_in_stock   = stock.get(asin, {}).get("in_stock", True)

        if in_stock and not was_in_stock and prev_oos_count >= 2:
            log.info("[Amazon] RESTOCK: %s", name)
            await send_restock_alert(
                AMAZON_WEBHOOK_URL,
                store="amazon",
                name=name,
                url=make_affiliate_url(url),
                price=price_str,
                image=image,
                extra_fields=[{"name": "🔑 ASIN", "value": asin, "inline": True}],
            )
            notify[f"restock_{asin}"] = time.time()

        stock[asin] = {
            "in_stock":  in_stock,
            "oos_count": 0 if in_stock else prev_oos_count + 1,
        }

        # ── Price-drop / coupon detection ─────────────────────────────────────
        prev_price = prices.get(asin)
        prices[asin] = price  # always update

        # Effective price after coupon
        effective_price = price
        coupon_amount   = 0.0
        if coupon_text:
            m = re.search(r"\$?([\d.]+)", coupon_text)
            if m:
                coupon_amount   = float(m.group(1))
                effective_price = max(0.0, price - coupon_amount)
            else:
                m_pct = re.search(r"(\d+)%", coupon_text)
                if m_pct:
                    coupon_amount   = price * int(m_pct.group(1)) / 100
                    effective_price = price * (1 - int(m_pct.group(1)) / 100)

        discount_pct = 0.0
        if was_price and was_price > 0:
            discount_pct = (was_price - effective_price) / was_price
        elif prev_price and prev_price > 0:
            discount_pct = (prev_price - effective_price) / prev_price

        is_freebie  = effective_price <= 0.01
        has_coupon  = coupon_amount > 0
        big_drop    = discount_pct >= DEAL_THRESHOLD

        cooldown_key  = f"deal_{asin}"
        price_key     = f"notified_price_{asin}"
        coupon_key    = f"coupon_{asin}"
        on_cool       = (time.time() - notify.get(cooldown_key, 0)) < DEAL_COOLDOWN
        on_coupon_cool = (time.time() - notify.get(coupon_key, 0)) < COUPON_COOLDOWN

        # Only re-alert if the effective price dropped below the last notified price
        # (prevents hourly re-pings for items that stay on sale at the same price)
        last_notified_price = notify.get(price_key, float("inf"))
        price_improved = effective_price < last_notified_price - 0.01

        # Reset tracked price when item is no longer on deal so the next sale re-triggers
        if not (is_freebie or big_drop or has_coupon):
            notify.pop(price_key, None)

        if is_freebie or (big_drop and price_improved and not on_cool) or (has_coupon and price_improved and not on_coupon_cool):
            pct_str = f"{discount_pct * 100:.0f}% off" if discount_pct > 0 else ""
            eff_str = f"${effective_price:.2f}" if has_coupon else price_str

            log.info("[Amazon] DEAL: %s | %s | coupon=%s | pct=%.0f%%",
                     name, eff_str, coupon_text or "—", discount_pct * 100)

            await send_deal_alert(
                AMAZON_WEBHOOK_URL,
                store="amazon",
                name=name,
                url=make_affiliate_url(url),
                price=eff_str,
                original_price=was_str,
                discount_pct=pct_str or "N/A",
                coupon=coupon_text or "",
                image=image,
                is_freebie=is_freebie,
                extra_fields=[{"name": "🔑 ASIN", "value": asin, "inline": True}],
            )
            notify[cooldown_key]  = time.time()
            notify[coupon_key]    = time.time()
            if not is_freebie:
                notify[price_key] = effective_price


# ── HTML extraction helpers ───────────────────────────────────────────────────

def _extract_name(soup: BeautifulSoup) -> str:
    tag = soup.find("span", id="productTitle")
    return tag.get_text(strip=True)[:200] if tag else ""


def _extract_price(soup: BeautifulSoup) -> float | None:
    # Try primary price block
    for sel in [
        ("span", {"class": "a-price-whole"}),
        ("span", {"id": "priceblock_ourprice"}),
        ("span", {"id": "priceblock_dealprice"}),
    ]:
        tag = soup.find(*sel)
        if tag:
            text = tag.get_text(strip=True).replace(",", "").replace("$", "")
            # price-whole doesn't include cents; look for fraction sibling
            frac = tag.find_next_sibling("span", class_="a-price-fraction")
            if frac:
                text = text.rstrip(".") + "." + frac.get_text(strip=True)
            try:
                return float(text)
            except ValueError:
                pass
    # Fallback: search for any dollar amount in the page
    m = re.search(r'\$\s*([\d,]+\.\d{2})', soup.get_text())
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_was_price(soup: BeautifulSoup) -> float | None:
    for cls in ["a-text-price", "a-text-strike"]:
        tag = soup.find("span", class_=cls)
        if tag:
            m = re.search(r'[\d,.]+', tag.get_text())
            if m:
                try:
                    return float(m.group(0).replace(",", ""))
                except ValueError:
                    pass
    return None


def _extract_coupon(soup: BeautifulSoup) -> str:
    """Return coupon label text if present, else empty string."""
    for cls in ["couponBadge", "s-coupon-clipped", "coupon-tip-content"]:
        tag = soup.find(class_=cls)
        if tag:
            return tag.get_text(strip=True)
    # Look for "Apply X% coupon" checkbox text
    m = soup.find(string=re.compile(r'Apply\s+\d+%?\s+coupon', re.I))
    return str(m).strip() if m else ""


def _is_in_stock(soup: BeautifulSoup) -> bool:
    avail = soup.find("div", id="availability")
    if avail:
        text = avail.get_text(strip=True).lower()
        return "in stock" in text or "ships" in text
    # If Add to Cart button exists, assume in stock
    return bool(soup.find("input", id="add-to-cart-button"))


def _extract_image(soup: BeautifulSoup) -> str:
    tag = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
    return tag.get("src", "") if tag else ""
