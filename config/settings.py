"""Centralised config loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord webhooks ──────────────────────────────────────────────────────────
AMAZON_WEBHOOK_URL      = os.getenv("AMAZON_WEBHOOK_URL", "")
BESTBUY_WEBHOOK_URL     = os.getenv("BESTBUY_WEBHOOK_URL", "")
WALMART_WEBHOOK_URL     = os.getenv("WALMART_WEBHOOK_URL", "")
TARGET_WEBHOOK_URL      = os.getenv("TARGET_WEBHOOK_URL", "")
FOOTSITES_WEBHOOK_URL   = os.getenv("FOOTSITES_WEBHOOK_URL", "")
NIKE_SNKRS_WEBHOOK_URL  = os.getenv("NIKE_SNKRS_WEBHOOK_URL", "")
UPCOMING_DROPS_WEBHOOK_URL = os.getenv(
    "UPCOMING_DROPS_WEBHOOK_URL", os.getenv("NIKE_SNKRS_WEBHOOK_URL", "")
)

# ── Branding ──────────────────────────────────────────────────────────────────
COOK_GROUP_NAME     = os.getenv("COOK_GROUP_NAME", "Deal Monitor")
COOK_GROUP_ICON_URL = os.getenv("COOK_GROUP_ICON_URL", "")

# ── Affiliate ─────────────────────────────────────────────────────────────────
# Set this in Railway variables to earn Amazon Associates commissions.
# Example: AMAZON_AFFILIATE_TAG=solealerts-20
AMAZON_AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")

# ── Deal scoring ──────────────────────────────────────────────────────────────
# Minimum score (0-100) required before posting a deal alert.
# Raise this to post fewer but better deals. Lower to post more.
DEAL_MIN_SCORE = int(os.getenv("DEAL_MIN_SCORE", "40"))

# ── Browser ───────────────────────────────────────────────────────────────────
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "")   # leave blank for Playwright default

# ── Monitor intervals (seconds) ───────────────────────────────────────────────
# Nike/BestBuy are fastest because drops sell out in seconds/minutes.
# Walmart/Amazon/Target scrape individual pages so stay slower to avoid blocks.
AMAZON_INTERVAL    = int(os.getenv("AMAZON_INTERVAL",    "240"))   # 4 min
BESTBUY_INTERVAL   = int(os.getenv("BESTBUY_INTERVAL",    "60"))   # 60s — batch API, low ban risk
WALMART_INTERVAL   = int(os.getenv("WALMART_INTERVAL",   "180"))   # 3 min — Akamai protection, don't go lower
TARGET_INTERVAL    = int(os.getenv("TARGET_INTERVAL",    "240"))   # 4 min
FOOTSITES_INTERVAL = int(os.getenv("FOOTSITES_INTERVAL", "300"))   # 5 min — heavy Playwright requests
NIKE_INTERVAL      = int(os.getenv("NIKE_INTERVAL",       "45"))   # 45s — JSON API, drops have 10-30min window
WOOT_INTERVAL      = int(os.getenv("WOOT_INTERVAL",       "180"))  # 3 min — Woot-Offs can sell out in seconds

# ── Woot webhook (defaults to Amazon channel since Woot is Amazon-owned) ──────
WOOT_WEBHOOK_URL = os.getenv("WOOT_WEBHOOK_URL", os.getenv("AMAZON_WEBHOOK_URL", ""))
