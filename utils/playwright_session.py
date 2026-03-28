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

    cookies: dict[str, str] = {}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
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
                # They typically finish within 2-3 seconds; wait a bit extra.
                await asyncio.sleep(5)

                raw = await context.cookies()
                cookies = {c["name"]: c["value"] for c in raw}
                log.debug("[CookieManager] Extracted %d cookies from %s", len(cookies), url)

                # Log Kasada-specific cookies so we know the challenge was solved
                kasada_keys = [k for k in cookies if "kpsdk" in k.lower() or "x-kpsdk" in k.lower()]
                akamai_keys = [k for k in cookies if "ak_bmsc" in k.lower() or "bm_sz" in k.lower()]
                if kasada_keys:
                    log.info("[CookieManager] Kasada cookies obtained: %s", kasada_keys)
                if akamai_keys:
                    log.info("[CookieManager] Akamai cookies obtained: %s", akamai_keys)

            except Exception as exc:
                log.warning("[CookieManager] Navigation failed for %s: %s", url, exc)
            finally:
                await context.close()
                await browser.close()

    except Exception as exc:
        log.warning("[CookieManager] Playwright launch error: %s", exc)

    return cookies