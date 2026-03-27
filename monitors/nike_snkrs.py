"""
Nike SNKRS monitor — two complementary strategies:

1. Live feed monitor: polls the SNKRS feed API every cycle and fires an alert
   for any newly-available drop (status STOCKED / DAN / HOLD / CLOSEOUT).

2. Style-code watchlist: separately tracks specific style codes from
   config/products.py for restocks / availability changes.

API endpoints:
  Primary:  rollup_threads/v2  (works on Railway)
  Fallback: threads/v2
"""
import asyncio
import logging
import time

from config.products import NIKE_STYLE_CODES, SNKRS_CHANNEL_ID
from config.settings import NIKE_SNKRS_WEBHOOK_URL, UPCOMING_DROPS_WEBHOOK_URL, NIKE_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_nike_drop
from utils.storage import load, save

log = logging.getLogger(__name__)

NOTIFY_COOLDOWN = 30 * 60   # 30 min per product

AVAILABLE_STATUSES  = {"STOCKED", "DAN", "HOLD", "CLOSEOUT"}
UPCOMING_STATUSES   = {"PRODUCT_HOLD", "SCHEDULED", "COMING_SOON", "INACTIVE"}

FEED_URL_ROLLUP = (
    "https://api.nike.com/product_feed/rollup_threads/v2"
    f"?filter=marketplace(US)&filter=language(en)"
    f"&filter=channelId({SNKRS_CHANNEL_ID})&count=50"
)
FEED_URL_THREADS = (
    "https://api.nike.com/product_feed/threads/v2"
    f"?filter=marketplace(US)&filter=language(en)"
    f"&filter=channelId({SNKRS_CHANNEL_ID})&count=50"
)

_SEEN   = "nike_seen.json"
_STATUS = "nike_status.json"
_NOTIFY = "nike_notify.json"


class NikeSnkrsMonitor(BaseMonitor):
    name = "Nike SNKRS"
    interval = NIKE_INTERVAL

    async def check(self) -> None:
        seen   = await load(_SEEN)
        status = await load(_STATUS)
        notify = await load(_NOTIFY)

        session = make_session("chrome110")   # Nike API works fine with Chrome 110
        try:
            objects = await self._fetch_feed(session)
            if objects:
                await self._process_feed(objects, seen, status, notify)

            await self._check_watchlist(session, status, notify)
        finally:
            await session.close()

        await save(_SEEN,   seen)
        await save(_STATUS, status)
        await save(_NOTIFY, notify)

    # ── Feed polling ──────────────────────────────────────────────────────────

    async def _fetch_feed(self, session) -> list:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.nike.com/")
        headers["Accept"] = "application/json"

        for feed_url in (FEED_URL_ROLLUP, FEED_URL_THREADS):
            try:
                resp = await session.get(feed_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("objects", [])
                log.debug("[Nike] Feed URL returned %d: %s", resp.status_code, feed_url)
            except Exception as exc:
                log.debug("[Nike] Feed error (%s): %s", feed_url, exc)
        return []

    async def _process_feed(self, objects, seen, status, notify) -> None:
        for obj in objects:
            thread = obj if "publishedContent" in obj else obj.get("productInfo", [{}])[0]
            # Extract from rollup_threads structure
            publish = obj.get("publishedContent", {})
            nodes   = publish.get("nodes", [])
            props   = publish.get("properties", {})

            product_id = obj.get("id", "")
            launch_type = props.get("launchType", "")
            launch_view = props.get("launchView", {}).get("status", "")
            title = props.get("title") or props.get("subtitle") or "Unknown Drop"

            # Extract from productInfo array (threads/v2 structure)
            product_infos = obj.get("productInfo", [])
            if not product_infos and "channel_id" in obj:
                # threads/v2: thread object itself
                product_infos = [obj]

            for pi in product_infos:
                style = pi.get("merchProduct", {}).get("styleColor", "").replace("/", "-")
                launch_status = (
                    pi.get("launchView", {}).get("status")
                    or pi.get("merchProduct", {}).get("status")
                    or launch_view
                    or ""
                ).upper()
                price = pi.get("merchPrice", {}).get("currentRetail", 0)
                currency = pi.get("merchPrice", {}).get("currency", "USD")
                skus = pi.get("skus") or pi.get("availableSkus") or []
                sizes = _extract_sizes(skus)
                image = _extract_image(pi)
                product_url = f"https://www.nike.com/launch/t/{style.lower()}" if style else "https://www.nike.com/launch"

                key = style or product_id
                prev = status.get(key, "")
                on_cool = (time.time() - notify.get(key, 0)) < NOTIFY_COOLDOWN

                if launch_status in AVAILABLE_STATUSES and not on_cool and prev not in AVAILABLE_STATUSES:
                    price_str = f"${price:.0f}" if price else "N/A"
                    log.info("[Nike SNKRS] LIVE DROP: %s | %s | %s", title, style, price_str)
                    await send_nike_drop(
                        NIKE_SNKRS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style, image=image,
                        upcoming=False,
                    )
                    notify[key] = time.time()

                elif launch_status in UPCOMING_STATUSES and key not in seen:
                    price_str = f"${price:.0f}" if price else "N/A"
                    log.info("[Nike SNKRS] UPCOMING: %s | %s", title, style)
                    await send_nike_drop(
                        UPCOMING_DROPS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style, image=image,
                        upcoming=True,
                    )
                    seen[key] = True

                status[key] = launch_status

    # ── Watchlist ─────────────────────────────────────────────────────────────

    async def _check_watchlist(self, session, status, notify) -> None:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.nike.com/")
        headers["Accept"] = "application/json"

        for style_code in NIKE_STYLE_CODES:
            await asyncio.sleep(0.5)
            style_clean = style_code.replace("-", "")
            api_url = (
                f"https://api.nike.com/product_feed/threads/v2"
                f"?filter=marketplace(US)&filter=language(en)"
                f"&filter=styleColor({style_code})&count=1"
            )
            try:
                resp = await session.get(api_url, headers=headers, timeout=12)
                if resp.status_code != 200:
                    continue
                objects = resp.json().get("objects", [])
                if not objects:
                    continue

                obj = objects[0]
                product_infos = obj.get("productInfo", []) or [obj]
                for pi in product_infos:
                    launch_status = (
                        pi.get("launchView", {}).get("status")
                        or pi.get("merchProduct", {}).get("status", "")
                    ).upper()
                    price = pi.get("merchPrice", {}).get("currentRetail", 0)
                    skus  = pi.get("skus") or pi.get("availableSkus") or []
                    sizes = _extract_sizes(skus)
                    image = _extract_image(pi)
                    title = (pi.get("productContent", {}).get("fullTitle")
                             or obj.get("publishedContent", {}).get("properties", {}).get("title")
                             or style_code)
                    product_url = f"https://www.nike.com/launch/t/{style_code.lower()}"

                    prev = status.get(style_code, "")
                    on_cool = (time.time() - notify.get(style_code, 0)) < NOTIFY_COOLDOWN

                    if launch_status in AVAILABLE_STATUSES and not on_cool and prev not in AVAILABLE_STATUSES:
                        price_str = f"${price:.0f}" if price else "N/A"
                        log.info("[Nike SNKRS] WATCHLIST HIT: %s | %s", style_code, title)
                        await send_nike_drop(
                            NIKE_SNKRS_WEBHOOK_URL,
                            name=title, url=product_url,
                            price=price_str, sizes=sizes,
                            style_code=style_code, image=image,
                            upcoming=False,
                        )
                        notify[style_code] = time.time()

                    status[style_code] = launch_status

            except Exception as exc:
                log.debug("[Nike] Watchlist error %s: %s", style_code, exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_sizes(skus: list) -> list[str]:
    sizes = []
    for sku in skus:
        nl = sku.get("nikeSize") or sku.get("localizedSize") or sku.get("countrySpecifications", [{}])[0].get("localizedSize", "")
        avail = sku.get("availabilityStatus", "").upper()
        if nl and avail in ("IN_STOCK", "ACTIVE", "STOCKED"):
            sizes.append(nl)
    return sorted(set(sizes), key=lambda s: _size_sort_key(s))


def _size_sort_key(s: str) -> float:
    import re
    m = re.search(r"[\d.]+", s)
    return float(m.group()) if m else 99


def _extract_image(pi: dict) -> str:
    try:
        content = pi.get("productContent", {})
        imgs = content.get("colorwayImages", {})
        return imgs.get("portraitURL", "") or imgs.get("squarishURL", "")
    except Exception:
        return ""
