"""
Playwright-based cookie extractor for Kasada (Footsites) and Akamai (Walmart).

Bot challenges like Kasada and Akamai Bot Manager run JavaScript that:
  1. Fingerprints the browser (TLS, canvas, navigator.webdriver, etc.)
  2. Collects mouse/scroll/keyboard event data to score human-likeness
  3. Issues a cryptographic challenge the client must solve
  4. Sets cookies that prove the challenge was solved

curl_cffi alone can't solve these challenges — it never executes JavaScript.
Playwright with playwright-stealth patches the obvious automation signals,
and _simulate_human() drives realistic mouse movements + scrolling during
the challenge window so the event-data sensors score the session as human.

Architecture:
  • One Playwright launch per domain per TTL window (25 min default)
  • Cookies are cached in-process; Playwright closes immediately after extraction
  • curl_cffi requests attach the cached cookies — fast, no extra browser overhead
"""
import asyncio
import logging
import math
import os
import random
import time
from urllib.parse import urlparse

log = logging.getLogger(__name__)

COOKIE_TTL = 1500   # 25 min — Kasada tokens typically last 15-30 min

# domain → {"cookies": dict[str,str], "expires": float}
_cache: dict[str, dict] = {}


async def get_site_cookies(url: str) -> dict[str, str]:
    """
    Return a dict of cookies for the given URL's domain.

    Serves from cache when valid; otherwise launches a Chromium browser
    with playwright-stealth + human simulation, navigates to the URL
    (solving any bot challenge), and returns the resulting cookies.
    """
    domain = urlparse(url).netloc
    entry  = _cache.get(domain)
    if entry and time.time() < entry["expires"]:
        log.debug("[CookieManager] Cache hit for %s (%d cookies, %.0fs remaining)",
                  domain, len(entry["cookies"]), entry["expires"] - time.time())
        return entry["cookies"]

    log.info("[CookieManager] Launching browser to solve challenge for %s", domain)
    cookies = await _fetch_via_playwright(url)

    if cookies:
        _cache[domain] = {"cookies": cookies, "expires": time.time() + COOKIE_TTL}
        log.info("[CookieManager] Cached %d cookies for %s (TTL=%ds)",
                 len(cookies), domain, COOKIE_TTL)
    else:
        log.warning("[CookieManager] 0 cookies returned for %s — challenge may have failed", domain)

    return cookies


def invalidate(url: str) -> None:
    """Force the next call to get_site_cookies to fetch fresh cookies."""
    domain = urlparse(url).netloc
    _cache.pop(domain, None)


# ── Human simulation ──────────────────────────────────────────────────────────

async def _simulate_human(page) -> None:
    """
    Drive the browser like a human for ~15 seconds while bot-challenge JS runs.

    Akamai's sensor and Kasada's challenge both collect mouse movement vectors,
    scroll velocity, and timing entropy.  A session with zero events is an
    instant bot signal.  This function produces:
      • Bezier-curve mouse paths (not straight lines) between random waypoints
      • Natural scroll-down then scroll-back-up with variable speed
      • Random micro-pauses between every action
    """
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]

        async def bezier_move(x0: float, y0: float, x1: float, y1: float,
                              steps: int = 30) -> None:
            """Move mouse along a quadratic Bezier curve with jitter."""
            # Random control point slightly off the straight path
            cx = (x0 + x1) / 2 + random.uniform(-80, 80)
            cy = (y0 + y1) / 2 + random.uniform(-80, 80)
            for i in range(1, steps + 1):
                t = i / steps
                # Quadratic Bezier
                nx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
                ny = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
                # Tiny per-step jitter
                nx += random.uniform(-1.5, 1.5)
                ny += random.uniform(-1.5, 1.5)
                await page.mouse.move(nx, ny)
                await asyncio.sleep(random.uniform(0.008, 0.025))

        # Start near centre of page
        cur_x, cur_y = w / 2 + random.uniform(-40, 40), h / 3 + random.uniform(-20, 20)
        await page.mouse.move(cur_x, cur_y)
        await asyncio.sleep(random.uniform(0.4, 0.8))

        # ── Phase 1: a few random mouse sweeps while page loads ───────────────
        for _ in range(random.randint(3, 5)):
            tx = random.uniform(80, w - 80)
            ty = random.uniform(80, h - 80)
            await bezier_move(cur_x, cur_y, tx, ty,
                              steps=random.randint(20, 40))
            cur_x, cur_y = tx, ty
            await asyncio.sleep(random.uniform(0.2, 0.7))

        # ── Phase 2: scroll down naturally ───────────────────────────────────
        scroll_target = random.randint(400, 900)
        scroll_pos = 0
        step = random.randint(60, 120)
        while scroll_pos < scroll_target:
            scroll_pos = min(scroll_pos + step, scroll_target)
            await page.evaluate(f"window.scrollTo({{top: {scroll_pos}, behavior: 'auto'}})")
            await asyncio.sleep(random.uniform(0.08, 0.22))
            # Occasional micro-pause like a reader
            if random.random() < 0.2:
                await asyncio.sleep(random.uniform(0.3, 0.8))

        await asyncio.sleep(random.uniform(0.6, 1.2))

        # ── Phase 3: more mouse movement at the scrolled position ─────────────
        for _ in range(random.randint(2, 4)):
            tx = random.uniform(80, w - 80)
            ty = random.uniform(80, min(h - 80, h / 2))
            await bezier_move(cur_x, cur_y, tx, ty,
                              steps=random.randint(15, 35))
            cur_x, cur_y = tx, ty
            await asyncio.sleep(random.uniform(0.15, 0.5))

        # ── Phase 4: scroll back to top ───────────────────────────────────────
        while scroll_pos > 0:
            scroll_pos = max(scroll_pos - random.randint(80, 160), 0)
            await page.evaluate(f"window.scrollTo({{top: {scroll_pos}, behavior: 'auto'}})")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        await asyncio.sleep(random.uniform(0.4, 0.9))

        # ── Phase 5: final drift toward a nav/header element ─────────────────
        tx = random.uniform(w * 0.2, w * 0.8)
        ty = random.uniform(20, 80)
        await bezier_move(cur_x, cur_y, tx, ty, steps=25)
        await asyncio.sleep(random.uniform(0.3, 0.6))

        log.debug("[CookieManager] Human simulation complete")

    except Exception as exc:
        # Never let simulation errors abort cookie extraction
        log.debug("[CookieManager] Human simulation error (non-fatal): %s", exc)


# ── Core Playwright fetch ─────────────────────────────────────────────────────

async def _fetch_via_playwright(url: str) -> dict[str, str]:
    """Launch Playwright, simulate human behaviour, return resulting cookies."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log.warning("[CookieManager] Playwright not installed — cannot extract cookies")
        return {}

    stealth_async = None
    try:
        from playwright_stealth import stealth_async  # type: ignore
    except ImportError:
        log.debug("[CookieManager] playwright-stealth not installed — running without patches")

    # Use visible browser locally — removes headless detection signals.
    # On Railway (no display) stay headless.
    on_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))
    headless = on_railway

    cookies: dict[str, str] = {}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
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
            page = await context.new_page()

            if stealth_async:
                await stealth_async(page)

            try:
                await page.goto(url, timeout=30_000, wait_until="domcontentloaded")

                # Simulate human while challenge JS collects sensor data
                log.info("[CookieManager] Simulating human behaviour on %s ...", urlparse(url).netloc)
                await _simulate_human(page)

                # Check if we got blocked even inside Playwright
                page_title = (await page.title()).lower()
                block_signals = ("access denied", "blocked", "robot", "captcha",
                                 "error", "403", "412", "unusual traffic")
                if any(s in page_title for s in block_signals):
                    log.warning(
                        "[CookieManager] *** BLOCK DETECTED *** "
                        "Playwright page title: '%s' for %s. "
                        "Bot protection is defeating the human simulation.",
                        await page.title(), urlparse(url).netloc,
                    )
                    await context.close()
                    await browser.close()
                    return {}

                raw = await context.cookies()
                cookies = {c["name"]: c["value"] for c in raw}

                # Log all cookie names for diagnostics
                log.info("[CookieManager] All cookies for %s: %s",
                         urlparse(url).netloc, list(cookies.keys()))

                # Report whether the key challenge cookies were obtained
                kasada_keys = [k for k in cookies if "kpsdk" in k.lower() or "x-kpsdk" in k.lower()]
                akamai_keys = [k for k in cookies if any(s in k.lower() for s in
                               ("ak_bmsc", "bm_sz", "_abck", "bm_sv", "bm_mi"))]
                abck = "_abck" in cookies

                if kasada_keys:
                    log.info("[CookieManager] ✓ Kasada cookies obtained: %s", kasada_keys)
                elif "footlocker" in url or "champssports" in url:
                    log.warning("[CookieManager] ✗ No Kasada cookies from %s — challenge not solved", url)

                if akamai_keys:
                    log.info("[CookieManager] ✓ Akamai cookies obtained (abck=%s): %s", abck, akamai_keys)
                elif "walmart" in url:
                    log.warning("[CookieManager] ✗ No Akamai cookies from %s — challenge not solved", url)

            except Exception as exc:
                log.warning("[CookieManager] Navigation failed for %s: %s", url, exc)
            finally:
                await context.close()
                await browser.close()

    except Exception as exc:
        log.warning("[CookieManager] Playwright launch error: %s", exc)

    return cookies