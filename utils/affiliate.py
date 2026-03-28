"""
Amazon affiliate link generator.
Set AMAZON_AFFILIATE_TAG in Railway environment variables to earn
commissions on every purchase made through your deal links.

Example tag: solealerts-20
"""
import re
from config.settings import AMAZON_AFFILIATE_TAG


def make_affiliate_url(url: str) -> str:
    """Append or replace the Amazon Associates tag in any Amazon URL."""
    if not AMAZON_AFFILIATE_TAG or not url:
        return url
    if "amazon.com" not in url:
        return url
    # Strip any existing tag
    url = re.sub(r"[?&]tag=[^&]*", "", url).rstrip("?&")
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}tag={AMAZON_AFFILIATE_TAG}"


def asin_to_affiliate_url(asin: str) -> str:
    """Build a short affiliate URL directly from an ASIN."""
    if not AMAZON_AFFILIATE_TAG:
        return f"https://www.amazon.com/dp/{asin}"
    return f"https://www.amazon.com/dp/{asin}?tag={AMAZON_AFFILIATE_TAG}"
