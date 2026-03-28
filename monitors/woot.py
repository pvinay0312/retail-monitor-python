"""
Woot.com monitor — scrapes woot.com/deals for electronics & computer deals.

Woot is Amazon-owned and offers daily deals on electronics, computers, and home
goods at 40-70% off — including new overstock and refurbished items.
Woot-Offs (rapid-fire flash sales where a new item loads the moment the previous
one sells out) are especially valuable for cook groups.

Strategy:
  • Fetches woot.com deals page with curl_cffi Chrome impersonation
  • Primary parse: __NEXT_DATA__ JSON blob (reliable, doesn't depend on CSS classes)
  • Fallback parse: CSS class / article / link heuristics
  • Filters for New / Refurbished condition only (skips Used/Good/Acceptable)
  • Scores via deal scorer — only posts if score >= MIN_SCORE_TO_ALERT
  • Detects Woot-Off mode and adds ⚡ warning to alerts
  • Deduplicates by product URL with 1-hour cooldown
"""
from __future__ import annotations
import asyncio
import json
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
    "https://www.woot.com/deals",
    "https://www.woot.com/electronics/deals",
    "https://www.woot.com/computers/deals",
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
            log.info("[Woot] %s → parsed %d qualifying deals", url, len(deals))
            return deals
        except Exception as exc:
            log.warning("[Woot] Fetch error for %s: %s", url, exc)
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
    """
    Parse Woot deal cards from an HTML page.

    Primary strategy: extract the Next.js __NEXT_DATA__ JSON blob which
    contains the full, structured offer list — far more reliable than
    matching CSS classes that change with every Woot frontend deploy.

    Fallback strategy: CSS class / article / link heuristics for pages
    that don't embed __NEXT_DATA__ (e.g. category sub-pages).
    """
    soup = BeautifulSoup(html, "lxml")

    # Detect Woot-Off mode (orange banner or body class)
    is_wootoff = bool(
        soup.find(string=re.compile(r"woot.?off", re.I)) or
        soup.find(class_=re.compile(r"wootoff", re.I))
    )

    # ── Primary: __NEXT_DATA__ JSON ───────────────────────────────────────────
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if next_data_tag:
        try:
            data = json.loads(next_data_tag.string or "")
            deals = _parse_next_data(data, is_wootoff)
            if deals:
                log.debug("[Woot] __NEXT_DATA__ → %d raw offers", len(deals))
                return deals
        except Exception as exc:
            log.debug("[Woot] __NEXT_DATA__ parse error: %s", exc)

    # ── Fallback: CSS / article / link heuristics ─────────────────────────────
    log.debug("[Woot] __NEXT_DATA__ empty — falling back to HTML heuristics")
    return _parse_woot_html(soup, is_wootoff)


def _parse_next_data(data: dict, is_wootoff: bool) -> list[dict]:
    """Recursively find offer arrays in the Next.js page data blob."""
    offers = _find_offer_list(data)
    if not offers:
        return []

    deals: list[dict] = []
    seen_urls: set[str] = set()

    for o in offers:
        if not isinstance(o, dict):
            continue

        # ── Title ──────────────────────────────────────────────────────────────
        title = (
            o.get("name") or o.get("title") or o.get("offerTitle") or
            o.get("productName") or ""
        )[:200]
        if not title or len(title) < 5:
            continue

        # ── URL ────────────────────────────────────────────────────────────────
        raw_url = (
            o.get("url") or o.get("offerUrl") or o.get("canonicalUrl") or
            o.get("slug") or ""
        )
        if raw_url and not raw_url.startswith("http"):
            raw_url = f"https://www.woot.com{raw_url}"
        if not raw_url:
            continue
        if raw_url in seen_urls:
            continue
        seen_urls.add(raw_url)

        # ── Prices ─────────────────────────────────────────────────────────────
        sale_price = _coerce_price(
            o.get("salePrice") or o.get("price") or o.get("currentPrice") or
            o.get("minSalePrice") or 0
        )
        list_price = _coerce_price(
            o.get("listPrice") or o.get("regularPrice") or o.get("msrp") or
            o.get("maxListPrice") or 0
        )
        if not sale_price:
            continue
        original_price = list_price if list_price and list_price > sale_price else None
        discount_pct   = (
            (original_price - sale_price) / original_price * 100
            if original_price else 0.0
        )

        # Woot sometimes provides percentOff directly
        if not discount_pct and o.get("percentOff"):
            try:
                discount_pct = float(o["percentOff"])
                if not original_price:
                    original_price = round(sale_price / (1 - discount_pct / 100), 2)
            except (ValueError, ZeroDivisionError):
                pass

        # ── Condition ──────────────────────────────────────────────────────────
        condition = (
            o.get("condition") or o.get("itemCondition") or
            o.get("conditionDescription") or ""
        )
        if isinstance(condition, dict):
            condition = condition.get("displayName") or condition.get("name") or ""
        condition = str(condition).strip()

        if condition.lower() in ("used", "acceptable", "good"):
            continue

        # ── Image ──────────────────────────────────────────────────────────────
        image = ""
        photos = o.get("photos") or o.get("images") or o.get("photo") or []
        if isinstance(photos, list) and photos:
            first = photos[0]
            image = (first.get("url") or first.get("src") or first) if isinstance(first, dict) else str(first)
        elif isinstance(photos, str):
            image = photos
        if not image:
            image = o.get("imageUrl") or o.get("imageUri") or o.get("primaryImage") or ""

        # ── Category ───────────────────────────────────────────────────────────
        url_lower = raw_url.lower()
        if "computer" in url_lower or "laptop" in url_lower:
            category = "computers"
        elif "phone" in url_lower or "tablet" in url_lower:
            category = "tablets"
        else:
            category = "electronics"

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=sale_price,
            category=category,
        )

        deals.append({
            "title":          title,
            "url":            raw_url,
            "deal_price":     sale_price,
            "original_price": original_price,
            "discount_pct":   discount_pct,
            "condition":      condition,
            "image":          str(image),
            "score":          score,
            "is_wootoff":     is_wootoff,
        })

    return deals


def _find_offer_list(obj, depth: int = 0) -> list:
    """
    Recursively walk the Next.js JSON blob looking for an array of offer dicts.
    Returns the first array where items have both a title-like and price-like key.
    """
    if depth > 8:
        return []
    if isinstance(obj, dict):
        for key in ("offers", "deals", "items", "products", "offerItems", "pageOffers"):
            val = obj.get(key)
            if isinstance(val, list) and val and _looks_like_offer_list(val):
                return val
        for v in obj.values():
            result = _find_offer_list(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        if _looks_like_offer_list(obj):
            return obj
        for item in obj:
            result = _find_offer_list(item, depth + 1)
            if result:
                return result
    return []


def _looks_like_offer_list(lst: list) -> bool:
    """Return True if the list looks like a list of product offer dicts."""
    if not lst or not isinstance(lst[0], dict):
        return False
    sample = lst[0]
    has_title = any(k in sample for k in ("name", "title", "offerTitle", "productName"))
    has_price = any(k in sample for k in ("salePrice", "price", "currentPrice", "minSalePrice"))
    return has_title and has_price


def _coerce_price(val) -> float:
    """Convert various price representations to float."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_woot_html(soup: BeautifulSoup, is_wootoff: bool) -> list[dict]:
    """CSS/article/link heuristic fallback when __NEXT_DATA__ is absent."""
    deals: list[dict] = []

    cards = (
        soup.find_all("div", class_=re.compile(
            r"item-main|moreFeed-item|offer-listing|deal-item|DealCard|dealCard", re.I
        )) or
        soup.find_all("article") or
        soup.find_all("div", attrs={"data-offer-id": True})
    )

    if not cards:
        links = soup.find_all("a", href=re.compile(
            r"woot\.com/(?:\w+/)?(?:offers|products|deals)/", re.I
        ))
        seen_hrefs: set[str] = set()
        for link in links:
            href = link.get("href", "")
            if href not in seen_hrefs:
                seen_hrefs.add(href)
                cards.append(link.find_parent("div") or link)

    if not cards:
        log.warning("[Woot] No deal cards found in HTML — page structure may have changed")
        return []

    log.debug("[Woot] HTML fallback found %d candidate cards", len(cards))
    seen_urls: set[str] = set()

    for card in cards:
        link = (
            card.find("a", href=re.compile(r"woot\.com/(?:\w+/)?(?:offers|products|deals)/")) or
            card.find("a", href=re.compile(r"/(?:offers|products|deals)/"))
        )
        if not link:
            continue
        href = link.get("href", "")
        url  = href if href.startswith("http") else f"https://www.woot.com{href}"
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title_tag = (
            card.find(class_=re.compile(r"title|item-title|offer-title|product-name", re.I)) or
            card.find("h2") or card.find("h3") or link
        )
        title = title_tag.get_text(strip=True)[:200] if title_tag else ""
        if not title or len(title) < 5:
            continue

        original_price, deal_price = _extract_prices(card)
        if not deal_price:
            continue

        discount_pct = (
            (original_price - deal_price) / original_price * 100
            if original_price and original_price > deal_price else 0.0
        )

        cond_match = re.search(
            r"\b(New|Refurbished|Open Box|Like New|Used|Good|Acceptable)\b",
            card.get_text(), re.I
        )
        condition = cond_match.group(1) if cond_match else ""
        if condition.lower() in ("used", "acceptable", "good"):
            continue

        img   = card.find("img")
        image = img.get("src", "") if img else ""

        url_lower = url.lower()
        category = (
            "computers" if ("computer" in url_lower or "laptop" in url_lower) else
            "tablets"   if ("phone" in url_lower or "tablet" in url_lower) else
            "electronics"
        )

        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=deal_price,
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
    """Return (original_price, deal_price) — highest and lowest price found in card."""
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