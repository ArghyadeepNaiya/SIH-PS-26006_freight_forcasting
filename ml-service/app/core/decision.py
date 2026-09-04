"""Step 6: fix now, wait, or split.

DESIGN RULE (non-negotiable, encoded here rather than in a comment):
never recommend waiting on a forecast with no demonstrated skill. If skill score at
the required horizon is at or below the threshold, we default to FIX NOW and say why.
"""
from app.config import ASSUMPTIONS


def decide(best_option, forecast, skill_score, horizon_days, split_option=None, overrides=None):
    a = dict(ASSUMPTIONS)
    if overrides:
        a.update({k: v for k, v in overrides.items() if k in a})

    drivers = []

    # --- No-skill guard ---
    if skill_score is None or skill_score <= a["min_skill_score_to_wait"]:
        return {
            "action": "fix_now",
            "headline": "Fix now.",
            "reason": (
                f"Our forecast shows no reliable skill at {horizon_days} days "
                f"(skill score {0.0 if skill_score is None else round(skill_score, 3)}). "
                "With no demonstrated edge over simply assuming today's rate holds, "
                "waiting is a gamble, not a strategy."
            ),
            "confidence_label": "High confidence in the recommendation, low confidence in the forecast",
            "drivers": ["No forecast skill at this horizon"],
            "expected_saving_usd_per_tonne": 0.0,
        }

    today = best_option["landed_cost_usd_per_tonne"]
    lo, mid, hi = forecast["lower"], forecast["point"], forecast["upper"]

    # Translate an index-level forecast into a cost delta on this option.
    ratio_mid = mid / forecast["current"] if forecast["current"] else 1.0
    ratio_hi = hi / forecast["current"] if forecast["current"] else 1.0
    freight_share = best_option["cost_breakdown_usd_per_tonne"]["freight"] / today

    expected_cost = today * (1 - freight_share) + today * freight_share * ratio_mid
    worst_cost = today * (1 - freight_share) + today * freight_share * ratio_hi

    expected_saving = today - expected_cost
    downside_risk = max(0.0, worst_cost - today)

    if expected_saving > downside_risk * a["wait_risk_premium"] and expected_saving > 0.5:
        action, headline = "wait", "Wait."
        reason = (
            f"The {horizon_days}-day forecast implies roughly "
            f"${expected_saving:.2f}/t of saving against a downside risk of "
            f"${downside_risk:.2f}/t. The model beats a no-change assumption at this "
            f"horizon (skill score {skill_score:.3f})."
        )
        drivers.append(f"Forecast rates falling for {best_option['vessel_class']}")
    else:
        action, headline = "fix_now", "Fix now."
        reason = (
            f"Expected saving from waiting is only ${expected_saving:.2f}/t against "
            f"${downside_risk:.2f}/t of downside. Not worth the exposure."
        )
        drivers.append("Downside risk exceeds expected saving")

    if split_option and split_option["landed_cost_usd_per_tonne"] < today * (1 - a["split_advantage_threshold"]):
        action, headline = "split", "Split the cargo."
        reason = (
            f"Two smaller parcels land at ${split_option['landed_cost_usd_per_tonne']:.2f}/t "
            f"versus ${today:.2f}/t for the best single vessel, because the smaller class "
            f"can load closer to full at this port."
        )
        drivers.insert(0, "Draft limit penalises the larger vessel")

    if best_option.get("requires_lightering"):
        drivers.append(f"{best_option['discharge_port']} requires lightering at anchorage")
    if best_option.get("load_percentage", 100) < 85:
        drivers.append(
            f"Draft limits loading to {best_option['load_percentage']}% of capacity"
        )

    return {
        "action": action,
        "headline": headline,
        "reason": reason,
        "confidence_label": f"Forecast skill score {skill_score:.3f} at {horizon_days} days",
        "drivers": drivers[:3],
        "expected_saving_usd_per_tonne": round(expected_saving, 2),
    }
