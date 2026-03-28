"""
Woot.com monitor — scrapes woot.com/alldeals for electronics & computer deals.

Woot is Amazon-owned and offers daily deals on electronics, computers, and home
goods at 40-70% off — including new overstock and refurbished items.
Woot-Offs (rapid-fire flash sales where a new item loads the moment the previous
one sells out) are especially valuable for cook groups.

Strategy:
  • Scrapes woot.com/alldeals with curl_cffi Chrome impersonation
  • Filters for New / Refurbished condition only (skips Used/Good/Acceptable)
  • Scores via deal scorer — only posts if score >= MIN_SCORE_TO_ALERT
  • Detects Woot-Off mode and adds ⚡ warning to alerts
  • Deduplicates by product URL with 1-hour cooldown
"""
import asyncio
import logging
import re
import time

from bs4 import BeautifulSoup

from config.settings import WOOT_WEBHOOK_URL, WOOT_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.deal_scorer import calculate_deal_score, score_label, MIN_SCORE_TO_ALERT
from utils.discord_client import send_deal_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_COOLDOWN = 3600   # 1 hour per item URL
_NOTIFY       = "woot_notify.json"

WOOT_URLS = [
    "https://www.woot.com/alldeals",
]


class WootMonitor(BaseMonitor):
    name     = "Woot"
    interval = WOOT_INTERVAL

    async def check(self) -> None:
        if not WOOT_WEBHOOK_URL:
            log.debug("[Woot] No webhook configured — skipping")
            return

        notify = await load(_NOTIFY)
        session = make_session("chrome120")
        found = 0
        try:
            for url in WOOT_URLS:
                deals = await self._fetch_deals(session, url)
                for deal in deals:
                    key = deal["url"]
                    if (time.time() - notify.get(key, 0)) < DEAL_COOLDOWN:
                        continue
                    if deal["score"] < MIN_SCORE_TO_ALERT:
                        continue
                    await self._post_alert(deal)
                    notify[key] = time.time()
                    found += 1
                    await asyncio.sleep(1)
        finally:
            await session.close()

        await save(_NOTIFY, notify)
        if found:
            log.info("[Woot] Posted %d deals this cycle", found)

    async def _fetch_deals(self, session, url: str) -> list[dict]:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.woot.com/")
        headers["Accept"] = "text/html,application/xhtml+xml,*/*;q=0.8"
        try:
            resp = await session.get(url, headers=headers, timeout=25, allow_redirects=True)
            if resp.status_code != 200:
                log.debug("[Woot] %s → HTTP %d", url, resp.status_code)
                return []
            deals = _parse_woot(resp.text)
            log.debug("[Woot] Parsed %d deals", len(deals))
            return deals
        except Exception as exc:
            log.debug("[Woot] Fetch error: %s", exc)
            return []

    async def _post_alert(self, deal: dict) -> None:
        price     = deal["deal_price"]
        orig      = deal["original_price"]
        pct       = deal["discount_pct"]
        score     = deal["score"]
        condition = deal.get("condition", "")
        wootoff   = deal.get("is_wootoff", False)

        price_str = f"${price:.2f}" if price else "N/A"
        orig_str  = f"${orig:.2f}" if orig else "N/A"
        pct_str   = f"{pct:.0f}% off" if pct else "N/A"
        label     = "⚡ Woot-Off" if wootoff else "Woot"

        log.info("[Woot] DEAL (score=%d %s): %s | %s%s",
                 score, score_label(score), deal["title"][:60], price_str,
                 " ⚡ WOOT-OFF" if wootoff else "")

        extra = [
            {"name": "🏷️ Condition",  "value": condition or "Unknown",              "inline": True},
            {"name": "⭐ Deal Score",  "value": f"{score}/100 {score_label(score)}", "inline": True},
        ]
        if wootoff:
            extra.insert(0, {"name": "⚡ WOOT-OFF", "value": "Flash sale — buy NOW before it's gone!", "inline": False})

        await send_deal_alert(
            WOOT_WEBHOOK_URL,
            store="woot",
            name=f"[{label}] {deal['title']}",
            url=deal["url"],
            price=price_str,
            original_price=orig_str,
            discount_pct=pct_str,
            image=deal.get("image", ""),
            is_freebie=False,
            extra_fields=extra,
        )


# ── HTML parser ────────────────────────────────────────────────────────────────

def _parse_woot(html: str) -> list[dict]:
    soup  = BeautifulSoup(html, "lxml")
    deals = []

    # Detect Woot-Off mode (orange banner with "Woot-Off" text)
    is_wootoff = bool(
        soup.find(string=re.compile(r"woot.?off", re.I)) or
        soup.find(class_=re.compile(r"wootoff", re.I))
    )

    # Woot renders offer cards in various container patterns depending on page version
    cards = (
        soup.find_all("div", class_=re.compile(r"item-main|moreFeed-item|offer-listing|deal-item", re.I)) or
        soup.find_all("article") or
        soup.find_all("div", attrs={"data-offer-id": True})
    )

    # Fallback: build pseudo-cards from all woot offer links
    if not cards:
        links = soup.find_all("a", href=re.compile(r"woot\.com/offers/|woot\.com/\w+/products/|/offers/"))
        seen_hrefs: set[str] = set()
        for link in links:
            href = link.get("href", "")
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            cards.append(link.find_parent("div") or link)

    seen_urls: set[str] = set()
    for card in cards:
        # ── URL ────────────────────────────────────────────────────────────────
        link = (
            card.find("a", href=re.compile(r"woot\.com/offers/|/offers/")) or
            card.find("a", href=re.compile(r"woot\.com/\w+/products/"))
        )
        if not link:
            continue
        href = link.get("href", "")
        url  = href if href.startswith("http") else f"https://www.woot.com{href}"
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # ── Title ──────────────────────────────────────────────────────────────
        title_tag = (
            card.find(class_=re.compile(r"title|item-title|offer-title|product-name", re.I)) or
            card.find("h2") or card.find("h3") or link
        )
        title = title_tag.get_text(strip=True)[:200] if title_tag else ""
        if not title or len(title) < 5:
            continue

        # ── Prices ─────────────────────────────────────────────────────────────
        original_price, deal_price = _extract_prices(card)
        if not deal_price:
            continue

        discount_pct = 0.0
        if original_price and original_price > deal_price:
            discount_pct = (original_price - deal_price) / original_price * 100

        # ── Condition ──────────────────────────────────────────────────────────
        cond_str = card.get_text()
        cond_match = re.search(r"\b(New|Refurbished|Open Box|Like New|Used|Good|Acceptable)\b",
                               cond_str, re.I)
        condition = cond_match.group(1) if cond_match else ""

        # Skip lower-quality conditions — resale margin too thin
        if condition.lower() in ("used", "acceptable", "good"):
            continue

        # ── Image ──────────────────────────────────────────────────────────────
        img   = card.find("img")
        image = img.get("src", "") if img else ""

        # ── Category from URL slug ─────────────────────────────────────────────
        url_lower = url.lower()
        if "computer" in url_lower or "laptop" in url_lower:
            category = "computers"
        elif "phone" in url_lower or "tablet" in url_lower:
            category = "tablets"
        else:
            category = "electronics"

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=deal_price or 0,
            category=category,
        )

        deals.append({
            "title":          title,
            "url":            url,
            "deal_price":     deal_price,
            "original_price": original_price,
            "discount_pct":   discount_pct,
            "condition":      condition,
            "image":          image,
            "score":          score,
            "is_wootoff":     is_wootoff,
        })

    return deals


def _extract_prices(card) -> tuple[float | None, float | None]:
    """Return (original_price, deal_price) — highest and lowest price found."""
    prices = []

    for tag in card.find_all(class_=re.compile(r"price|Price")):
        m = re.search(r"\$([\d,]+\.?\d*)", tag.get_text(strip=True))
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    prices.append(val)
            except ValueError:
                pass

    # Broad fallback: any $XX.XX in the card text
    if not prices:
        for m in re.finditer(r"\$([\d,]+\.\d{2})", card.get_text()):
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