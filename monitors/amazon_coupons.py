"""
Amazon Coupons Hub monitor — scrapes amazon.com/coupons automatically.

Instead of monitoring a fixed product list, this spider crawls Amazon's
public coupon hub which aggregates ALL active clip coupons across every
category. No hardcoded ASINs needed — any new coupon appears here.

Strategy:
  • Loads amazon.com/coupons with curl_cffi Chrome impersonation
  • Parses every coupon card: ASIN, title, coupon value, original price, image
  • Scores each deal using the deal scorer
  • Posts to Discord only if score >= MIN_SCORE_TO_ALERT
  • Deduplicates by ASIN+coupon_value to avoid repeat alerts
"""
from __future__ import annotations
import asyncio
import logging
import re
import time

from bs4 import BeautifulSoup

from config.settings import AMAZON_WEBHOOK_URL, AMAZON_INTERVAL
from monitors.base import BaseMonitor
from utils.affiliate import make_affiliate_url
from utils.anti_bot import make_session, base_headers, random_ua
from utils.deal_scorer import calculate_deal_score, score_label, MIN_SCORE_TO_ALERT
from utils.discord_client import send_deal_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

COUPON_COOLDOWN = 3600   # 1 hour per ASIN+coupon combo
_NOTIFY = "amazon_coupons_notify.json"

# URL fragments (#electronics, #beauty, etc.) are client-side JS filters —
# the server returns identical HTML for all of them. One request is enough.
COUPON_URLS = [
    "https://www.amazon.com/coupons",
]


class AmazonCouponsMonitor(BaseMonitor):
    name = "Amazon Coupons"
    interval = int(AMAZON_INTERVAL * 0.8)   # slightly faster than product monitor

    async def check(self) -> None:
        notify = await load(_NOTIFY)
        session = make_session("chrome120")
        found = 0
        try:
            for url in COUPON_URLS:
                deals = await self._fetch_coupons(session, url)
                for deal in deals:
                    if await self._should_alert(deal, notify):
                        await self._post_alert(deal)
                        key = f"{deal['asin']}_{deal['coupon_raw']}"
                        notify[key] = time.time()
                        found += 1
                await asyncio.sleep(2)
        finally:
            await session.close()

        await save(_NOTIFY, notify)
        if found:
            log.info("[Amazon Coupons] Posted %d deals this cycle", found)

    async def _fetch_coupons(self, session, url: str) -> list[dict]:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.amazon.com/")
        headers["Accept"] = "text/html,application/xhtml+xml,*/*;q=0.8"
        try:
            resp = await session.get(url, headers=headers, timeout=25, allow_redirects=True)
            if resp.status_code != 200:
                log.debug("[Amazon Coupons] %s → HTTP %d", url, resp.status_code)
                return []
            return _parse_coupons(resp.text)
        except Exception as exc:
            log.debug("[Amazon Coupons] Fetch error %s: %s", url, exc)
            return []

    async def _should_alert(self, deal: dict, notify: dict) -> bool:
        key = f"{deal['asin']}_{deal['coupon_raw']}"
        if (time.time() - notify.get(key, 0)) < COUPON_COOLDOWN:
            return False
        return deal["score"] >= MIN_SCORE_TO_ALERT

    async def _post_alert(self, deal: dict) -> None:
        aff_url  = make_affiliate_url(deal["url"])
        price    = deal["deal_price"]
        orig     = deal["original_price"]
        pct      = deal["discount_pct"]
        score    = deal["score"]

        price_str = f"${price:.2f}" if price else "N/A"
        orig_str  = f"${orig:.2f}" if orig else "N/A"
        pct_str   = f"{pct:.0f}% off" if pct else "N/A"

        log.info("[Amazon Coupons] DEAL (score=%d %s): %s | %s | coupon=%s",
                 score, score_label(score), deal["title"][:60], price_str, deal["coupon_raw"])

        await send_deal_alert(
            AMAZON_WEBHOOK_URL,
            store="amazon",
            name=deal["title"],
            url=aff_url,
            price=price_str,
            original_price=orig_str,
            discount_pct=pct_str,
            coupon=deal["coupon_raw"],
            image=deal.get("image", ""),
            is_freebie=(price is not None and price <= 0.01),
            extra_fields=[
                {"name": "🔑 ASIN",       "value": deal["asin"],              "inline": True},
                {"name": "⭐ Deal Score",  "value": f"{score}/100 {score_label(score)}", "inline": True},
            ],
        )


# ── HTML parser ───────────────────────────────────────────────────────────────

def _parse_coupons(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    deals = []

    # Amazon renders coupon cards in several wrapper patterns
    cards = (
        soup.find_all("div", class_=re.compile(r"coupon-item|cpn-card|coupons-item")) or
        soup.find_all("div", attrs={"data-asin": True})
    )

    for card in cards:
        asin = card.get("data-asin", "")
        if not asin:
            # Try extracting from link href
            link = card.find("a", href=re.compile(r"/dp/([A-Z0-9]{10})"))
            if link:
                m = re.search(r"/dp/([A-Z0-9]{10})", link["href"])
                asin = m.group(1) if m else ""
        if not asin:
            continue

        # Title
        title_tag = (
            card.find(id=re.compile(r"coupon.*title|cpn.*title", re.I)) or
            card.find(class_=re.compile(r"truncate|title|product-title", re.I))
        )
        title = title_tag.get_text(strip=True)[:200] if title_tag else ""
        if not title:
            continue

        # Coupon text
        coupon_tag = card.find(class_=re.compile(r"coupon.*badge|cpn.*badge|coupon.*text|percent", re.I))
        coupon_raw = coupon_tag.get_text(strip=True) if coupon_tag else ""
        if not coupon_raw:
            coupon_tag = card.find(string=re.compile(r"Save\s+[\d$]", re.I))
            coupon_raw = str(coupon_tag).strip() if coupon_tag else ""

        # Price
        price_tag = card.find(class_=re.compile(r"a-price|price"))
        original_price: float | None = None
        if price_tag:
            m = re.search(r"[\d,]+\.\d{2}", price_tag.get_text())
            if m:
                try:
                    original_price = float(m.group(0).replace(",", ""))
                except ValueError:
                    pass

        # Image
        img = card.find("img")
        image = img.get("src", "") if img else ""

        # Parse coupon value
        coupon_amount, coupon_type = _parse_coupon_value(coupon_raw)
        deal_price: float | None = None
        discount_pct = 0.0
        if original_price and coupon_amount:
            if coupon_type == "percent":
                deal_price   = original_price * (1 - coupon_amount / 100)
                discount_pct = coupon_amount
            else:
                deal_price   = max(0.0, original_price - coupon_amount)
                discount_pct = (coupon_amount / original_price * 100) if original_price else 0

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=deal_price or 0,
        )

        deals.append({
            "asin":           asin,
            "title":          title,
            "coupon_raw":     coupon_raw,
            "original_price": original_price,
            "deal_price":     deal_price,
            "discount_pct":   discount_pct,
            "image":          image,
            "url":            f"https://www.amazon.com/dp/{asin}",
            "score":          score,
        })

    return deals


def _parse_coupon_value(text: str) -> tuple[float, str]:
    """Returns (amount, 'percent'|'fixed')."""
    # "$X.XX off" or "$X off"
    m = re.search(r"\$\s*([\d.]+)\s*(?:off)?", text, re.I)
    if m:
        try:
            return float(m.group(1)), "fixed"
        except ValueError:
            pass
    # "X% off"
    m = re.search(r"(\d+)\s*%", text, re.I)
    if m:
        try:
            return float(m.group(1)), "percent"
        except ValueError:
            pass
    return 0.0, "fixed"
