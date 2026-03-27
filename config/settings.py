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

# ── Browser ───────────────────────────────────────────────────────────────────
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "")   # leave blank for Playwright default

# ── Monitor intervals (seconds) ───────────────────────────────────────────────
AMAZON_INTERVAL    = int(os.getenv("AMAZON_INTERVAL",    "300"))   # 5 min
BESTBUY_INTERVAL   = int(os.getenv("BESTBUY_INTERVAL",   "180"))   # 3 min
WALMART_INTERVAL   = int(os.getenv("WALMART_INTERVAL",   "300"))   # 5 min
TARGET_INTERVAL    = int(os.getenv("TARGET_INTERVAL",    "300"))   # 5 min
FOOTSITES_INTERVAL = int(os.getenv("FOOTSITES_INTERVAL", "600"))   # 10 min
NIKE_INTERVAL      = int(os.getenv("NIKE_INTERVAL",      "120"))   # 2 min
