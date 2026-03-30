"""
Target monitor — uses patchright browser to render each product page and
intercept Target's internal Redsky API responses. Falls back to DOM extraction.

Target migrated to full client-side rendering in 2025/2026; the public
Redsky API key and the HTML JSON-LD approach no longer return product data.

Alerts on ≥10% price drops and restocks.
"""
from __future__ import annotations
import asyncio
import logging
import re
import time

from config.products import TARGET_PRODUCTS
from config.settings import TARGET_WEBHOOK_URL, TARGET_INTERVAL
from monitors.base import BaseMonitor
from utils.discord_client import send_deal_alert, send_restock_alert
from utils.resale import resale_fields
from utils.storage import load, save

log = logging.getLogger(__name__)

DEAL_THRESHOLD = 0.10   # 10% off
DEAL_COOLDOWN  = 6 * 3600

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

        for url in TARGET_PRODUCTS:
            result = await self._check_product(url, prices, stock, notify)
            if result:
                c, d, r = result
                checked        += c
                deals_found    += d
                restocks_found += r
            await asyncio.sleep(2)

        await save(_PRICES, prices)
        await save(_STOCK,  stock)
        await save(_NOTIFY, notify)
        log.info("[Target] Cycle complete — %d/%d TCINs fetched | %d deals | %d restocks",
                 checked, len(TARGET_PRODUCTS), deals_found, restocks_found)

    async def _check_product(self, url, prices, stock, notify) -> tuple[int, int, int] | None:
        """Returns (checked, deals_found, restocks_found) or None on parse failure."""
        tcin = _tcin(url)
        if not tcin:
            return None

        product = await self._fetch_product(url, tcin)
        if not product:
            log.debug("[Target] No data for TCIN %s", tcin)
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
            extra_restock = [{"name": "🔑 TCIN", "value": tcin, "inline": True}]
            extra_restock.extend(resale_fields(name, price))
            await send_restock_alert(
                TARGET_WEBHOOK_URL, store="target",
                name=name, url=url, price=price_str, image=image,
                extra_fields=extra_restock,
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
            extra_deal = [{"name": "🔑 TCIN", "value": tcin, "inline": True}]
            extra_deal.extend(resale_fields(name, price))
            await send_deal_alert(
                TARGET_WEBHOOK_URL, store="target",
                name=name, url=url,
                price=price_str, original_price=was_str,
                discount_pct=pct_str, image=image,
                extra_fields=extra_deal,
            )
            notify[cooldown_key] = time.time()
            deals_found = 1

        prices[tcin] = price
        return 1, deals_found, restocks_found

    # ── Data sources ──────────────────────────────────────────────────────────

    async def _fetch_product(self, url: str, tcin: str) -> dict | None:
        """Navigate to Target product page with patchright; intercept Redsky API or scrape DOM."""
        from utils.playwright_session import _launch_browser

        p_ctx = browser = context = page = None
        intercepted: dict | None = None

        try:
            p_ctx, browser, context = await _launch_browser()
            page = await context.new_page()

            async def _on_response(response) -> None:
                nonlocal intercepted
                url_r = response.url
                if intercepted:
                    return
                # Intercept any Redsky/Target API response that has pricing data
                if ("redsky.target.com" in url_r or "api.target.com" in url_r) and response.ok:
                    try:
                        data = await response.json()
                        parsed = _parse_redsky_json(data)
                        if parsed and parsed.get("price"):
                            intercepted = parsed
                            log.debug("[Target] Intercepted API for TCIN %s: %s", tcin, url_r[:80])
                    except Exception:
                        pass

            page.on("response", _on_response)

            log.debug("[Target] Navigating to %s", url)
            try:
                await page.goto(url, timeout=35_000, wait_until="networkidle")
            except Exception:
                try:
                    await page.goto(url, timeout=35_000, wait_until="domcontentloaded")
                    await asyncio.sleep(4)
                except Exception as exc:
                    log.warning("[Target] Navigation error for TCIN %s: %s", tcin, exc)
                    return None

            if intercepted:
                return intercepted

            # Fallback: extract from rendered DOM via JavaScript
            result = await page.evaluate("""
                () => {
                    // Price: look for [data-test="product-price"] or schema.org
                    const priceEl = document.querySelector('[data-test="product-price"]');
                    const priceText = priceEl ? priceEl.textContent : '';
                    const priceMatch = priceText.match(/\\$([\\d,]+\\.?\\d*)/);
                    const price = priceMatch ? parseFloat(priceMatch[1].replace(/,/g,'')) : null;

                    // Was-price (sale scenarios)
                    const wasEl = document.querySelector('[data-test="product-regular-price"]');
                    const wasText = wasEl ? wasEl.textContent : '';
                    const wasMatch = wasText.match(/\\$([\\d,]+\\.?\\d*)/);
                    const wasPrice = wasMatch ? parseFloat(wasMatch[1].replace(/,/g,'')) : null;

                    // Title
                    const h1 = document.querySelector('h1[data-test="product-title"]') ||
                               document.querySelector('h1');
                    const name = h1 ? h1.textContent.trim() : document.title;

                    // Stock
                    const body = document.body.innerText.toLowerCase();
                    const outOfStock = body.includes('out of stock') ||
                                       body.includes('sold out') ||
                                       body.includes('temporarily out of stock');
                    const inStock = !outOfStock && price !== null;

                    // Image
                    const img = document.querySelector('[data-test="product-image"] img') ||
                                document.querySelector('img[alt][src*="target"]');
                    const image = img ? img.src : '';

                    return { name, price, wasPrice, inStock, image };
                }
            """)

            if result and result.get("price"):
                return {
                    "name":      str(result.get("name", ""))[:200],
                    "price":     float(result["price"]),
                    "was_price": float(result["wasPrice"]) if result.get("wasPrice") else None,
                    "in_stock":  bool(result.get("inStock", False)),
                    "image":     str(result.get("image", "")),
                }

            log.debug("[Target] Could not extract price for TCIN %s from DOM", tcin)
            return None

        except Exception as exc:
            log.warning("[Target] Browser error for TCIN %s: %s", tcin, exc)
            return None
        finally:
            try:
                if page:    await page.close()
                if context: await context.close()
                if browser: await browser.close()
                if p_ctx:   await p_ctx.__aexit__(None, None, None)
            except Exception:
                pass


def _parse_redsky_json(data: dict) -> dict | None:
    """Parse a Redsky/Target API JSON response intercepted from the browser."""
    if not isinstance(data, dict):
        return None
    # Standard Redsky v1 shape: data.product.price / inventory / item
    product = data.get("data", {}).get("product", {})
    if not product:
        return None
    pricing   = product.get("price", {})
    inventory = product.get("inventory", {})
    desc      = product.get("item", {}).get("product_description", {})
    name      = desc.get("title", "")
    price     = pricing.get("current_retail") or pricing.get("formatted_current_price_type")
    was_price = pricing.get("reg_retail") or pricing.get("comparable_price")
    in_stock  = inventory.get("availability_status", "") in ("IN_STOCK", "AVAILABLE")
    try:
        price = float(str(price).replace("$", "").replace(",", "").strip()) if price else None
        was_price = float(str(was_price).replace("$", "").replace(",", "").strip()) if was_price else None
    except (ValueError, TypeError):
        price = was_price = None
    if not price:
        return None
    image_url = ""
    imgs = product.get("item", {}).get("enrichment", {}).get("images", {})
    if imgs:
        image_url = imgs.get("base_url", "") + (imgs.get("primary_image_url") or "")
    return {"name": name[:200], "price": price, "was_price": was_price,
            "in_stock": in_stock, "image": image_url}
