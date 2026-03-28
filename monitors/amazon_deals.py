"""
Amazon Deals Page monitor — scrapes amazon.com/deals automatically.

Captures Limited Time Deals, Lightning Deals, and Deals of the Day
without needing a hardcoded product list. Uses Playwright for JS rendering
since the deals page is a React SPA.

Scoring: only deals scoring >= MIN_SCORE_TO_ALERT are posted to Discord.
Hot deals (score 80+) get an @here ping.
"""
import asyncio
import logging
import re
import time

from config.settings import AMAZON_WEBHOOK_URL
from monitors.base import BaseMonitor
from utils.affiliate import make_affiliate_url
from utils.deal_scorer import calculate_deal_score, score_label, MIN_SCORE_TO_ALERT
from utils.discord_client import send_deal_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_COOLDOWN = 7200    # 2 hours per deal
_NOTIFY       = "amazon_deals_notify.json"
INTERVAL      = 600     # 10 minutes


class AmazonDealsMonitor(BaseMonitor):
    name = "Amazon Deals"
    interval = INTERVAL

    async def check(self) -> None:
        notify = await load(_NOTIFY)
        deals  = await _fetch_deals_playwright()
        found  = 0

        for deal in deals:
            key = f"{deal['asin']}_{deal['deal_type']}"
            if (time.time() - notify.get(key, 0)) < DEAL_COOLDOWN:
                continue
            if deal["score"] < MIN_SCORE_TO_ALERT:
                continue

            await _post_alert(deal)
            notify[key] = time.time()
            found += 1
            await asyncio.sleep(1.5)

        await save(_NOTIFY, notify)
        if found:
            log.info("[Amazon Deals] Posted %d deals this cycle", found)


async def _fetch_deals_playwright() -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("[Amazon Deals] Playwright not available — skipping")
        return []

    deals = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            try:
                await page.goto("https://www.amazon.com/deals", timeout=30000,
                                wait_until="domcontentloaded")
                await asyncio.sleep(3)   # let React render
                # Scroll to load more deals
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(1)

                html = await page.content()
                deals = _parse_deals(html)
                log.debug("[Amazon Deals] Parsed %d deal cards", len(deals))
            finally:
                await page.close()
                await context.close()
                await browser.close()
    except Exception as exc:
        log.warning("[Amazon Deals] Playwright error: %s", exc)

    return deals


def _parse_deals(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup  = BeautifulSoup(html, "lxml")
    deals = []

    # Deal cards may appear under various class patterns in React
    cards = soup.find_all("div", attrs={"data-asin": True})
    if not cards:
        # Fallback: look for any link containing /dp/ with nearby price info
        cards = soup.find_all("div", class_=re.compile(r"DealCard|deal-card|dealCard", re.I))

    for card in cards:
        asin = card.get("data-asin", "")
        if not asin:
            link = card.find("a", href=re.compile(r"/dp/([A-Z0-9]{10})"))
            if link:
                m = re.search(r"/dp/([A-Z0-9]{10})", link["href"])
                asin = m.group(1) if m else ""
        if not asin:
            continue

        # Skip expired / sold-out / unavailable deals — they stay on the page
        # after ending and would trigger false alerts when users click the link
        card_text = card.get_text(" ", strip=True).lower()
        if any(s in card_text for s in (
            "deal ended", "sold out", "no longer available",
            "expired", "out of stock", "deal is no longer",
        )):
            continue

        # Title
        title_tag = card.find(class_=re.compile(r"title|name|truncate", re.I))
        title = title_tag.get_text(strip=True)[:200] if title_tag else ""
        if not title:
            continue

        # Deal badge type
        badge_tag = card.find(class_=re.compile(r"badge|deal-type|dealBadge", re.I))
        deal_type = badge_tag.get_text(strip=True) if badge_tag else "Limited Time Deal"

        # Prices
        original_price, deal_price = _extract_dual_prices(card)
        discount_pct = 0.0
        if original_price and deal_price and original_price > 0:
            discount_pct = (original_price - deal_price) / original_price * 100

        # Image
        img   = card.find("img")
        image = img.get("src", "") if img else ""

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=deal_price or 0,
        )

        deals.append({
            "asin":           asin,
            "title":          title,
            "deal_type":      deal_type,
            "original_price": original_price,
            "deal_price":     deal_price,
            "discount_pct":   discount_pct,
            "image":          image,
            "url":            f"https://www.amazon.com/dp/{asin}",
            "score":          score,
        })

    return deals


def _extract_dual_prices(card) -> tuple[float | None, float | None]:
    prices = []
    for tag in card.find_all(class_=re.compile(r"a-price|price")):
        m = re.search(r"[\d,]+\.\d{2}", tag.get_text())
        if m:
            try:
                prices.append(float(m.group(0).replace(",", "")))
            except ValueError:
                pass
    if len(prices) >= 2:
        return max(prices), min(prices)
    if len(prices) == 1:
        return prices[0], None
    return None, None


async def _post_alert(deal: dict) -> None:
    aff_url   = make_affiliate_url(deal["url"])
    orig      = deal["original_price"]
    dp        = deal["deal_price"]
    pct       = deal["discount_pct"]
    score     = deal["score"]
    deal_type = deal["deal_type"]

    price_str = f"${dp:.2f}" if dp else "N/A"
    orig_str  = f"${orig:.2f}" if orig else "N/A"
    pct_str   = f"{pct:.0f}% off" if pct else "N/A"

    log.info("[Amazon Deals] %s (score=%d %s): %s | %s",
             deal_type, score, score_label(score), deal["title"][:60], price_str)

    await send_deal_alert(
        AMAZON_WEBHOOK_URL,
        store="amazon",
        name=f"[{deal_type}] {deal['title']}",
        url=aff_url,
        price=price_str,
        original_price=orig_str,
        discount_pct=pct_str,
        image=deal.get("image", ""),
        is_freebie=(dp is not None and dp <= 0.01),
        extra_fields=[
            {"name": "🏷️ Deal Type",  "value": deal_type,                       "inline": True},
            {"name": "🔑 ASIN",       "value": deal["asin"],                    "inline": True},
            {"name": "⭐ Deal Score",  "value": f"{score}/100 {score_label(score)}", "inline": True},
        ],
    )