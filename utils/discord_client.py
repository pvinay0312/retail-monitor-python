"""
Discord webhook client — sends rich embeds in the style of professional cook groups.

Design principles (matching industry standard monitors):
  • @here goes in the plain-text `content` field ABOVE the embed, not inside it
    (Discord only parses mentions in content, not embed fields/descriptions)
  • Author line  = store name + store favicon — instant retailer recognition
  • Thumbnail    = product image (top-right corner) — clean, not giant footer image
  • Title        = alert type prefix + product name — bold, clickable, links to product
  • Fields       = 3-wide inline grid: Price | Original | Savings, then extras
  • Color        = alert-type driven (green=restock, orange=deal, gold=coupon, black=Nike)
  • Footer       = cook group name + ISO timestamp
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from config.settings import COOK_GROUP_NAME, COOK_GROUP_ICON_URL

log = logging.getLogger(__name__)

# ── Startup grace period ──────────────────────────────────────────────────────
# Every Railway redeploy wipes data/, resetting all cooldowns to zero. Without
# a grace window the first cycle after deploy floods every channel with ~50
# re-alerts for items already seen.
#
# Solution: suppress all Discord POSTs for 10 min after process start.
# Monitors still run and write cooldown timestamps — so by the time the grace
# window ends, every previously-seen item has a fresh cooldown and won't fire.
_STARTUP_TIME          = time.time()
_STARTUP_GRACE_SECONDS = 600          # 10 minutes
_grace_logged          = False


def _in_startup_grace() -> bool:
    return (time.time() - _STARTUP_TIME) < _STARTUP_GRACE_SECONDS


# ── Store metadata ─────────────────────────────────────────────────────────────
# brand_colour  = left-border accent on neutral/info embeds
# favicon       = small icon shown in author line (loaded from store's CDN)

_STORE_META: dict[str, dict] = {
    "amazon":    {"colour": 0xFF9900, "label": "Amazon",   "favicon": "https://www.amazon.com/favicon.ico"},
    "bestbuy":   {"colour": 0x003B8E, "label": "Best Buy", "favicon": "https://www.bestbuy.com/favicon.ico"},
    "walmart":   {"colour": 0x0071CE, "label": "Walmart",  "favicon": "https://www.walmart.com/favicon.ico"},
    "target":    {"colour": 0xCC0000, "label": "Target",   "favicon": "https://www.target.com/favicon.ico"},
    "nike":      {"colour": 0x111111, "label": "Nike SNKRS","favicon": "https://www.nike.com/favicon.ico"},
    "footsites": {"colour": 0xE31837, "label": "Foot Locker","favicon": "https://www.footlocker.com/favicon.ico"},
    "woot":      {"colour": 0x00A0AE, "label": "Woot!",    "favicon": "https://www.woot.com/favicon.ico"},
}

# ── Alert-type colours (override store colour when alert type is known) ────────
COLOUR_DEAL     = 0xFF9500   # Orange  — price drop
COLOUR_COUPON   = 0xFEE75C   # Gold    — coupon / promo code
COLOUR_FREEBIE  = 0x57F287   # Green   — free item
COLOUR_RESTOCK  = 0x57F287   # Green   — back in stock
COLOUR_UPCOMING = 0xFEE75C   # Gold    — upcoming drop
COLOUR_LIVE     = 0xED4245   # Red     — live now (Nike drop)


def _store_meta(store: str) -> dict:
    return _STORE_META.get(store.lower(), {"colour": 0x5865F2, "label": store.title(), "favicon": ""})


async def send_embed(
    webhook_url: str,
    *,
    title: str,
    url: str = "",
    description: str = "",
    store: str = "amazon",
    fields: Optional[list[dict]] = None,
    thumbnail_url: str = "",
    colour: Optional[int] = None,
    mention: str = "@here",
    alert_type: str = "",        # shown in author line: "Price Drop", "Restock", etc.
    image_url: str = "",         # kept for backwards-compat; mapped to thumbnail if no thumb set
) -> bool:
    """POST a Discord embed to webhook_url. Returns True on success."""
    if not webhook_url:
        log.warning("No webhook URL configured for %s — skipping alert.", store)
        return False

    global _grace_logged
    if _in_startup_grace():
        remaining = int(_STARTUP_GRACE_SECONDS - (time.time() - _STARTUP_TIME))
        if not _grace_logged:
            log.info(
                "[Discord] Startup grace period active (%ds) — "
                "suppressing alerts until cooldown state is rebuilt after deploy.",
                _STARTUP_GRACE_SECONDS,
            )
            _grace_logged = True
        log.debug("[Discord] Grace suppressed: %s (%ds remaining)", title[:60], remaining)
        return True  # pretend success so notify.json timestamps are written

    meta   = _store_meta(store)
    colour = colour if colour is not None else meta["colour"]

    # Author line: "Amazon Monitor • Price Drop"
    author_name = meta["label"] + " Monitor"
    if alert_type:
        author_name += f"  ·  {alert_type}"

    embed: dict = {
        "author": {
            "name":     author_name,
            "icon_url": meta["favicon"] or (COOK_GROUP_ICON_URL or None),
        },
        "title":  title[:256],
        "color":  colour,
        "timestamp": _iso_now(),
        "footer": {
            "text":     COOK_GROUP_NAME,
            "icon_url": COOK_GROUP_ICON_URL or None,
        },
    }
    if url:
        embed["url"] = url
    if description:
        embed["description"] = description[:4096]
    if fields:
        embed["fields"] = fields[:25]

    # Thumbnail (top-right, small) — preferred over full-width image for clean layout
    thumb = thumbnail_url or image_url
    if thumb:
        embed["thumbnail"] = {"url": thumb}

    # @here / @everyone goes in `content` (plain text above embed) — Discord
    # only parses mentions in content, not inside embed fields or descriptions.
    content = mention if mention else ""

    payload: dict = {"embeds": [embed]}
    if content:
        payload["content"] = content

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(webhook_url, json=payload)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                log.warning("Discord rate-limited — sleeping %.1fs", retry_after)
                await asyncio.sleep(float(retry_after))
                continue
            log.error("Discord webhook error %d: %s", resp.status_code, resp.text[:200])
            return False
        except httpx.HTTPError as exc:
            log.warning("Discord send attempt %d failed: %s", attempt + 1, exc)
            await asyncio.sleep(2 ** attempt)
    return False


def _iso_now() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Alert helpers ──────────────────────────────────────────────────────────────

async def send_deal_alert(
    webhook_url: str,
    *,
    store: str,
    name: str,
    url: str,
    price: str,
    original_price: str,
    discount_pct: str,
    coupon: str = "",
    is_promo_code: bool = False,
    image: str = "",
    extra_fields: Optional[list[dict]] = None,
    is_freebie: bool = False,
) -> bool:
    pct_label = f" {discount_pct.upper()}" if discount_pct and discount_pct != "N/A" else ""
    meta = _store_meta(store)

    if is_freebie:
        title      = f"🆓 FREE — {name}"
        colour     = COLOUR_FREEBIE
        alert_type = "🆓 Free Item"
        mention    = "@here"
    elif coupon and is_promo_code:
        title      = f"🏷️ PROMO CODE{pct_label} — {name}"
        colour     = COLOUR_COUPON
        alert_type = f"🏷️ Promo Code{pct_label}"
        mention    = "@here"
    elif coupon:
        title      = f"🎟️ CLIP COUPON{pct_label} — {name}"
        colour     = COLOUR_COUPON
        alert_type = f"🎟️ Coupon{pct_label}"
        mention    = "@here"
    else:
        title      = f"🔥 PRICE DROP{pct_label} — {name}"
        colour     = COLOUR_DEAL
        alert_type = f"🔥 Price Drop{pct_label}"
        mention    = "@here"

    fields = [
        {"name": "💰 Sale Price",     "value": f"**{price}**",          "inline": True},
        {"name": "📦 Original Price", "value": f"~~{original_price}~~", "inline": True},
        {"name": "📉 Savings",        "value": f"**{discount_pct}**",   "inline": True},
        {"name": "🏪 Store",          "value": meta["label"],           "inline": True},
        {"name": "🛒 Buy Now",        "value": f"[Buy Now →]({url})",   "inline": True},
    ]

    if coupon and is_promo_code:
        fields.append({
            "name":   "🏷️ Promo Code — copy & paste at checkout",
            "value":  f"```\n{coupon}\n```",
            "inline": False,
        })
    elif coupon:
        fields.append({
            "name":   "🎟️ Coupon",
            "value":  f"**{coupon}** — clip on the product page before checkout",
            "inline": False,
        })

    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        store=store,
        fields=fields,
        thumbnail_url=image,
        colour=colour,
        alert_type=alert_type,
        mention=mention,
    )


async def send_restock_alert(
    webhook_url: str,
    *,
    store: str,
    name: str,
    url: str,
    price: str,
    image: str = "",
    extra_fields: Optional[list[dict]] = None,
) -> bool:
    meta   = _store_meta(store)
    fields = [
        {"name": "💰 Price",   "value": f"**{price}**",           "inline": True},
        {"name": "📊 Status",  "value": "✅ **Back In Stock**",   "inline": True},
        {"name": "🏪 Store",   "value": meta["label"],            "inline": True},
        {"name": "🛒 Buy Now", "value": f"[Buy Now →]({url})",    "inline": False},
    ]
    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=f"🔔 RESTOCK — {name}",
        url=url,
        store=store,
        fields=fields,
        thumbnail_url=image,
        colour=COLOUR_RESTOCK,
        alert_type="🔔 Restock",
        mention="@here",
    )


async def send_nike_drop(
    webhook_url: str,
    *,
    name: str,
    url: str,
    price: str,
    sizes: list[str],
    style_code: str,
    image: str = "",
    upcoming: bool = False,
    drop_date: str = "",
    is_24h_reminder: bool = False,
    hours_until: float = 0,
) -> bool:
    stockx_url = f"https://stockx.com/search/sneakers?s={name.replace(' ', '%20')}"

    if is_24h_reminder:
        hrs        = int(hours_until)
        title      = f"⏰ DROPPING IN ~{hrs}H — {name}"
        colour     = COLOUR_UPCOMING
        alert_type = f"⏰ Dropping in ~{hrs}h"
        mention    = "@here"
    elif upcoming:
        title      = f"📅 UPCOMING DROP — {name}"
        colour     = COLOUR_UPCOMING
        alert_type = "📅 Upcoming Drop"
        mention    = ""          # no ping for far-future announcements
    else:
        title      = f"👟 LIVE NOW — {name}"
        colour     = COLOUR_LIVE
        alert_type = "👟 Live Drop"
        mention    = "@here"

    fields = [
        {"name": "💰 Retail Price", "value": f"**{price}**",   "inline": True},
        {"name": "🔑 Style Code",   "value": f"`{style_code}`", "inline": True},
    ]
    if drop_date:
        fields.append({"name": "📅 Release Date", "value": f"**{drop_date}**", "inline": True})
    if sizes:
        fields.append({
            "name":   f"📐 Available Sizes ({len(sizes)})",
            "value":  ", ".join(sizes[:20]),
            "inline": False,
        })
    fields.append({
        "name":   "🔗 Links",
        "value":  f"[Enter on SNKRS]({url})  •  [Resell on StockX]({stockx_url})",
        "inline": False,
    })

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        store="nike",
        fields=fields,
        thumbnail_url=image,
        colour=colour,
        alert_type=alert_type,
        mention=mention,
    )