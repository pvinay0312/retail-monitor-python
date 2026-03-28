"""
Discord webhook client — sends rich embed messages.
Uses httpx directly (no discord.py needed) for lightweight webhook posting.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from config.settings import COOK_GROUP_NAME, COOK_GROUP_ICON_URL

log = logging.getLogger(__name__)

# Colours for each store
STORE_COLOURS = {
    "amazon":   0xFF9900,
    "bestbuy":  0x003B8E,
    "walmart":  0x0071CE,
    "target":   0xCC0000,
    "nike":     0x111111,
    "footsites": 0xE31837,
}

# Rate-limit: max 5 embeds / 2 s per webhook to stay under Discord's limits
_last_send: dict[str, float] = {}
_RATE_WINDOW = 2.0
_RATE_LIMIT  = 5


async def send_embed(
    webhook_url: str,
    *,
    title: str,
    url: str = "",
    description: str = "",
    store: str = "amazon",
    fields: Optional[list[dict]] = None,
    image_url: str = "",
    thumbnail_url: str = "",
    colour: Optional[int] = None,
) -> bool:
    """
    POST a Discord embed to webhook_url.
    Returns True on success.
    """
    if not webhook_url:
        log.warning("No webhook URL configured for %s — skipping alert.", store)
        return False

    colour = colour if colour is not None else STORE_COLOURS.get(store, 0x5865F2)

    embed: dict = {
        "title": title[:256],
        "color": colour,
        "timestamp": _iso_now(),
        "footer": {
            "text": COOK_GROUP_NAME,
            "icon_url": COOK_GROUP_ICON_URL or None,
        },
    }
    if url:
        embed["url"] = url
    if description:
        embed["description"] = description[:4096]
    if fields:
        embed["fields"] = fields[:25]
    if image_url:
        embed["image"] = {"url": image_url}
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}

    payload = {"embeds": [embed]}

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


# ── Pre-built embed helpers per store ─────────────────────────────────────────

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
    image: str = "",
    extra_fields: Optional[list[dict]] = None,
    is_freebie: bool = False,
) -> bool:
    if is_freebie:
        emoji = "🆓"
        title = f"🆓 FREEBIE — {name}"
        description = "@here **This item is FREE or near-free! Grab it before it's gone.**"
    elif coupon:
        emoji = "🎟️"
        title = f"🎟️ COUPON DEAL — {name}"
        description = f"**Clip the coupon before checkout:** `{coupon}`"
    else:
        emoji = "🔥"
        title = f"🔥 PRICE DROP — {name}"
        description = ""

    fields = [
        {"name": "💰 Sale Price",     "value": f"**{price}**",              "inline": True},
        {"name": "📦 Original Price", "value": f"~~{original_price}~~",     "inline": True},
        {"name": "📉 Savings",        "value": f"**{discount_pct}**",        "inline": True},
    ]
    if coupon:
        fields.append({"name": "🎟️ Coupon Code", "value": f"`{coupon}`", "inline": True})
    fields.append({"name": "🛒 Buy Now", "value": f"[Click here to purchase]({url})", "inline": False})
    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        description=description,
        store=store,
        fields=fields,
        image_url=image,
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
    fields = [
        {"name": "💰 Price", "value": f"**{price}**", "inline": True},
        {"name": "📊 Status", "value": "✅ **In Stock**", "inline": True},
        {"name": "🛒 Buy Now", "value": f"[Click here to purchase]({url})", "inline": False},
    ]
    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=f"🔔 RESTOCK — {name}",
        url=url,
        description="@here **Item is back in stock! Limited quantities available.**",
        store=store,
        fields=fields,
        image_url=image,
        colour=0x57F287,  # green
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
    stockx_query = name.replace(" ", "%20")
    stockx_url = f"https://stockx.com/search/sneakers?s={stockx_query}"

    if is_24h_reminder:
        hrs = int(hours_until)
        title = f"⏰ DROPPING IN ~{hrs}H — {name}"
        description = f"@here **This drop goes live in approximately {hrs} hour{'s' if hrs != 1 else ''}. Get ready!**"
    elif upcoming:
        title = f"📅 UPCOMING DROP — {name}"
        description = "@here **New drop announced on SNKRS! Mark your calendar.**"
    else:
        title = f"👟 LIVE NOW — {name}"
        description = "@here **Drop is LIVE on SNKRS! Enter now before it sells out.**"

    fields = [
        {"name": "💰 Retail Price",  "value": f"**{price}**",       "inline": True},
        {"name": "🔑 Style Code",    "value": f"`{style_code}`",     "inline": True},
    ]
    if drop_date:
        fields.append({"name": "📅 Release Date", "value": f"**{drop_date}**", "inline": False})
    if sizes:
        available = ", ".join(sizes[:20])
        fields.append({"name": f"📐 Available Sizes ({len(sizes)})", "value": available, "inline": False})
    fields.append({
        "name": "🔗 Links",
        "value": f"[Enter on SNKRS]({url})  •  [Check Resell on StockX]({stockx_url})",
        "inline": False,
    })

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        description=description,
        store="nike",
        fields=fields,
        image_url=image,
        colour=0x57F287 if not upcoming else 0xFEE75C,
    )
