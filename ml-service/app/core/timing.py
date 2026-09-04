"""When to go into the market, looked at across every horizon at once.

The single shipment screen asks one horizon at a time, because a buyer with a cargo
in front of them has already chosen how long they can wait. A buyer planning ahead
has not, and the honest answer to "when should we enter the market" has three parts
that this module puts on one page.

1. WHERE OUR MODEL CAN SAY ANYTHING. Every horizon is scored against naive
   persistence, and horizons where the model loses are reported as such. On the
   scaffolding data that is most of them, and the correct behaviour is to stop
   talking about the forecast rather than to soften the wording.
2. WHAT THE CALENDAR DOES. A month of the year effect, if the history contains one
   that is larger than its own noise. This needs no model and no skill. It is a
   property of the series that can be checked by hand.
3. HOW UNSTABLE THE MARKET IS RIGHT NOW. Volatility decides how much a fixed rate is
   worth, independently of where anybody thinks rates are going.

The three are deliberately kept apart in the response. A seasonal pattern is not
evidence that our model works, and a working model is not evidence of a seasonal
pattern. Merging them into one confidence number would hide exactly the distinction
this project exists to make.
"""
from app.config import ASSUMPTIONS, INDEX_KEYS, CLASS_BY_INDEX
from app.core import market
from app.forecasting import predict as fc


def scan(df, index_key="BCI", horizons=(7, 14, 30, 60, 90)):
    a = ASSUMPTIONS
    series = df[index_key]

    rows = []
    for h in horizons:
        f = fc.forecast(df, index_key, h)
        outlook = market.period_outlook(series, h)
        rows.append({
            "horizon_days": h,
            "has_skill": bool(f.get("has_skill")),
            "skill_score": f.get("skill_score"),
            "point": f.get("point"),
            "lower": f.get("lower"),
            "upper": f.get("upper"),
            "current": f.get("current"),
            "implied_change_percent": (
                round(100.0 * (f["point"] / f["current"] - 1.0), 1)
                if f.get("current") else None),
            # What history did over a period this long, which stands whether or not
            # the model has skill, and is the only thing left to lean on when it
            # does not.
            "historical_median_ratio": (
                round(outlook["expected_ratio"], 4) if outlook else None),
            "historical_p10_ratio": round(outlook["p10_ratio"], 4) if outlook else None,
            "historical_p90_ratio": round(outlook["p90_ratio"], 4) if outlook else None,
            "share_of_periods_above_today":
                round(outlook["share_above_one"], 3) if outlook else None,
        })

    vol = market.volatility_regime(
        series, high_percentile=a.get("high_volatility_percentile", 0.75))
    seas = market.seasonality(df["date"], series)

    usable = [r for r in rows if r["has_skill"]]
    if usable:
        best = min(usable, key=lambda r: -(r["skill_score"] or 0))
        verdict = (f"Our model earns its keep at {best['horizon_days']} days and only there. "
                   f"Treat its forecast as usable over that period and ignore it elsewhere.")
    else:
        verdict = ("Our model does not beat the lazy guess at any period we tested, so no "
                   "entry timing advice on this page comes from it. What is left below "
                   "comes from measured properties of the price history itself, which need "
                   "no model to be true.")

    return {
        "index_key": index_key,
        "vessel_class": CLASS_BY_INDEX.get(index_key, index_key),
        "horizons": rows,
        "any_horizon_usable": bool(usable),
        "verdict": verdict,
        "volatility": vol,
        "seasonality": seas,
    }


def all_indices(df):
    """The same scan for every vessel class, for the risk panel and the programme."""
    return {k: scan(df, k) for k in INDEX_KEYS if k in df.columns}
