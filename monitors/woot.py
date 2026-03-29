"""
Woot.com monitor — tracks daily deals and Woot-Off flash sales.

Woot migrated to a fully client-side-rendered jQuery app in early 2026.
The old /deals and /electronics/deals paths now return 404, and the HTML
shell at /alldeals / /category/* contains zero product data — everything
loads via AJAX after page JS executes.

Strategy (updated):
  1. Launch patchright browser and navigate to each Woot category page.
  2. Intercept the JSON API response the page JS loads automatically
     (matches *.woot.com/api/* or api.woot.com/* patterns).
  3. If no API intercept fires, fall back to full DOM extraction:
     • look for rendered deal card elements
     • pull price / title / URL / image from the live DOM
  4. Score each deal; post those above MIN_SCORE_TO_ALERT.
  5. Detect Woot-Off mode (orange flash-sale banner) and flag alerts.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from config.settings import WOOT_WEBHOOK_URL, WOOT_INTERVAL
from monitors.base import BaseMonitor
from utils.deal_scorer import calculate_deal_score, score_label, MIN_SCORE_TO_ALERT
from utils.discord_client import send_deal_alert
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_COOLDOWN = 3600   # 1 hour per item URL
_NOTIFY       = "woot_notify.json"

# Woot category pages (correct URLs as of 2026)
WOOT_URLS = [
    "https://www.woot.com/alldeals",
    "https://www.woot.com/category/electronics",
    "https://www.woot.com/category/computers",
    "https://www.woot.com/category/home",
]

class WootMonitor(BaseMonitor):
    name     = "Woot"
    interval = WOOT_INTERVAL

    async def check(self) -> None:
        if not WOOT_WEBHOOK_URL:
            log.debug("[Woot] No webhook configured — skipping")
            return

        notify = await load(_NOTIFY)
        found  = 0

        for url in WOOT_URLS:
            deals = await self._fetch_deals_browser(url)
            for deal in deals:
                key = deal["url"]
                if (time.time() - notify.get(key, 0)) < DEAL_COOLDOWN:
                    continue
                if deal["score"] < MIN_SCORE_TO_ALERT:
                    continue
                await self._post_alert(deal)
                notify[key] = time.time()
                found += 1
                await asyncio.sleep(1.5)

        await save(_NOTIFY, notify)
        if found:
            log.info("[Woot] Posted %d deals this cycle", found)
        else:
            log.info("[Woot] Cycle complete — no new qualifying deals")

    # ── Browser-based fetch ────────────────────────────────────────────────────

    async def _fetch_deals_browser(self, url: str) -> list[dict]:
        """Navigate to the Woot page in patchright; intercept API or scrape DOM."""
        from utils.playwright_session import _launch_browser

        p_ctx = browser = context = page = None
        intercepted: list[Any] = []

        try:
            p_ctx, browser, context = await _launch_browser()
            page = await context.new_page()

            # Capture any JSON API responses the page triggers
            async def _on_response(response) -> None:
                url_r = response.url
                if any(k in url_r for k in ("api.woot", "/api/", "events.json", "offers.json")):
                    if response.ok:
                        try:
                            data = await response.json()
                            intercepted.append(data)
                            log.debug("[Woot] Intercepted API: %s", url_r)
                        except Exception:
                            pass

            page.on("response", _on_response)

            log.info("[Woot] Navigating to %s ...", url)
            try:
                await page.goto(url, timeout=35_000, wait_until="networkidle")
            except Exception:
                # networkidle can time out on pages with perpetual background calls
                try:
                    await page.goto(url, timeout=35_000, wait_until="domcontentloaded")
                    await asyncio.sleep(5)   # wait for AJAX deal load
                except Exception as exc:
                    log.warning("[Woot] Navigation error for %s: %s", url, exc)
                    return []

            # ── Try intercepted API data first ────────────────────────────────
            if intercepted:
                deals = []
                for data in intercepted:
                    deals.extend(_parse_api_response(data))
                if deals:
                    log.info("[Woot] %s → %d deals via API intercept", url, len(deals))
                    return deals

            # ── Fallback: extract from rendered DOM ────────────────────────────
            log.debug("[Woot] No API intercepted for %s — extracting from DOM", url)
            is_wootoff = await page.evaluate("""
                () => document.body.innerText.toLowerCase().includes('woot-off') ||
                      document.body.className.toLowerCase().includes('wootoff')
            """)

            raw_cards = await page.evaluate("""
                () => {
                    // Strip price/savings noise from a candidate title string
                    function cleanTitle(raw) {
                        if (!raw) return '';
                        // Remove leading price patterns: "$259.99 Reference PriceSave: $50 (16%)"
                        let t = raw
                            .replace(/^(\\$[\\d.,]+\\s*)+/g, '')
                            .replace(/^[\\d.,]+\\s*$/g, '')
                            .replace(/Reference Price[^A-Z]*/gi, '')
                            .replace(/Save:\\s*\\$[\\d.,]+\\s*\\([^)]+\\)/gi, '')
                            .replace(/\\([\\d]+%\\s*off\\)/gi, '')
                            .replace(/\\$[\\d,]+\\.\\d{2}/g, '')
                            .replace(/\\s{2,}/g, ' ')
                            .trim();
                        return t;
                    }

                    // Best title candidate from a card element
                    function extractTitle(card, link) {
                        const img = card.querySelector('img[alt]');
                        const imgAlt = img ? img.getAttribute('alt') : '';

                        // Img alt that looks like a real product name (not "deal image" etc.)
                        if (imgAlt && imgAlt.length > 8 && !/deal|image|photo|thumb|logo/i.test(imgAlt)) {
                            return imgAlt;
                        }
                        // data-name / aria-label on the card
                        const dataName = card.getAttribute('data-name') || card.getAttribute('aria-label');
                        if (dataName && dataName.length > 5) return dataName;

                        // Heading — clean it before using
                        const heading = card.querySelector('h1,h2,h3,h4');
                        if (heading) {
                            const cleaned = cleanTitle(heading.textContent);
                            if (cleaned.length >= 5) return cleaned;
                        }
                        // Link text as last resort
                        const linkText = cleanTitle(link.textContent);
                        return linkText;
                    }

                    const results = [];
                    const seen = new Set();

                    // Helper: parse a price string like "$9.99" or "$1,299" → float
                    function parsePrice(txt) {
                        if (!txt) return 0;
                        const m = txt.match(/\$?([\d,]+\.?\d*)/);
                        return m ? parseFloat(m[1].replace(/,/g, '')) : 0;
                    }

                    // Helper: extract sale price + list price from a card using
                    // Woot's known CSS classes.  Falls back to regex on card text.
                    function extractPrices(card) {
                        // Woot uses span.price (current) and span.list-price (reference)
                        const saleEl = card.querySelector('span.price');
                        const listEl = card.querySelector('span.list-price');
                        const sale   = saleEl ? parsePrice(saleEl.textContent) : 0;
                        const list   = listEl ? parsePrice(listEl.textContent) : 0;
                        if (sale > 0) {
                            return list > sale ? [list, sale] : [sale];
                        }
                        // Fallback: regex on card text, but restrict to the card's
                        // own price block element to avoid sibling card prices
                        const priceBlock = card.querySelector(
                            '[class*="price"],[class*="Price"],[data-testid*="price"]'
                        );
                        const src = priceBlock ? priceBlock.innerText : card.innerText;
                        // Only take first 2 price-like matches to avoid sibling bleed
                        const matches = (src.match(/\$[\d,]+\\.\\d{2}/g) || []).slice(0, 2);
                        return matches.map(p => parseFloat(p.replace(/[\\$,]/g,''))).filter(p => p > 0);
                    }

                    // Strategy 1: offer links
                    const offerLinks = document.querySelectorAll(
                        'a[href*="/offers/"], a[href*="woot.com/deals/"], a[href*="woot.com/products/"]'
                    );

                    for (const link of offerLinks) {
                        const href = link.href;
                        if (!href || seen.has(href)) continue;
                        seen.add(href);

                        const card  = link.closest('div, article, section, li') || link.parentElement || link;
                        const txt   = card.innerText || '';
                        const prices = extractPrices(card);
                        const title  = extractTitle(card, link);
                        const img    = card.querySelector('img');
                        const condMatch = txt.match(/\\b(New|Refurbished|Open Box|Like New)\\b/i);

                        if (title.length >= 5 && prices.length > 0) {
                            results.push({
                                title:    title.substring(0, 200),
                                url:      href,
                                prices:   prices,
                                image:    img ? img.src : '',
                                condition: condMatch ? condMatch[1] : '',
                            });
                        }
                    }

                    // Strategy 2: any card with price + link if strategy 1 found nothing
                    if (results.length === 0) {
                        const cards = document.querySelectorAll(
                            'article, [class*="deal"], [class*="item"], [class*="offer"], [class*="card"]'
                        );
                        for (const card of cards) {
                            const link = card.querySelector('a[href]');
                            if (!link) continue;
                            const href = link.href;
                            if (!href || seen.has(href) || !href.includes('woot.com')) continue;
                            seen.add(href);
                            const prices = extractPrices(card);
                            const img    = card.querySelector('img');
                            const title  = extractTitle(card, link);
                            if (title.length >= 5 && prices.length > 0) {
                                results.push({ title: title.substring(0,200), url: href,
                                               prices, image: img ? img.src : '', condition: '' });
                            }
                        }
                    }
                    return results;
                }
            """)

            deals = _build_deals_from_dom(raw_cards, bool(is_wootoff))
            log.info("[Woot] %s → %d deals via DOM extraction", url, len(deals))
            return deals

        except Exception as exc:
            log.warning("[Woot] Browser error for %s: %s", url, exc)
            return []
        finally:
            try:
                if page:    await page.close()
                if context: await context.close()
                if browser: await browser.close()
                if p_ctx:   await p_ctx.__aexit__(None, None, None)
            except Exception:
                pass

    # ── Discord alert ──────────────────────────────────────────────────────────

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
            {"name": "🏷️ Condition",  "value": condition or "New/Refurb",            "inline": True},
            {"name": "⭐ Deal Score",  "value": f"{score}/100 {score_label(score)}", "inline": True},
        ]
        if wootoff:
            extra.insert(0, {"name": "⚡ WOOT-OFF",
                              "value": "Flash sale — buy NOW before it's gone!",
                              "inline": False})

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


# ── Parsers ────────────────────────────────────────────────────────────────────

def _parse_api_response(data: Any) -> list[dict]:
    """Parse JSON from an intercepted Woot API response."""
    if not isinstance(data, (dict, list)):
        return []
    offers = _find_offer_list(data) if isinstance(data, dict) else (data if _looks_like_offer_list(data) else [])
    if not offers:
        return []

    deals: list[dict] = []
    seen: set[str] = set()

    for o in offers:
        if not isinstance(o, dict):
            continue

        title = (o.get("name") or o.get("title") or o.get("offerTitle") or
                 o.get("productName") or "")[:200]
        if not title or len(title) < 5:
            continue

        raw_url = (o.get("url") or o.get("offerUrl") or o.get("canonicalUrl") or o.get("slug") or "")
        if raw_url and not raw_url.startswith("http"):
            raw_url = f"https://www.woot.com{raw_url}"
        if not raw_url or raw_url in seen:
            continue
        seen.add(raw_url)

        sale_price = _coerce_price(o.get("salePrice") or o.get("price") or o.get("currentPrice") or
                                   o.get("minSalePrice") or 0)
        list_price = _coerce_price(o.get("listPrice") or o.get("regularPrice") or o.get("msrp") or
                                   o.get("maxListPrice") or 0)
        if not sale_price:
            continue

        original_price = list_price if list_price and list_price > sale_price else None
        discount_pct = (original_price - sale_price) / original_price * 100 if original_price else 0.0

        if not discount_pct and o.get("percentOff"):
            try:
                discount_pct = float(o["percentOff"])
                if not original_price:
                    original_price = round(sale_price / (1 - discount_pct / 100), 2)
            except (ValueError, ZeroDivisionError):
                pass

        condition = o.get("condition") or o.get("itemCondition") or ""
        if isinstance(condition, dict):
            condition = condition.get("displayName") or condition.get("name") or ""
        condition = str(condition).strip()
        if condition.lower() in ("used", "acceptable", "good"):
            continue

        image = ""
        photos = o.get("photos") or o.get("images") or o.get("photo") or []
        if isinstance(photos, list) and photos:
            first = photos[0]
            image = (first.get("url") or first.get("src") or first) if isinstance(first, dict) else str(first)
        if not image:
            image = o.get("imageUrl") or o.get("imageUri") or o.get("primaryImage") or ""

        category = _guess_category(raw_url)
        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=sale_price,
            category=category,
        )
        deals.append({
            "title": title, "url": raw_url, "deal_price": sale_price,
            "original_price": original_price, "discount_pct": discount_pct,
            "condition": condition, "image": str(image), "score": score,
            "is_wootoff": False,
        })

    return deals


def _build_deals_from_dom(raw_cards: list[dict], is_wootoff: bool) -> list[dict]:
    """Convert DOM-extracted card dicts into scored deal dicts."""
    deals: list[dict] = []
    for card in raw_cards:
        prices = sorted(set(card.get("prices", [])), reverse=True)
        if not prices:
            continue

        # Lowest price = sale price; highest = original if there are 2+
        sale_price = prices[-1]
        original_price = prices[0] if len(prices) >= 2 and prices[0] > sale_price else None
        discount_pct = (
            (original_price - sale_price) / original_price * 100
            if original_price else 0.0
        )

        condition = card.get("condition", "")
        if condition.lower() in ("used", "acceptable", "good"):
            continue

        raw_url = card.get("url", "")
        category = _guess_category(raw_url)
        score = calculate_deal_score(
            discount_pct=discount_pct,
            original_price=original_price or 0,
            deal_price=sale_price,
            category=category,
        )
        deals.append({
            "title": card.get("title", ""),
            "url": raw_url,
            "deal_price": sale_price,
            "original_price": original_price,
            "discount_pct": discount_pct,
            "condition": condition,
            "image": card.get("image", ""),
            "score": score,
            "is_wootoff": is_wootoff,
        })

    return deals


# ── Utility helpers ────────────────────────────────────────────────────────────

def _guess_category(url: str) -> str:
    u = url.lower()
    if any(k in u for k in ("computer", "laptop", "monitor", "keyboard")):
        return "computers"
    if any(k in u for k in ("phone", "tablet", "ipad")):
        return "tablets"
    if any(k in u for k in ("gaming", "game", "console", "xbox", "playstation")):
        return "gaming"
    return "electronics"


def _find_offer_list(obj, depth: int = 0) -> list:
    if depth > 8 or not isinstance(obj, dict):
        return []
    for key in ("offers", "deals", "items", "products", "offerItems", "pageOffers"):
        val = obj.get(key)
        if isinstance(val, list) and val and _looks_like_offer_list(val):
            return val
    for v in obj.values():
        if isinstance(v, (dict, list)):
            r = _find_offer_list(v, depth + 1) if isinstance(v, dict) else (v if _looks_like_offer_list(v) else [])
            if r:
                return r
    return []


def _looks_like_offer_list(lst: list) -> bool:
    if not lst or not isinstance(lst[0], dict):
        return False
    sample = lst[0]
    has_title = any(k in sample for k in ("name", "title", "offerTitle", "productName"))
    has_price = any(k in sample for k in ("salePrice", "price", "currentPrice", "minSalePrice"))
    return has_title and has_price


def _coerce_price(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0