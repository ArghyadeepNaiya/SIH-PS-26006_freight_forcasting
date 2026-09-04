"""Spot by spot, or one contract covering many voyages. The stated objective.

WHAT THIS ANSWERS.

The problem statement's objective is one sentence long and it is the whole point of
the project. Move from entering many single spot contracts to entering short or
medium term contracts covering multiple voyages. Everything else in this service
prices ONE shipment. This module prices a PROGRAMME, which is a quantity of material
that has to arrive over a period, and it says how much of that programme should be
committed to a term contract now.

HOW THE ANSWER IS REACHED, IN SIXTY SECONDS.

1. Ask the existing pipeline to solve one shipment. That returns the best ship class
   and discharge port, how many tonnes that ship can actually land at that port, and
   the landed cost of a tonne broken into its parts. Nothing about that changes here.
2. Divide the programme quantity by what one ship can land, which gives the number of
   voyages and therefore how often a ship has to be fixed.
3. Split the landed cost into the part exposed to the freight market and the part
   that is not. Port charges, unloading at sea and the inland leg do not move when
   the charter market moves, so a term contract cannot protect them and it would be
   dishonest to claim savings against them.
4. Take the historical distribution of what the average spot level over a period of
   this length has been, relative to the level on the day the period began. That
   distribution, from app.core.market, is what a term rate is competing against. It
   needs no forecasting skill, which matters, because on this data we have none.
5. Price three plans against that distribution. Everything on spot. Everything on
   term. And the mean variance answer in between, which is the one that is normally
   right.

WHAT THIS DELIBERATELY DOES NOT DO.

It does not claim to know where rates are going. The expected spot cost here is the
median of what history did over periods of this length, not a forecast, and it is
labelled that way everywhere it is shown. If the forecasting model ever does earn a
positive skill score at the relevant horizon, that is a separate signal and it is
reported separately, in the timing scan.
"""
from app.config import ASSUMPTIONS, VESSELS
from app.core import market
from app.core import pipeline


# A term contract shorter than this is not a term contract, it is a run of spot
# fixtures with extra paperwork. Below it the module says so rather than pretending.
MIN_TERM_DAYS = 45


def _plan(name, label, covered_share, term_ratio, outlook, landed, freight_share,
          voyages, tonnes_per_voyage):
    """Cost one plan under the historical distribution of spot outcomes.

    A tonne's landed cost is split into the market exposed part and the fixed part.
    Under a plan that covers `covered_share` of the programme on a term contract, the
    exposed part is paid at `term_ratio` on the covered share and at whatever the
    spot average turns out to be on the rest.
    """
    fixed_part = landed * (1.0 - freight_share)
    exposed = landed * freight_share
    k = float(covered_share)

    def at(ratio):
        return fixed_part + exposed * (k * term_ratio + (1.0 - k) * ratio)

    expected = at(outlook["expected_ratio"])
    low = at(outlook["p10_ratio"])
    high = at(outlook["p90_ratio"])
    total_tonnes = voyages * tonnes_per_voyage
    return {
        "plan": name,
        "label": label,
        "covered_share": round(k, 4),
        "covered_percent": round(k * 100, 1),
        "expected_cost_usd_per_tonne": round(expected, 2),
        "best_case_usd_per_tonne": round(low, 2),
        "worst_case_usd_per_tonne": round(high, 2),
        "range_usd_per_tonne": round(high - low, 2),
        "expected_programme_cost_usd": round(expected * total_tonnes),
        "worst_case_programme_cost_usd": round(high * total_tonnes),
    }


def run(req, df):
    """Plan a whole procurement programme. `req` extends the recommend request.

    Extra fields beyond a single shipment request are `programme_tonnes`, the total
    quantity to be landed, `programme_days`, the period it has to land over, and
    optionally `term_rate_ratio`, the rate an owner has actually offered expressed as
    a fraction of today's spot level.
    """
    # An explicit zero is a mistake to be reported, not an absent value to be filled
    # in from the single shipment field. `or` would have quietly swallowed it.
    total = req.get("programme_tonnes")
    if total is None:
        total = req.get("quantity_tonnes")
    total_tonnes = float(total or 0)
    period_days = int(req.get("programme_days") or 180)
    if total_tonnes <= 0:
        raise ValueError("A programme needs a total quantity greater than zero tonnes.")
    if period_days < 7:
        raise ValueError("A programme period shorter than a week is a single shipment. "
                         "Use the recommendation screen for that.")

    a = dict(ASSUMPTIONS)
    overrides = req.get("overrides") or {}
    a.update({k: v for k, v in overrides.items() if k in a})

    # --- 1 and 2. Solve one shipment, then work out how many of them there are. ---
    # The pipeline is asked for the whole programme quantity, because that is what
    # makes it report how many voyages the quantity needs. The per voyage economics
    # it returns are unaffected by the total, since a ship can only carry what a ship
    # can carry.
    single = pipeline.run({**req, "quantity_tonnes": total_tonnes}, df)
    options = single.get("options") or []
    if not options:
        return {
            "feasible": False,
            "reason": ("No ship and port combination can carry this material at all, so "
                       "there is no programme to plan. The single shipment screen lists "
                       "every combination that was refused and why."),
            "single_shipment": single,
        }

    best = options[0]
    per_voyage = float(best["deliverable_tonnes"])
    voyages = int(max(1, -(-total_tonnes // max(1.0, per_voyage))))
    days_between = period_days / voyages if voyages else period_days

    landed = float(best["landed_cost_usd_per_tonne"])
    freight_usd = float(best["cost_breakdown_usd_per_tonne"]["freight"])
    # Demurrage moves with the market too, because it is priced off the daily hire
    # rate. Treating it as exposed is the conservative and the correct choice.
    demurrage_usd = float(best["cost_breakdown_usd_per_tonne"]["expected_demurrage"])
    exposed_usd = freight_usd + demurrage_usd
    freight_share = exposed_usd / landed if landed > 0 else 0.0

    # --- 3 and 4. What has the spot market done over periods of this length. ---
    index_key = VESSELS[best["vessel_class"]]["index_key"]
    series = df[index_key]
    outlook = market.period_outlook(series, period_days)
    if outlook is None:
        return {
            "feasible": False,
            "reason": (f"There is not enough price history to describe what a "
                       f"{period_days} day period has typically done. At least a few years "
                       f"of daily history for the {index_key} index is needed before this "
                       f"comparison means anything."),
            "single_shipment": single,
        }

    term_ratio = req.get("term_rate_ratio")
    term_ratio = float(term_ratio) if term_ratio else float(a["term_rate_ratio_default"])
    term_quoted = req.get("term_rate_ratio") is not None

    # --- 5. Three plans, priced against the same distribution. ---
    k_star = market.optimal_coverage(outlook["expected_ratio"], term_ratio,
                                     outlook["sd_ratio"], a["risk_aversion_lambda"])
    plans = [
        _plan("all_spot", "Fix every voyage on the day you need it", 0.0, term_ratio,
              outlook, landed, freight_share, voyages, per_voyage),
        _plan("recommended", f"Cover {round(k_star * 100)} percent on a term contract",
              k_star, term_ratio, outlook, landed, freight_share, voyages, per_voyage),
        _plan("all_term", "Put the whole programme on one term contract", 1.0, term_ratio,
              outlook, landed, freight_share, voyages, per_voyage),
    ]
    by_name = {p["plan"]: p for p in plans}
    spot, rec, term = by_name["all_spot"], by_name["recommended"], by_name["all_term"]

    # The break even is the term rate at which a fully covered programme costs the
    # same as the expected spot programme. Any offer below it is cheaper on average
    # AND removes the range, which is why it is the number to take into a negotiation.
    break_even_ratio = outlook["expected_ratio"]
    current_index = float(series.iloc[-1])
    tce_now = float(best["tce_usd_per_day"])

    saving_vs_spot = spot["expected_cost_usd_per_tonne"] - rec["expected_cost_usd_per_tonne"]
    range_cut = spot["range_usd_per_tonne"] - rec["range_usd_per_tonne"]

    # How much the term rate is above or below where spot has typically settled. This
    # is the premium being charged for certainty, and it is the single number the
    # recommendation turns on, so it is stated rather than left to be inferred.
    premium_ratio = term_ratio - outlook["expected_ratio"]
    premium_per_tonne = round(exposed_usd * premium_ratio, 2)
    # Coverage falls linearly from everything, at no premium, to nothing, at a
    # premium of two lambda sigma squared. Saying where that end point sits turns the
    # risk aversion figure from an arbitrary constant into a sentence a buyer can
    # agree or disagree with.
    walk_away_premium_ratio = 2.0 * a["risk_aversion_lambda"] * outlook["sd_ratio"] ** 2

    def _tail(): return (
        f"On average that costs about ${abs(premium_per_tonne):.2f} a tonne "
        f"{'more' if premium_per_tonne > 0 else 'less'} than buying every voyage on the day, "
        f"and it takes ${range_cut:.2f} a tonne out of the range the final bill could land in."
    )

    if period_days < MIN_TERM_DAYS:
        headline = "This period is too short for a term contract to mean anything."
        plain = (f"{period_days} days is about one voyage's worth of time. A contract over a "
                 f"period this short is a spot fixture with extra paperwork. Plan it on the "
                 f"single shipment screen instead.")
        chosen = "all_spot"
    elif k_star >= 0.95:
        headline = "Put the whole programme on a term contract."
        if premium_ratio <= 0:
            plain = (f"The term rate assumed here is at or below where the spot market has "
                     f"typically settled over {period_days} days, so committing is both "
                     f"cheaper on average and steadier. There is no case for leaving any of "
                     f"it exposed. " + _tail())
        else:
            plain = (f"The owner is asking only a little above where spot has typically "
                     f"settled over {period_days} days, and that is comfortably less than "
                     f"the swing it removes is worth to you at the risk appetite recorded in "
                     f"cost_assumptions.json. " + _tail())
        chosen = "all_term"
    elif k_star <= 0.05:
        headline = "Keep this programme on the spot market."
        plain = (f"The term rate on the table sits {premium_ratio * 100:.1f} percent above "
                 f"where spot has typically settled over {period_days} days. That premium is "
                 f"larger than the certainty is worth to you, so buy each voyage as it comes. "
                 + _tail())
        chosen = "all_spot"
    else:
        headline = f"Cover {round(k_star * 100)} percent of this programme on a term contract."
        plain = (f"Commit {round(k_star * 100)} percent of the {voyages} voyages now and buy "
                 f"the remaining {round((1 - k_star) * 100)} percent on the spot market as "
                 f"each shipment comes up. That splits the difference between paying the "
                 f"owner for certainty and carrying the whole swing yourself. " + _tail())
        chosen = "recommended"

    return {
        "feasible": True,
        "headline": headline,
        "plain": plain,
        "chosen_plan": chosen,
        "shape": {
            "total_tonnes": round(total_tonnes),
            "period_days": period_days,
            "voyages": voyages,
            "tonnes_per_voyage": round(per_voyage),
            "days_between_fixtures": round(days_between, 1),
            "vessel_class": best["vessel_class"],
            "discharge_port": best["discharge_port"],
            "origin": best["origin"],
            "landed_cost_usd_per_tonne": landed,
            "market_exposed_usd_per_tonne": round(exposed_usd, 2),
            "market_exposed_share": round(freight_share, 4),
            "fixed_usd_per_tonne": round(landed - exposed_usd, 2),
        },
        "market": {
            "index_key": index_key,
            "current_index": current_index,
            "current_tce_usd_per_day": tce_now,
            **outlook,
            "break_even_ratio": round(break_even_ratio, 4),
            "break_even_tce_usd_per_day": round(tce_now * break_even_ratio),
            "term_ratio_used": round(term_ratio, 4),
            "term_rate_was_quoted": term_quoted,
            "term_tce_usd_per_day": round(tce_now * term_ratio),
            "premium_ratio": round(premium_ratio, 4),
            "premium_usd_per_tonne": premium_per_tonne,
            "walk_away_premium_ratio": round(walk_away_premium_ratio, 4),
            "walk_away_premium_usd_per_tonne": round(exposed_usd * walk_away_premium_ratio, 2),
            "risk_aversion_lambda": a["risk_aversion_lambda"],
        },
        "plans": plans,
        "recommended_coverage": round(k_star, 4),
        "expected_saving_vs_spot_usd_per_tonne": round(saving_vs_spot, 2),
        "expected_saving_vs_spot_usd_total": round(saving_vs_spot * voyages * per_voyage),
        "uncertainty_removed_usd_per_tonne": round(range_cut, 2),
        "single_shipment": single,
    }
