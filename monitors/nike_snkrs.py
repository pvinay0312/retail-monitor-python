"""
Nike SNKRS monitor — two complementary strategies:

1. Live feed monitor: polls the SNKRS feed API every cycle and fires an alert
   for any newly-available drop (status STOCKED / DAN / HOLD / CLOSEOUT).

2. Style-code watchlist: separately tracks specific style codes from
   config/products.py for restocks / availability changes.

3. Day-before reminder: saves upcoming drop times and sends a @here alert
   24 hours before each drop so members can prepare.

4. Auto-discovery: new style codes found in the feed are saved automatically
   to nike_auto_styles.json and monitored on future cycles.

API endpoints:
  Primary:  rollup_threads/v2  (works on Railway)
  Fallback: threads/v2
"""
import datetime
import logging
import time

from config.products import NIKE_STYLE_CODES, SNKRS_CHANNEL_ID
from config.settings import NIKE_SNKRS_WEBHOOK_URL, UPCOMING_DROPS_WEBHOOK_URL, NIKE_INTERVAL
from monitors.base import BaseMonitor
from utils.anti_bot import make_session, base_headers, random_ua
from utils.discord_client import send_nike_drop
from utils.storage import load, save

log = logging.getLogger(__name__)

NOTIFY_COOLDOWN = 4 * 3600  # 4 hours — notify once per drop, not every cycle

# ACTIVE is intentionally excluded here: Nike uses ACTIVE for both upcoming entry
# windows (draw open, future drop date) and same-day live drops.
# Date-based logic in _is_upcoming() and _is_live() handles this correctly.
AVAILABLE_STATUSES  = {"STOCKED", "DAN", "CLOSEOUT", "IN_STOCK"}
UPCOMING_STATUSES   = {
    "PRODUCT_HOLD", "SCHEDULED", "COMING_SOON", "INACTIVE",
    "EXCLUSIVE_ACCESS", "HOLD", "PUBLISH", "DRAFT",
}

# threads/v2 is the primary endpoint — rollup_threads/v2 often returns 0 objects
# count=100 to maximize coverage for client-side watchlist filtering
FEED_URL_THREADS = (
    "https://api.nike.com/product_feed/threads/v2"
    f"?filter=marketplace(US)&filter=language(en)"
    f"&filter=channelId({SNKRS_CHANNEL_ID})&count=100"
)
FEED_URL_ROLLUP = (
    "https://api.nike.com/product_feed/rollup_threads/v2"
    f"?filter=marketplace(US)&filter=language(en)"
    f"&filter=channelId({SNKRS_CHANNEL_ID})&count=100"
)

_SEEN           = "nike_seen.json"
_STATUS         = "nike_status.json"
_NOTIFY         = "nike_notify.json"
_DROPS          = "nike_drops.json"          # upcoming drops for 24h reminders
_UPCOMING_SEEN  = "nike_upcoming_seen.json"  # dedup for upcoming alerts (separate from drops)
_AUTO_STYLES    = "nike_auto_styles.json"    # auto-discovered style codes


class NikeSnkrsMonitor(BaseMonitor):
    name = "Nike SNKRS"
    interval = NIKE_INTERVAL

    def __init__(self):
        super().__init__()
        if NIKE_SNKRS_WEBHOOK_URL:
            log.info("[Nike SNKRS] Webhook URL: CONFIGURED (%d chars)", len(NIKE_SNKRS_WEBHOOK_URL))
        else:
            log.error("[Nike SNKRS] *** NIKE_SNKRS_WEBHOOK_URL IS NOT SET — NO NOTIFICATIONS WILL FIRE ***")

    async def check(self) -> None:
        seen          = await load(_SEEN)
        status        = await load(_STATUS)
        notify        = await load(_NOTIFY)
        drops         = await load(_DROPS)
        upcoming_seen = await load(_UPCOMING_SEEN)
        auto_styles   = await load(_AUTO_STYLES)

        session = make_session("chrome110")
        try:
            objects = await self._fetch_feed(session)
            # Snapshot of status BEFORE this cycle's updates — used for transition detection
            prev_statuses = dict(status)
            if objects:
                await self._process_feed(objects, seen, status, notify, drops, upcoming_seen, auto_styles, prev_statuses)

            # Watchlist: filter the already-fetched feed objects client-side instead of
            # making individual API calls (Nike's filter=styleColor() is now INVALID_FILTER_FIELD)
            all_styles = list(set(NIKE_STYLE_CODES + list(auto_styles.keys())))
            await self._check_watchlist(objects, status, prev_statuses, notify, drops, upcoming_seen, auto_styles, all_styles)

            await self._send_day_before_reminders(drops, notify)
        finally:
            await session.close()

        await save(_SEEN,          seen)
        await save(_STATUS,        status)
        await save(_NOTIFY,        notify)
        await save(_DROPS,         drops)
        await save(_UPCOMING_SEEN, upcoming_seen)
        await save(_AUTO_STYLES,   auto_styles)

    # ── Feed polling ──────────────────────────────────────────────────────────

    async def _fetch_feed(self, session) -> list:
        ua = random_ua()
        headers = base_headers(ua, referer="https://www.nike.com/")
        headers["Accept"] = "application/json"

        for feed_url in (FEED_URL_THREADS, FEED_URL_ROLLUP):
            try:
                resp = await session.get(feed_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("objects", [])
                log.debug("[Nike] Feed URL returned %d: %s", resp.status_code, feed_url)
            except Exception as exc:
                log.debug("[Nike] Feed error (%s): %s", feed_url, exc)
        return []

    async def _process_feed(self, objects, seen, status, notify, drops, upcoming_seen, auto_styles, prev_statuses) -> None:
        for obj in objects:
            publish = obj.get("publishedContent", {})
            props   = publish.get("properties", {})

            product_id  = obj.get("id", "")
            title       = props.get("title") or props.get("subtitle") or "Unknown Drop"
            launch_view = props.get("launchView", {})

            product_infos = obj.get("productInfo") or []
            if not product_infos:
                product_infos = [obj]

            for pi in product_infos:
                style = pi.get("merchProduct", {}).get("styleColor", "").replace("/", "-")
                launch_status = (
                    pi.get("launchView", {}).get("status")
                    or pi.get("merchProduct", {}).get("status")
                    or launch_view.get("status", "")
                    or ""
                ).upper()
                mp       = pi.get("merchPrice", {})
                price    = mp.get("currentPrice") or mp.get("currentRetail") or mp.get("fullPrice") or 0
                skus     = pi.get("skus") or pi.get("availableSkus") or []
                sizes    = _extract_sizes(skus)
                image    = _extract_image(pi, props)
                key      = style or product_id
                price_str = f"${price:.0f}" if price else "N/A"
                seo_slug  = props.get("seo", {}).get("slug", "")
                product_url = (
                    f"https://www.nike.com/launch/t/{seo_slug}" if seo_slug
                    else f"https://www.nike.com/launch/t/{style.lower()}" if style
                    else "https://www.nike.com/launch"
                )

                # Auto-save newly discovered style codes
                if style and style not in auto_styles:
                    auto_styles[style] = {"title": title, "discovered": _iso_now()}
                    log.info("[Nike SNKRS] Auto-discovered style code: %s — %s", style, title)

                prev_status   = prev_statuses.get(key, "")
                was_prev_live = prev_status in (AVAILABLE_STATUSES | {"ACTIVE"})
                on_cool       = (time.time() - notify.get(key, 0)) < NOTIFY_COOLDOWN
                is_live       = _is_live(launch_status, pi, props)

                # Only fire when transitioning from non-live → live (prevents re-pinging
                # items that stay ACTIVE/STOCKED across cycles once cooldown expires)
                if is_live and not was_prev_live and not on_cool:
                    log.info("[Nike SNKRS] LIVE DROP: %s | %s | %s", title, style, price_str)
                    await send_nike_drop(
                        NIKE_SNKRS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style, image=image,
                        upcoming=False,
                    )
                    notify[key] = time.time()

                elif _is_upcoming(launch_status, pi, props) and key not in upcoming_seen:
                    drop_date_str = _extract_drop_date(pi, props)
                    drop_ts       = _extract_drop_timestamp(pi, props)
                    log.info("[Nike SNKRS] UPCOMING (feed): %s | %s | status=%s | drop=%s",
                             title, style, launch_status, drop_date_str or "TBA")
                    await send_nike_drop(
                        UPCOMING_DROPS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style, image=image,
                        upcoming=True,
                        drop_date=drop_date_str,
                    )
                    upcoming_seen[key] = True
                    seen[key] = True
                    drops[key] = {
                        "title": title, "url": product_url, "price": price_str,
                        "image": image, "style_code": style,
                        "drop_date_str": drop_date_str, "drop_ts": drop_ts,
                        "reminded_24h": False,
                    }

                status[key] = launch_status

    # ── Watchlist ─────────────────────────────────────────────────────────────

    async def _check_watchlist(self, objects: list, status, prev_statuses, notify, drops, upcoming_seen, _auto_styles, all_styles) -> None:
        """
        Client-side watchlist: filter already-fetched feed objects by style code.

        Nike's API dropped support for filter=styleColor(...) — it now returns
        INVALID_FILTER_FIELD. We fetch count=100 from the feed and match style codes
        client-side instead of making one broken API call per style code.
        """
        # Build a map: style_code → list of (obj, pi) pairs from the feed
        feed_by_style: dict[str, list[tuple]] = {}
        for obj in objects:
            publish = obj.get("publishedContent", {})
            props   = publish.get("properties", {})
            product_infos = obj.get("productInfo", []) or [obj]
            for pi in product_infos:
                style = pi.get("merchProduct", {}).get("styleColor", "").replace("/", "-").upper()
                if style:
                    feed_by_style.setdefault(style, []).append((obj, pi, props))

        log.debug("[Nike SNKRS] Feed style codes: %s", list(feed_by_style.keys()))

        for style_code in all_styles:
            style_upper = style_code.upper()
            matches = feed_by_style.get(style_upper, [])

            if not matches:
                log.info("[Nike SNKRS] Watchlist %s → not in feed this cycle (may be sold out or upcoming)", style_code)
                continue

            for obj, pi, props in matches:
                launch_status = (
                    pi.get("launchView", {}).get("status")
                    or pi.get("merchProduct", {}).get("status", "")
                    or ""
                ).upper()
                mp       = pi.get("merchPrice", {})
                price    = mp.get("currentPrice") or mp.get("currentRetail") or mp.get("fullPrice") or 0
                skus     = pi.get("skus") or pi.get("availableSkus") or []
                sizes    = _extract_sizes(skus)
                image    = _extract_image(pi, props)
                title    = (
                    pi.get("productContent", {}).get("fullTitle")
                    or props.get("title")
                    or style_code
                )
                price_str = f"${price:.0f}" if price else "N/A"
                seo_slug  = props.get("seo", {}).get("slug", "")
                product_url = (
                    f"https://www.nike.com/launch/t/{seo_slug}" if seo_slug
                    else f"https://www.nike.com/launch/t/{style_code.lower()}"
                )

                prev_status   = prev_statuses.get(style_code, "")
                was_prev_live = prev_status in (AVAILABLE_STATUSES | {"ACTIVE"})
                on_cool       = (time.time() - notify.get(style_code, 0)) < NOTIFY_COOLDOWN

                log.info("[Nike SNKRS] Watchlist %s | %s | status=%s | sizes=%d",
                         style_code, title[:50], launch_status or "UNKNOWN", len(sizes))

                is_live = _is_live(launch_status, pi, props)
                if is_live and not was_prev_live and not on_cool:
                    log.info("[Nike SNKRS] WATCHLIST LIVE: %s | %s", style_code, title)
                    await send_nike_drop(
                        NIKE_SNKRS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style_code, image=image,
                        upcoming=False,
                    )
                    notify[style_code] = time.time()
                    upcoming_seen.pop(style_code, None)

                elif _is_upcoming(launch_status, pi, props) and style_code not in upcoming_seen:
                    drop_date_str = _extract_drop_date(pi, props)
                    drop_ts       = _extract_drop_timestamp(pi, props)
                    log.info("[Nike SNKRS] WATCHLIST UPCOMING: %s | %s | status=%s | drop=%s",
                             style_code, title[:50], launch_status, drop_date_str or "TBA")
                    await send_nike_drop(
                        UPCOMING_DROPS_WEBHOOK_URL,
                        name=title, url=product_url,
                        price=price_str, sizes=sizes,
                        style_code=style_code, image=image,
                        upcoming=True,
                        drop_date=drop_date_str,
                    )
                    upcoming_seen[style_code] = True
                    drops[style_code] = {
                        "title": title, "url": product_url, "price": price_str,
                        "image": image, "style_code": style_code,
                        "drop_date_str": drop_date_str, "drop_ts": drop_ts,
                        "reminded_24h": False,
                    }

                status[style_code] = launch_status

    # ── Day-before reminders ───────────────────────────────────────────────────

    async def _send_day_before_reminders(self, drops: dict, notify: dict) -> None:
        """Send @here alert when a drop is within the next 24 hours."""
        now = time.time()
        for key, info in drops.items():
            if info.get("reminded_24h"):
                continue
            drop_ts = info.get("drop_ts", 0)
            if drop_ts == 0:
                continue
            hours_until = (drop_ts - now) / 3600
            if 0 < hours_until <= 24:
                log.info("[Nike SNKRS] 24H REMINDER: %s drops in %.1fh", info.get("style_code", key), hours_until)
                await send_nike_drop(
                    UPCOMING_DROPS_WEBHOOK_URL,
                    name=info["title"],
                    url=info["url"],
                    price=info["price"],
                    sizes=[],
                    style_code=info.get("style_code", key),
                    image=info.get("image", ""),
                    upcoming=True,
                    drop_date=info.get("drop_date_str", ""),
                    is_24h_reminder=True,
                    hours_until=hours_until,
                )
                info["reminded_24h"] = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_sizes(skus: list) -> list[str]:
    # Nike uses several different availability strings across API versions
    AVAILABLE = {"IN_STOCK", "ACTIVE", "STOCKED", "AVAILABLE", "PURCHASABLE", "DAN", "CLOSEOUT"}
    sizes = []
    for sku in skus:
        nl = (
            sku.get("nikeSize")
            or sku.get("localizedSize")
            or (sku.get("countrySpecifications") or [{}])[0].get("localizedSize", "")
        )
        avail = sku.get("availabilityStatus", "").upper()
        # If status is explicitly OOS/unavailable, skip; otherwise include if we have a size
        oos = {"OUT_OF_STOCK", "CLOSEOUT_OOS", "HOLD", "NOT_AVAILABLE", "INACTIVE"}
        if nl and avail not in oos and (avail in AVAILABLE or avail == ""):
            sizes.append(nl)
    return sorted(set(sizes), key=lambda s: _size_sort_key(s))


def _size_sort_key(s: str) -> float:
    import re
    m = re.search(r"[\d.]+", s)
    return float(m.group()) if m else 99


def _extract_image(pi: dict, props: dict = None) -> str:
    # Best source: coverCard image from publishedContent.properties (obj-level, not pi-level)
    if props:
        try:
            card = props.get("coverCard", {}).get("properties", {})
            img = card.get("squarishURL") or card.get("portraitURL") or card.get("landscapeURL") or ""
            if img:
                return img
        except Exception:
            pass
    # Fallback: colorwayImages on productContent (often empty)
    try:
        content = pi.get("productContent", {})
        imgs = content.get("colorwayImages", {})
        return imgs.get("portraitURL", "") or imgs.get("squarishURL", "")
    except Exception:
        return ""


def _is_live(launch_status: str, pi: dict, props: dict) -> bool:
    """
    Returns True if the product is currently available to purchase/enter right now.
    ACTIVE with a future drop date = upcoming draw (NOT live).
    ACTIVE with no/past date = live or same-day drop (treat as live).
    """
    if launch_status in AVAILABLE_STATUSES:
        return True
    if launch_status == "ACTIVE":
        drop_ts = _extract_drop_timestamp(pi, props)
        # If drop date is in the future, this is an upcoming entry window — not live yet
        if drop_ts and drop_ts > time.time():
            return False
        return True  # no date or past date → treat as live
    return False


def _is_upcoming(launch_status: str, pi: dict, props: dict) -> bool:
    """
    Returns True if the product has a confirmed FUTURE drop date.
    Requires a future drop timestamp — this prevents spamming past drops that
    remain in the feed as INACTIVE after their release window has closed.
    """
    if _is_live(launch_status, pi, props):
        return False
    if launch_status == "ACTIVE":
        return False

    drop_ts = _extract_drop_timestamp(pi, props)
    now = time.time()

    if launch_status in UPCOMING_STATUSES:
        # Only notify if drop date is in the future (past drops remain INACTIVE in feed)
        if drop_ts and drop_ts > now:
            return True
        # COMING_SOON / SCHEDULED / EXCLUSIVE_ACCESS without a date are genuinely upcoming
        if launch_status in {"COMING_SOON", "SCHEDULED", "EXCLUSIVE_ACCESS"}:
            return True
        # INACTIVE/HOLD with no future date = old drop, skip
        return False

    # Unknown status but confirmed future date
    if drop_ts and drop_ts > now:
        return True

    return False


def _extract_drop_date(pi: dict, props: dict) -> str:
    """Return a human-readable drop date/time string, or empty string if unknown."""
    ts = _extract_drop_timestamp(pi, props)
    if ts:
        dt = datetime.datetime.utcfromtimestamp(ts)
        return dt.strftime("%b %d, %Y at %I:%M %p ET")
    return ""


def _extract_drop_timestamp(pi: dict, props: dict) -> float:
    """Return Unix timestamp of the drop, or 0 if unknown."""
    for source in (pi.get("launchView", {}), props.get("launchView", {}), props):
        for key in ("startEntryDate", "startDate", "publishStartDate"):
            raw = source.get(key)
            if raw:
                try:
                    dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return dt.timestamp()
                except Exception:
                    pass
    return 0.0


def _iso_now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"