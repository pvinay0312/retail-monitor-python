"""
Playwright-based cookie extractor for Kasada (Footsites) and Akamai (Walmart).

Bot challenges like Kasada and Akamai Bot Manager run JavaScript that:
  1. Fingerprints the browser (TLS, canvas, navigator.webdriver, etc.)
  2. Issues a cryptographic challenge the client must solve
  3. Sets cookies that prove the challenge was solved

curl_cffi alone can't solve these challenges — it never executes JavaScript.
Playwright with playwright-stealth patches the obvious automation signals and
actually runs the challenge JS, producing valid cookies we can re-use.

Architecture:
  • One Playwright launch per domain per TTL window (30 min default)
  • Cookies are cached in-process; Playwright closes immediately after extraction
  • curl_cffi requests attach the cached cookies — fast, no extra browser overhead

Limitations:
  • Kasada and Akamai do periodic re-challenges; TTL is tuned conservatively
  • Datacenter IPs (Railway) are sometimes blocked at the IP level regardless of
    cookies.  If the IP itself is on a hard block-list this won't help, but it's
    strictly better than no cookies at all.
"""
import asyncio
import logging
import os
import time
from urllib.parse import urlparse

log = logging.getLogger(__name__)

COOKIE_TTL = 1500   # 25 min — Kasada tokens typically last 15-30 min

# domain → {"cookies": dict[str,str], "expires": float}
_cache: dict[str, dict] = {}


async def get_site_cookies(url: str) -> dict[str, str]:
    """
    Return a dict of cookies for the given URL's domain.

    Serves from cache when valid; otherwise launches a headless Chromium browser
    with playwright-stealth, navigates to the URL (solving any bot challenge),
    and returns the resulting cookies.
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


async def _fetch_via_playwright(url: str) -> dict[str, str]:
    """Launch Playwright, navigate to url, return the resulting cookies."""
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

    # Use headless=False locally so Kasada/Akamai JS challenges pass fingerprint checks.
    # On Railway (no display) we must stay headless — the challenge will likely fail there
    # but at least we get partial cookies.
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
                # Pretend to be a real desktop browser
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
                # Let Kasada / Akamai challenge JS run to completion.
                # Akamai sensor typically needs 3-8 seconds; Kasada up to 10.
                await asyncio.sleep(10)

                # Check if we got blocked even inside Playwright
                page_title = (await page.title()).lower()
                block_signals = ("access denied", "blocked", "robot", "captcha",
                                 "error", "403", "412", "unusual traffic")
                if any(s in page_title for s in block_signals):
                    log.warning(
                        "[CookieManager] *** IP-LEVEL BLOCK DETECTED *** "
                        "Playwright page title: '%s' — Railway's datacenter IP is "
                        "hard-blocked by %s's bot protection. Cookies will not help. "
                        "Solution: run this bot on a non-datacenter IP "
                        "(home machine, Hetzner VPS, or similar).",
                        await page.title(), urlparse(url).netloc,
                    )
                    await context.close()
                    await browser.close()
                    return {}

                raw = await context.cookies()
                cookies = {c["name"]: c["value"] for c in raw}
                log.debug("[CookieManager] Extracted %d cookies from %s", len(cookies), url)

                # Log challenge-solved cookies so we know what protection was passed
                kasada_keys = [k for k in cookies if "kpsdk" in k.lower() or "x-kpsdk" in k.lower()]
                akamai_keys = [k for k in cookies if any(s in k.lower() for s in
                               ("ak_bmsc", "bm_sz", "_abck", "bm_sv", "bm_mi"))]
                abck = "_abck" in cookies
                log.info("[CookieManager] All cookies for %s: %s", urlparse(url).netloc, list(cookies.keys()))
                if kasada_keys:
                    log.info("[CookieManager] Kasada cookies obtained: %s", kasada_keys)
                elif "footlocker" in url or "champssports" in url:
                    log.warning("[CookieManager] No Kasada cookies from %s — challenge failed or IP blocked", url)
                if akamai_keys:
                    log.info("[CookieManager] Akamai cookies obtained (abck=%s): %s", abck, akamai_keys)
                elif "walmart" in url:
                    log.warning("[CookieManager] No Akamai cookies from %s — challenge failed or IP blocked", url)

            except Exception as exc:
                log.warning("[CookieManager] Navigation failed for %s: %s", url, exc)
            finally:
                await context.close()
                await browser.close()

    except Exception as exc:
        log.warning("[CookieManager] Playwright launch error: %s", exc)

    return cookies