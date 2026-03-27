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
) -> bool:
    emoji = "🔥" if not coupon else "🎟️"
    title = f"{emoji} {name}"
    description = ""
    if coupon:
        description = f"**Coupon code:** `{coupon}`"

    fields = [
        {"name": "💰 Price",    "value": price,          "inline": True},
        {"name": "~~Was~~",     "value": f"~~{original_price}~~", "inline": True},
        {"name": "📉 Off",      "value": discount_pct,   "inline": True},
    ]
    if coupon:
        fields.append({"name": "🎟️ Coupon", "value": f"`{coupon}`", "inline": True})
    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        description=description,
        store=store,
        fields=fields,
        thumbnail_url=image,
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
    fields = [{"name": "💰 Price", "value": price, "inline": True}]
    if extra_fields:
        fields.extend(extra_fields)

    return await send_embed(
        webhook_url,
        title=f"🔔 Back in Stock — {name}",
        url=url,
        store=store,
        fields=fields,
        thumbnail_url=image,
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
) -> bool:
    title = f"{'📅' if upcoming else '👟'} {'Upcoming' if upcoming else 'LIVE'} — {name}"
    fields = [
        {"name": "💰 Retail",    "value": price,      "inline": True},
        {"name": "🔑 Style",     "value": style_code, "inline": True},
    ]
    if sizes:
        fields.append({"name": "📐 Sizes", "value": ", ".join(sizes[:20]), "inline": False})

    return await send_embed(
        webhook_url,
        title=title,
        url=url,
        store="nike",
        fields=fields,
        thumbnail_url=image,
        colour=0x57F287 if not upcoming else 0xFEE75C,
    )
