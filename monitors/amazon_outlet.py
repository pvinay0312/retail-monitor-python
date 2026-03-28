"""
Amazon Outlet monitor — scrapes amazon.com/outlet/deals for overstock deals.

Amazon Outlet sells brand-new overstock and excess inventory at 20-70% off.
Unlike lightning deals, outlet items stay listed until stock runs out — no
Playwright needed, the page is server-rendered HTML.

Strategy:
  • Scrapes outlet/deals + electronics and computers sub-pages
  • Parses standard Amazon search-result card structure (data-asin)
  • Only alerts on deals with >= 15% discount AND score >= MIN_SCORE_TO_ALERT
  • 2-hour cooldown per ASIN to avoid repeat alerts on long-running deals
  • Deduplicates ASINs across all outlet sub-pages in the same cycle
"""
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

DEAL_COOLDOWN  = 7200              # 2 hours — outlet deals last much longer than lightning
MIN_DISCOUNT   = 15.0              # skip anything less than 15% off
_NOTIFY        = "amazon_outlet_notify.json"
INTERVAL       = AMAZON_INTERVAL * 2   # 8 min — no need to check as fast as product monitor

OUTLET_URLS = [
    ("https://www.amazon.com/outlet/deals",              "electronics"),   # all outlet
    ("https://www.amazon.com/outlet/deals?node=172282",  "electronics"),   # electronics
    ("https://www.amazon.com/outlet/deals?node=541966",  "computers"),     # computers
    ("https://www.amazon.com/outlet/deals?node=1055398", "home"),          # home & kitchen
]


class AmazonOutletMonitor(BaseMonitor):
    name     = "Amazon Outlet"
    interval = INTERVAL

    async def check(self) -> None:
        notify     = await load(_NOTIFY)
        session    = make_session("chrome120")
        found      = 0
        seen_asins: set[str] = set()   # deduplicate across sub-pages in one cycle

        try:
            for url, category in OUTLET_URLS:
                deals = await self._fetch_outlet(session, url, category)
                for deal in deals:
                    asin = deal["asin"]
                    if asin in seen_asins:
                        continue
                    seen_asins.add(asin)
                    if (time.time() - notify.get(asin, 0)) < DEAL_COOLDOWN:
                        continue
                    if deal["score"] < MIN_SCORE_TO_ALERT:
                        continue
                    await self._post_alert(deal)
                    notify[asin] = time.time()
                    found += 1
                await asyncio.sleep(3)
        finally:
            await session.close()

        await save(_NOTIFY, notify)
        if found:
            log.info("[Amazon Outlet] Posted %d deals this cycle", found)

    async def _fetch_outlet(self, session, url: str, category: str) -> list[dict]:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.amazon.com/")
        headers["Accept"] = "text/html,application/xhtml+xml,*/*;q=0.8"
        try:
            resp = await session.get(url, headers=headers, timeout=25, allow_redirects=True)
            if resp.status_code != 200:
                log.debug("[Amazon Outlet] %s → HTTP %d", url, resp.status_code)
                return []
            deals = _parse_outlet(resp.text, category)
            log.debug("[Amazon Outlet] %s → %d items", url, len(deals))
            return deals
        except Exception as exc:
            log.debug("[Amazon Outlet] Fetch error: %s", exc)
            return []

    async def _post_alert(self, deal: dict) -> None:
        aff_url   = make_affiliate_url(deal["url"])
        price     = deal["deal_price"]
        orig      = deal["original_price"]
        pct       = deal["discount_pct"]
        score     = deal["score"]

        price_str = f"${price:.2f}" if price else "N/A"
        orig_str  = f"${orig:.2f}" if orig else "N/A"
        pct_str   = f"{pct:.0f}% off" if pct else "N/A"

        log.info("[Amazon Outlet] DEAL (score=%d %s): %s | %s",
                 score, score_label(score), deal["title"][:60], price_str)

        await send_deal_alert(
            AMAZON_WEBHOOK_URL,
            store="amazon",
            name=f"[Outlet] {deal['title']}",
            url=aff_url,
            price=price_str,
            original_price=orig_str,
            discount_pct=pct_str,
            image=deal.get("image", ""),
            is_freebie=False,
            extra_fields=[
                {"name": "🏷️ Type",     "value": "Amazon Outlet (Overstock — Brand New)", "inline": False},
                {"name": "🔑 ASIN",      "value": deal["asin"],                            "inline": True},
                {"name": "⭐ Deal Score", "value": f"{score}/100 {score_label(score)}",    "inline": True},
            ],
        )


# ── HTML parser ────────────────────────────────────────────────────────────────

def _parse_outlet(html: str, category: str) -> list[dict]:
    soup  = BeautifulSoup(html, "lxml")
    deals = []

    # Outlet page uses standard Amazon search-result card structure
    cards = soup.find_all("div", attrs={"data-asin": re.compile(r"^[A-Z0-9]{10}$")})

    for card in cards:
        asin = card.get("data-asin", "").strip()
        if not asin or len(asin) != 10:
            continue

        # ── Title ──────────────────────────────────────────────────────────────
        title_tag = (
            card.find("span", class_="a-size-base-plus") or
            card.find("span", class_="a-size-medium") or
            card.find("h2") or
            card.find("span", class_=re.compile(r"a-text-normal"))
        )
        title = title_tag.get_text(strip=True)[:200] if title_tag else ""
        if not title:
            continue

        # ── Prices ─────────────────────────────────────────────────────────────
        original_price, deal_price = _extract_outlet_prices(card)
        if not deal_price:
            continue

        discount_pct = 0.0
        if original_price and original_price > deal_price:
            discount_pct = (original_price - deal_price) / original_price * 100

        if discount_pct < MIN_DISCOUNT:
            continue

        # ── Image ──────────────────────────────────────────────────────────────
        img   = card.find("img", class_=re.compile(r"s-image"))
        image = img.get("src", "") if img else ""

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=deal_price or 0,
            category=category,
        )

        deals.append({
            "asin":           asin,
            "title":          title,
            "deal_price":     deal_price,
            "original_price": original_price,
            "discount_pct":   discount_pct,
            "image":          image,
            "url":            f"https://www.amazon.com/dp/{asin}",
            "score":          score,
        })

    return deals


def _extract_outlet_prices(card) -> tuple[float | None, float | None]:
    """Return (original_price, deal_price) from an Amazon product card."""
    prices: list[float] = []

    # Most reliable: screen-reader offscreen spans (e.g. "$34.99")
    for tag in card.find_all("span", class_="a-offscreen"):
        m = re.search(r"\$([\d,]+\.?\d*)", tag.get_text(strip=True))
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    prices.append(val)
            except ValueError:
                pass

    # Fallback: whole + fraction pair
    if not prices:
        whole = card.find(class_="a-price-whole")
        frac  = card.find(class_="a-price-fraction")
        if whole:
            try:
                w = whole.get_text(strip=True).replace(",", "").rstrip(".")
                f = frac.get_text(strip=True) if frac else "00"
                prices.append(float(f"{w}.{f}"))
            except ValueError:
                pass

    # Strike-through price (original before discount)
    for tag in card.find_all("span", class_=re.compile(r"a-text-strike")):
        m = re.search(r"\$([\d,]+\.?\d*)", tag.get_text())
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    prices.append(val)
            except ValueError:
                pass

    prices = sorted(set(prices), reverse=True)
    if len(prices) >= 2:
        return prices[0], prices[-1]
    if len(prices) == 1:
        return None, prices[0]
    return None, None