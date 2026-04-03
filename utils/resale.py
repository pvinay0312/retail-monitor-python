"""
Resale value estimator — identifies resale-worthy products and provides
estimated resale price ranges + eBay sold listings / StockX links.

Estimates are rough multipliers based on category trends. Always link to
eBay sold listings so members can verify real-time prices with one click.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote_plus

# category key → detection keywords + resale multiplier range
_CATEGORIES: dict[str, dict] = {
    "lego": {
        "keywords": ["lego"],
        "lo": 1.1, "hi": 2.0,
        "note": "LEGO sets hold or appreciate — especially Star Wars, Icons & retiring sets",
        "stockx": False,
    },
    "pokemon": {
        "keywords": ["pokemon", "pokémon", "trading card", "booster pack",
                     "booster box", "elite trainer", " tcg "],
        "lo": 1.0, "hi": 3.0,
        "note": "Sealed Pokémon product typically holds value; new sets can 2-3× at peak",
        "stockx": False,
    },
    "gpu": {
        "keywords": [
            "rtx 5090", "rtx 5080", "rtx 5070", "rtx 4090", "rtx 4080",
            "radeon rx 9070", "radeon rx 7900",
            "graphics card", "video card",
        ],
        "lo": 1.0, "hi": 1.5,
        "note": "High-end GPUs trade at or above MSRP at launch; check StockX",
        "stockx": True,
    },
    "console": {
        "keywords": [
            "ps5", "playstation 5", "xbox series x",
            "nintendo switch 2", "switch 2",
        ],
        "lo": 1.0, "hi": 1.35,
        "note": "Limited / bundle editions command 10-35% resale premium",
        "stockx": True,
    },
    "sneakers": {
        "keywords": [
            "air jordan", "yeezy", "travis scott", "off-white", "dunk sb",
            "air max 1", "new balance 990", "new balance 2002",
        ],
        "lo": 1.2, "hi": 4.0,
        "note": "Hype sneakers 20-4× retail — check StockX for exact ask/bid",
        "stockx": True,
    },
    "funko": {
        "keywords": ["funko pop", "funko exclusive", "sdcc funko"],
        "lo": 1.1, "hi": 3.0,
        "note": "Convention exclusives & vaulted Pops appreciate significantly",
        "stockx": False,
    },
}


def get_resale_info(name: str, price: float) -> Optional[dict]:
    """
    Return resale estimate dict for resale-worthy products, else None.

    Keys: category, low_est, high_est, ebay_url, stockx_url (or None), note
    """
    if price <= 0:
        return None
    name_lower = name.lower()
    for cat_key, cat in _CATEGORIES.items():
        if any(kw in name_lower for kw in cat["keywords"]):
            q = quote_plus(name[:80])
            ebay_url   = f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_Sold=1&LH_Complete=1"
            stockx_url = (
                f"https://stockx.com/search?s={quote_plus(name[:60])}"
                if cat["stockx"] else None
            )
            return {
                "category":   cat_key,
                "low_est":    round(price * cat["lo"], 2),
                "high_est":   round(price * cat["hi"], 2),
                "ebay_url":   ebay_url,
                "stockx_url": stockx_url,
                "note":       cat["note"],
            }
    return None


def resale_fields(name: str, price: float) -> list[dict]:
    """Return Discord embed field dicts for resale info, or empty list."""
    info = get_resale_info(name, price)
    if not info:
        return []

    lo, hi = info["low_est"], info["high_est"]
    if lo == hi:
        est_value = f"**~${lo:.0f}**"
    elif hi >= lo * 2:
        est_value = f"**${lo:.0f} – ${hi:.0f}+**"
    else:
        est_value = f"**${lo:.0f} – ${hi:.0f}**"

    links = f"[eBay Sold ↗]({info['ebay_url']})"
    if info["stockx_url"]:
        links += f"  •  [StockX ↗]({info['stockx_url']})"

    return [
        {"name": "💹 Est. Resale Value", "value": est_value, "inline": True},
        {"name": "🔗 Resale Prices",     "value": links,     "inline": True},
    ]