"""
Playwright-based browser session for Kasada (Footsites) and Akamai (Walmart).

Uses patchright — a patched Playwright fork that modifies the Chromium binary
itself to remove automation signals at the binary level:
  • Removes navigator.webdriver and CDP fingerprints
  • Patches HeadlessChrome UA string and runtime flags

KEY INSIGHT — why fetch() / curl_cffi both fail:
  Akamai issues _abck only when its sensor script scores the session as human.
  Even with patchright, the sensor detects enough signals to withhold _abck.
  Without _abck, any call to terra-firma or the Footlocker API returns 412/403
  regardless of how it's made (fetch, XHR, curl_cffi).

  The fix: navigate to the actual product page.  When a real browser loads a
  Walmart or Footlocker product page, the page JS calls terra-firma / PDP API
  itself — from within a full browser context that has already passed Akamai's
  page-level challenge.  We intercept those natural API responses.

Architecture:
  fetch_products_via_page_navigation():
    1. Solve challenge on homepage (human simulation)
    2. For each product URL: page.goto(product_url) + intercept the API call
       the page makes automatically → capture the JSON without calling the API
       ourselves
    3. Parse data from intercepted responses
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger(__name__)

COOKIE_TTL = 1500   # 25 min

_cache: dict[str, dict] = {}


# ── Public helpers ─────────────────────────────────────────────────────────────

async def get_site_cookies(url: str) -> dict[str, str]:
    """Legacy helper — kept for diagnostic use."""
    domain = urlparse(url).netloc
    entry  = _cache.get(domain)
    if entry and time.time() < entry["expires"]:
        return entry["cookies"]
    cookies = await _fetch_via_patchright(url)
    if cookies:
        _cache[domain] = {"cookies": cookies, "expires": time.time() + COOKIE_TTL}
    return cookies


def invalidate(url: str) -> None:
    domain = urlparse(url).netloc
    _cache.pop(domain, None)


# ── Human simulation ──────────────────────────────────────────────────────────

async def _simulate_human(page) -> None:
    """Bezier mouse paths + natural scroll so bot sensors record real events."""
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]

        async def bezier_move(x0: float, y0: float, x1: float, y1: float,
                              steps: int = 30) -> None:
            cx = (x0 + x1) / 2 + random.uniform(-80, 80)
            cy = (y0 + y1) / 2 + random.uniform(-80, 80)
            for i in range(1, steps + 1):
                t = i / steps
                nx = (1-t)**2*x0 + 2*(1-t)*t*cx + t**2*x1 + random.uniform(-1.5, 1.5)
                ny = (1-t)**2*y0 + 2*(1-t)*t*cy + t**2*y1 + random.uniform(-1.5, 1.5)
                await page.mouse.move(nx, ny)
                await asyncio.sleep(random.uniform(0.008, 0.025))

        cur_x = w/2 + random.uniform(-40, 40)
        cur_y = h/3 + random.uniform(-20, 20)
        await page.mouse.move(cur_x, cur_y)
        await asyncio.sleep(random.uniform(0.4, 0.8))

        for _ in range(random.randint(3, 5)):
            tx, ty = random.uniform(80, w-80), random.uniform(80, h-80)
            await bezier_move(cur_x, cur_y, tx, ty, steps=random.randint(20, 40))
            cur_x, cur_y = tx, ty
            await asyncio.sleep(random.uniform(0.2, 0.7))

        scroll_pos, scroll_target = 0, random.randint(400, 900)
        while scroll_pos < scroll_target:
            scroll_pos = min(scroll_pos + random.randint(60, 120), scroll_target)
            await page.evaluate(f"window.scrollTo({{top:{scroll_pos},behavior:'auto'}})")
            await asyncio.sleep(random.uniform(0.08, 0.22))
            if random.random() < 0.2:
                await asyncio.sleep(random.uniform(0.3, 0.8))

        await asyncio.sleep(random.uniform(0.5, 1.0))

        for _ in range(random.randint(2, 3)):
            tx, ty = random.uniform(80, w-80), random.uniform(80, h/2)
            await bezier_move(cur_x, cur_y, tx, ty, steps=random.randint(15, 30))
            cur_x, cur_y = tx, ty
            await asyncio.sleep(random.uniform(0.15, 0.5))

        while scroll_pos > 0:
            scroll_pos = max(scroll_pos - random.randint(80, 160), 0)
            await page.evaluate(f"window.scrollTo({{top:{scroll_pos},behavior:'auto'}})")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        await asyncio.sleep(random.uniform(0.3, 0.6))
        log.debug("[CookieManager] Human simulation complete")
    except Exception as exc:
        log.debug("[CookieManager] Simulation error (non-fatal): %s", exc)


# ── Browser launcher ──────────────────────────────────────────────────────────

async def _launch_browser():
    """Return (p_ctx, browser, context) using patchright or playwright fallback."""
    try:
        from patchright.async_api import async_playwright
        log.debug("[CookieManager] Using patchright")
    except ImportError:
        from playwright.async_api import async_playwright  # type: ignore
        log.debug("[CookieManager] Using playwright (patchright not found)")

    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))
    p_ctx = async_playwright()
    p = await p_ctx.__aenter__()
    browser = await p.chromium.launch(
        headless=on_railway,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,800",
        ],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )
    return p_ctx, browser, context


# ── Main entry point for monitors ─────────────────────────────────────────────

async def fetch_products_via_page_navigation(
    site_url: str,
    products: list[dict],
    delay_between: float = 4.0,
) -> dict[str, Any]:
    """
    Solve the bot challenge on site_url, then for each product navigate to its
    page URL and intercept the API call the page makes automatically.

    Each product dict must have:
      "key"         — identifier (SKU, item ID, etc.)
      "url"         — product page URL to navigate to
      "api_pattern" — URL glob for the API call to intercept
                      e.g. "**/terra-firma/fetch**" or "**/api/products/pdp/**"

    Returns dict[key → raw JSON dict] for every successful interception.
    """
    results: dict[str, Any] = {}
    if not products:
        return results

    p_ctx = browser = context = page = None
    try:
        p_ctx, browser, context = await _launch_browser()
        page = await context.new_page()

        # ── Solve homepage challenge ──────────────────────────────────────────
        log.info("[CookieManager] Navigating to %s to solve challenge ...",
                 urlparse(site_url).netloc)
        await page.goto(site_url, timeout=30_000, wait_until="domcontentloaded")
        await _simulate_human(page)

        title = (await page.title()).lower()
        if any(s in title for s in ("robot", "captcha", "blocked", "access denied",
                                     "403", "412", "unusual")):
            log.warning("[CookieManager] Challenge page '%s' on %s — aborting",
                        await page.title(), urlparse(site_url).netloc)
            return results

        log.info("[CookieManager] Challenge passed on %s — navigating %d product pages ...",
                 urlparse(site_url).netloc, len(products))

        # ── Per-product page navigation ───────────────────────────────────────
        # Two modes:
        #   api_pattern set  → intercept the matching API response the page makes
        #   api_pattern None → extract embedded __NEXT_DATA__ JSON from the page
        for prod in products:
            key         = prod["key"]
            product_url = prod["url"]
            api_pattern = prod.get("api_pattern")
            try:
                if api_pattern:
                    async with page.expect_response(
                        api_pattern, timeout=20_000
                    ) as resp_info:
                        await page.goto(product_url, timeout=25_000,
                                        wait_until="domcontentloaded")
                    response = await resp_info.value
                    if response.ok:
                        results[key] = await response.json()
                        log.debug("[CookieManager] ✓ %s via API intercept (HTTP %d)",
                                  key, response.status)
                    else:
                        log.debug("[CookieManager] ✗ %s → API HTTP %d", key, response.status)
                else:
                    # Extract __NEXT_DATA__ embedded in the HTML
                    await page.goto(product_url, timeout=25_000,
                                    wait_until="domcontentloaded")
                    data = await page.evaluate("""
                        () => {
                            const el = document.getElementById('__NEXT_DATA__');
                            if (!el) return null;
                            try { return JSON.parse(el.textContent); }
                            catch(e) { return null; }
                        }
                    """)
                    if data:
                        results[key] = data
                        log.debug("[CookieManager] ✓ %s via __NEXT_DATA__", key)
                    else:
                        log.debug("[CookieManager] ✗ %s — no __NEXT_DATA__ found", key)

            except Exception as exc:
                log.debug("[CookieManager] ✗ %s: %s", key, exc)

            await asyncio.sleep(random.uniform(delay_between * 0.7, delay_between * 1.3))

    except Exception as exc:
        log.warning("[CookieManager] Browser session error for %s: %s", site_url, exc)
    finally:
        try:
            if page:    await page.close()
            if context: await context.close()
            if browser: await browser.close()
            if p_ctx:   await p_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    log.info("[CookieManager] Session complete — %d/%d pages succeeded",
             len(results), len(products))
    return results


# ── Legacy cookie-only fetch ───────────────────────────────────────────────────

async def _fetch_via_patchright(url: str) -> dict[str, str]:
    p_ctx = browser = context = page = None
    cookies: dict[str, str] = {}
    try:
        p_ctx, browser, context = await _launch_browser()
        page = await context.new_page()
        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        await _simulate_human(page)
        raw = await context.cookies()
        cookies = {c["name"]: c["value"] for c in raw}
        log.info("[CookieManager] Extracted %d cookies from %s",
                 len(cookies), urlparse(url).netloc)
    except Exception as exc:
        log.warning("[CookieManager] Cookie fetch error: %s", exc)
    finally:
        try:
            if page:    await page.close()
            if context: await context.close()
            if browser: await browser.close()
            if p_ctx:   await p_ctx.__aexit__(None, None, None)
        except Exception:
            pass
    return cookies