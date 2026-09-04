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
                f"Our price forecast for the next {horizon_days} days is not reliable. Its "
                f"skill score is "
                f"{0.0 if skill_score is None else round(skill_score, 3)}, and anything at or "
                "below zero means the forecast is no better than simply assuming today's "
                "price holds. With nothing solid to wait for, waiting would be a gamble "
                "rather than a plan, so book the ship now."
            ),
            "confidence_label": ("We are confident in this advice, and not at all confident "
                                 "in the forecast it is based on"),
            "drivers": ["The forecast is not reliable this far ahead"],
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
            f"Looking {horizon_days} days ahead, the forecast suggests you would save about "
            f"${expected_saving:.2f} on every tonne, against a risk of losing "
            f"${downside_risk:.2f} a tonne if prices move the other way. The model does beat "
            f"the lazy guess of assuming no change over this period, with a skill score of "
            f"{skill_score:.3f}, so the forecast is worth acting on."
        )
        drivers.append(f"Hire prices for a {best_option['vessel_class']} are forecast to fall")
    else:
        action, headline = "fix_now", "Fix now."
        reason = (
            f"Waiting would save only about ${expected_saving:.2f} a tonne, while risking "
            f"${downside_risk:.2f} a tonne if prices go the other way. That is not worth the "
            f"exposure, so book now."
        )
        drivers.append("The risk of waiting is larger than the likely saving")

    if split_option and split_option["landed_cost_usd_per_tonne"] < today * (1 - a["split_advantage_threshold"]):
        action, headline = "split", "Split the cargo."
        reason = (
            f"Bringing the material in as two smaller shiploads costs "
            f"${split_option['landed_cost_usd_per_tonne']:.2f} a tonne, against "
            f"${today:.2f} a tonne for the best single ship, because the smaller ship can be "
            f"loaded much closer to full at this port."
        )
        drivers.insert(0, "The port is too shallow to fill the larger ship")

    if best_option.get("requires_lightering"):
        drivers.append(
            f"{best_option['discharge_port']} needs part of the load taken off at sea first"
        )
    if best_option.get("load_percentage", 100) < 85:
        drivers.append(
            f"Shallow water means the ship can only be filled to "
            f"{best_option['load_percentage']} percent"
        )

    return {
        "action": action,
        "headline": headline,
        "reason": reason,
        "confidence_label": f"Forecast skill score {skill_score:.3f} at {horizon_days} days",
        "drivers": drivers[:3],
        "expected_saving_usd_per_tonne": round(expected_saving, 2),
    }
