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
DEAL_COOLDOWN    = 6 * 3600   # 6 hours — prevents re-pinging same deal each cycle
COUPON_COOLDOWN  = 4 * 3600   # 4 hours
CAPTCHA_BACKOFF  = 7200        # 2 hours if CAPTCHA detected

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

        name                    = _extract_name(soup)
        price                   = _extract_price(soup)
        was_price               = _extract_was_price(soup)
        coupon_text, is_promo   = _extract_coupon(soup)
        in_stock                = _is_in_stock(soup)
        image                   = _extract_image(soup)

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

        # Skip price/deal detection when the item can't be purchased.
        # When unavailable, Amazon still renders the page with accessory prices
        # inside the same container — scraping those causes false deal alerts.
        # Also clear any stale notify entries so the next genuine restock+deal
        # fires cleanly rather than being blocked by an old cooldown.
        if not in_stock:
            log.debug("[Amazon] %s out of stock — skipping deal check", asin)
            notify.pop(f"notified_price_{asin}", None)
            notify.pop(f"deal_{asin}", None)
            notify.pop(f"coupon_{asin}", None)
            return

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

        # Sanity check: was_price must be strictly higher than current price and
        # no more than 10× it (avoids using an unrelated page price as "original")
        if was_price and not (price < was_price <= price * 10):
            was_price = None

        discount_pct = 0.0
        if was_price and was_price > 0:
            discount_pct = (was_price - effective_price) / was_price
        elif prev_price and prev_price > 0 and prev_price > price:
            discount_pct = (prev_price - effective_price) / prev_price

        is_freebie  = effective_price <= 0.01
        has_coupon  = coupon_amount > 0
        big_drop    = discount_pct >= DEAL_THRESHOLD

        cooldown_key   = f"deal_{asin}"
        price_key      = f"notified_price_{asin}"
        coupon_key     = f"coupon_{asin}"
        on_cool        = (time.time() - notify.get(cooldown_key, 0)) < DEAL_COOLDOWN
        on_coupon_cool = (time.time() - notify.get(coupon_key, 0)) < COUPON_COOLDOWN

        # last_notified_price = the effective price when we last sent an alert.
        # We only re-alert if price has dropped meaningfully below that anchor.
        last_notified_price = notify.get(price_key)   # None = never alerted

        # "Price improved" = dropped ≥5% AND ≥$5 below last notified price.
        # Using a dual threshold avoids re-alerting on $0.10 price ticks.
        if last_notified_price:
            price_improved = (effective_price < last_notified_price * 0.95
                              and effective_price < last_notified_price - 5.0)
        else:
            price_improved = True   # never alerted → always eligible

        # Reset dedup tracking only when price clearly returned to full price.
        # Anchor on last_notified_price (NOT prev_price — prev_price is updated
        # every cycle so prev_price ≈ current price, making the reset fire constantly).
        if last_notified_price and not (is_freebie or big_drop or has_coupon):
            if effective_price > last_notified_price * 1.15:
                # Price rose 15%+ above last notified — deal is over, reset
                notify.pop(price_key,    None)
                notify.pop(cooldown_key, None)
                notify.pop(coupon_key,   None)

        if is_freebie or (big_drop and (not last_notified_price or price_improved) and not on_cool) or (has_coupon and (not last_notified_price or price_improved) and not on_coupon_cool):
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
                is_promo_code=is_promo,
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


def _price_container(soup: BeautifulSoup):
    """Return the main product price section, scoped to avoid sidebar/comparison prices."""
    for div_id in (
        "corePriceDisplay_desktop_feature_div",
        "apex_desktop",
        "corePrice_desktop",
        "price_inside_buybox",
        "centerCol",          # wider fallback — still excludes right rail / footer
    ):
        tag = soup.find(id=div_id)
        if tag:
            return tag
    return None


def _parse_price_text(text: str) -> float | None:
    text = text.replace(",", "").replace("$", "").strip().rstrip(".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_price(soup: BeautifulSoup) -> float | None:
    container = _price_container(soup)

    # 1. a-offscreen spans hold the exact accessible price string ("$649.99")
    #    and are always inside the correct price block
    if container:
        for span in container.find_all("span", class_="a-offscreen"):
            v = _parse_price_text(span.get_text(strip=True))
            if v and v > 0:
                return v

    # 2. Legacy price block IDs (older Amazon layout)
    for pid in ("priceblock_ourprice", "priceblock_dealprice", "priceblock_saleprice"):
        tag = soup.find("span", id=pid)
        if tag:
            v = _parse_price_text(tag.get_text(strip=True))
            if v and v > 0:
                return v

    # 3. a-price-whole inside the container (no broad-page fallback)
    if container:
        whole = container.find("span", class_="a-price-whole")
        if whole:
            text = whole.get_text(strip=True)
            frac = whole.find_next_sibling("span", class_="a-price-fraction")
            if frac:
                text = text.rstrip(".") + "." + frac.get_text(strip=True)
            v = _parse_price_text(text)
            if v and v > 0:
                return v

    # No broad regex fallback — avoids picking up sponsored / sidebar prices
    return None


def _extract_was_price(soup: BeautifulSoup) -> float | None:
    container = _price_container(soup)
    if not container:
        return None

    # "Was" price appears as a struck-through a-text-price INSIDE the price block
    for span in container.find_all("span", class_="a-text-price"):
        text = span.get_text(strip=True)
        m = re.search(r"[\d,.]+", text)
        if m:
            v = _parse_price_text(m.group(0))
            if v and v > 0:
                return v

    # data-a-strike attribute (newer layout)
    for span in container.find_all("span", attrs={"data-a-strike": "true"}):
        m = re.search(r"[\d,.]+", span.get_text(strip=True))
        if m:
            v = _parse_price_text(m.group(0))
            if v and v > 0:
                return v

    return None


def _extract_coupon(soup: BeautifulSoup) -> tuple[str, bool]:
    """
    Return (coupon_text, is_promo_code).
    is_promo_code=True  → short alphanumeric code typed at checkout (e.g. DZTZGW9X)
    is_promo_code=False → clip/checkbox coupon on the product page
    """
    # Promo code pre-filled in input box
    for input_id in ("promotionInput", "gcpromoinput"):
        tag = soup.find("input", {"id": input_id})
        if tag:
            val = tag.get("value", "").strip()
            if val and re.match(r"^[A-Z0-9]{4,20}$", val.upper()):
                return val.upper(), True

    # Promo code shown as plain text near "Enter code" labels
    for label in soup.find_all(string=re.compile(r"promo(?:tion)? ?code", re.I)):
        parent = label.parent
        if parent:
            code = re.search(r"\b([A-Z0-9]{5,20})\b", parent.get_text())
            if code:
                return code.group(1), True

    # Clip coupon badge (percentage or dollar)
    for cls in ["couponBadge", "s-coupon-clipped", "coupon-tip-content"]:
        tag = soup.find(class_=cls)
        if tag:
            return tag.get_text(strip=True), False

    # "Apply X% coupon" checkbox
    m = soup.find(string=re.compile(r"Apply\s+[\d$]+%?\s+coupon", re.I))
    if m:
        return str(m).strip(), False

    return "", False


def _is_in_stock(soup: BeautifulSoup) -> bool:
    """
    Conservative stock check — returns False unless we see an explicit
    in-stock signal. Amazon serves static HTML (no JS), so many divs are
    empty or dynamic. Two key static OOS signals:
      • div#outOfStock   — "Currently unavailable" box, always static
      • div#availability — may be empty (dynamic); if non-empty, trust it
    """
    _OOS_PHRASES = (
        "currently unavailable",
        "this item is unavailable",
        "not available",
        "out of stock",
        "temporarily out of stock",
        "see all buying options",        # no direct stock, 3P sellers only
        "available from these sellers",  # same
        "we don't know when or if",
    )
    _IN_PHRASES = (
        "in stock",
        "in-stock",
        "ships from",
        "available to ship",
        "usually ships",
        "get it as soon as",
    )

    # 1. div#outOfStock is the most reliable static OOS signal on Amazon.
    #    When present and non-empty, the item is definitively unavailable.
    oos_box = soup.find("div", id="outOfStock")
    if oos_box and oos_box.get_text(strip=True):
        log.debug("[Amazon] _is_in_stock: outOfStock div present → OOS")
        return False

    # 2. div#availability may be populated in static HTML on some page types.
    #    If it has content, trust it; if empty (dynamic), skip it entirely.
    avail = soup.find("div", id="availability")
    if avail:
        text = avail.get_text(" ", strip=True).lower()
        if text:
            if any(p in text for p in _OOS_PHRASES):
                log.debug("[Amazon] _is_in_stock: #availability OOS phrase → OOS")
                return False
            if any(p in text for p in _IN_PHRASES):
                log.debug("[Amazon] _is_in_stock: #availability IN phrase → in stock")
                return True
            # Non-empty but unrecognised text (e.g. "Select a configuration")
            # → conservatively treat as OOS
            log.debug("[Amazon] _is_in_stock: #availability ambiguous '%s' → OOS", text[:60])
            return False
        # Empty div (content loads via JS) — fall through to button check

    # 3. Add to Cart button in the main buybox is the clearest positive signal.
    #    Only trust it when it lives inside a recognised buybox container —
    #    NOT a page-wide search (3P seller sections also have this button).
    for buybox_id in ("buyBoxAccordion", "desktop_buybox", "newAccordionRow",
                      "addToCart_feature_div", "add-to-cart-button"):
        container = soup.find(id=buybox_id)
        if container:
            # If the buybox itself mentions OOS, stop immediately
            bt = container.get_text(" ", strip=True).lower()
            if any(p in bt for p in _OOS_PHRASES):
                log.debug("[Amazon] _is_in_stock: buybox OOS phrase → OOS")
                return False
            if container.find("input", id="add-to-cart-button"):
                log.debug("[Amazon] _is_in_stock: add-to-cart in buybox → in stock")
                return True
            break   # found the buybox but no cart button — OOS

    # 4. No definitive signal found → conservative default: treat as OOS
    log.debug("[Amazon] _is_in_stock: no signal found → OOS (conservative default)")
    return False


def _extract_image(soup: BeautifulSoup) -> str:
    tag = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
    return tag.get("src", "") if tag else ""
