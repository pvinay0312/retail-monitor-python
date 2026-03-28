"""
Deal scoring engine — ports the scoring formula from the spec.
Score range: 0–100.
Routing thresholds:
  80+   → @here ping, all channels
  60–79 → standard alert
  40–59 → low-priority alert
  <40   → suppressed (not posted)
"""

CATEGORY_WEIGHTS: dict[str, int] = {
    "electronics":      90,
    "computers":        90,
    "gaming":           85,
    "video games":      85,
    "headphones":       80,
    "phones":           80,
    "tablets":          80,
    "laptops":          80,
    "cameras":          75,
    "smart home":       70,
    "kitchen":          65,
    "home":             60,
    "appliances":       65,
    "tools":            55,
    "sports":           55,
    "fitness":          55,
    "toys":             60,
    "beauty":           55,
    "health":           55,
    "clothing":         50,
    "shoes":            70,
    "sneakers":         85,
    "gardening":        45,
    "furniture":        50,
    "outdoors":         50,
    "baby":             55,
    "pet":              55,
    "food":             40,
    "grocery":          40,
    "office":           50,
    "books":            35,
}

MIN_SCORE_TO_ALERT = 40   # below this, deal is suppressed


def calculate_deal_score(
    discount_pct: float,
    original_price: float = 0.0,
    deal_price: float = 0.0,
    star_rating: float = 4.0,
    review_count: int = 100,
    category: str = "general",
    hours_old: float = 0.0,
) -> int:
    """
    Returns 0–100 composite deal score.

    Weights:
      35% discount depth
      25% product quality (stars + review count)
      15% category popularity
      15% freshness (decays over 24h)
      10% dollar savings value
    """
    # ── Discount depth (35%) ─────────────────────────────────────────────────
    discount_score = 0.0
    if discount_pct >= 25:
        discount_score = min(100.0, (discount_pct - 25) * 2.2)

    # ── Product quality (25%) ─────────────────────────────────────────────────
    stars_score   = min(100.0, max(0.0, (star_rating - 3.0) * 50))
    reviews_score = min(100.0, review_count / 5.0)
    quality_score = stars_score * 0.6 + reviews_score * 0.4

    # ── Category popularity (15%) ─────────────────────────────────────────────
    category_score = float(CATEGORY_WEIGHTS.get(category.lower(), 50))

    # ── Freshness (15%) — decays to 0 over 24 hours ───────────────────────────
    freshness_score = max(0.0, 100.0 - hours_old * 4.17)

    # ── Dollar savings value (10%) ────────────────────────────────────────────
    savings = original_price - deal_price if original_price and deal_price else 0.0
    dollar_score = min(100.0, savings * 2)   # $50+ savings = max score

    score = (
        discount_score  * 0.35 +
        quality_score   * 0.25 +
        category_score  * 0.15 +
        freshness_score * 0.15 +
        dollar_score    * 0.10
    )
    return round(score)


def score_label(score: int) -> str:
    if score >= 80:
        return "🔥🔥🔥 HOT"
    if score >= 60:
        return "🔥🔥 Great"
    if score >= 40:
        return "🔥 Good"
    return "Low"