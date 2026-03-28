"""
Anti-bot utilities: user-agent rotation and realistic browser headers.

Uses curl_cffi to get Chrome's real TLS fingerprint — significantly harder
to detect than requests/httpx because the TLS handshake matches Chrome byte-for-byte.
"""
import random
from curl_cffi.requests import AsyncSession

# A realistic pool of current Chrome / Edge / Firefox versions
# Keep these updated — bots using old browser versions are easier to fingerprint
USER_AGENTS = [
    # Chrome 133 on Windows (most common globally)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Chrome 133 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    # Chrome 131 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome 130 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Edge 133 on Windows (shares Chrome engine)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0",
    # Firefox 135 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    # Safari 18 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
]

# Matching sec-ch-ua values for Chrome UA strings (must stay in sync)
_SEC_CH_UA = {
    "133": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
    "131": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "130": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "edge":'"Not(A:Brand";v="99", "Microsoft Edge";v="133", "Chromium";v="133"',
    "other": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
}


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def base_headers(ua: str | None = None, referer: str = "https://www.google.com/") -> dict:
    """Return a realistic set of request headers for a given user-agent."""
    ua = ua or random_ua()
    # Pick matching sec-ch-ua brand string based on the UA version
    if "Edg/" in ua:
        sec_ch = _SEC_CH_UA["edge"]
        platform = '"Windows"'
    elif "133.0" in ua:
        sec_ch = _SEC_CH_UA["133"]
        platform = '"Windows"' if "Windows" in ua else '"macOS"'
    elif "131.0" in ua:
        sec_ch = _SEC_CH_UA["131"]
        platform = '"Windows"' if "Windows" in ua else '"macOS"'
    elif "130.0" in ua:
        sec_ch = _SEC_CH_UA["130"]
        platform = '"macOS"'
    else:
        sec_ch = _SEC_CH_UA["other"]
        platform = '"Windows"'

    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "sec-ch-ua": sec_ch,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": platform,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


def make_session(impersonate: str = "chrome120") -> AsyncSession:
    """
    Return an async curl_cffi session that impersonates Chrome's TLS fingerprint.
    This is the core anti-detection mechanism for sites that check JA3/JA4 hashes.
    """
    return AsyncSession(impersonate=impersonate)
