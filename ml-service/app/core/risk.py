"""Early warnings. The fourth thing the problem statement asks for.

A warning here has to earn its place. Every one of them names the evidence that
raised it and says what a buyer can actually do about it, because a warning that
cannot be acted on is decoration, and a dashboard full of decoration teaches people
to ignore the one warning that mattered.

Five sources are watched.

1. The freight market, through how violently it is currently moving compared with
   its own history.
2. Our own forecast, which is warned about when it fails its skill test, because a
   buyer who does not know that will read the forecast as advice.
3. The ports, by comparing the waiting time a port operator has declared today
   against the typical waiting time published for that port. That difference is
   congestion, stated by the people who can see the queue.
4. The weather, which is already priced into every landed cost, and is repeated here
   because a delay that has been paid for is still a delay that has to be planned
   around.
5. The data itself. Running on scaffolding rather than real market history, or on a
   port record made mostly of unverified assumptions, is a risk to the decision even
   when every number on screen looks confident.

Severity is one of three words and nothing else. `high` means this could change the
decision. `medium` means it should be read before committing. `low` means it is
context. There is no colour-only signal anywhere in the output, because the interface
that renders it is used with a screen reader.
"""
from app.config import ASSUMPTIONS, PORTS, INDEX_KEYS, CLASS_BY_INDEX
from app.core import declarations as decl
from app.core import market
from app.core import weather
from app.forecasting import predict as fc


def _w(severity, category, title, detail, action, evidence):
    return {
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
        "action": action,
        "evidence": evidence,
    }


def market_warnings(df):
    out = []
    a = ASSUMPTIONS
    for key in INDEX_KEYS:
        if key not in df.columns:
            continue
        vol = market.volatility_regime(
            df[key], high_percentile=a.get("high_volatility_percentile", 0.75))
        if not vol or vol["band"] in ("normal", "calm"):
            continue
        cls = CLASS_BY_INDEX.get(key, key)
        pct = round(vol["percentile_of_history"] * 100)
        out.append(_w(
            "high" if vol["band"] == "high" else "medium",
            "market volatility",
            f"Hire prices for {cls} ships are moving unusually violently",
            (f"Over the last {vol['window_days']} trading days the price has swung more "
             f"than it did on {pct} percent of all the days in its history. {vol['plain']}"),
            ("Shorten the time between agreeing a price and fixing the ship. Where a term "
             "rate is available, this is the market in which paying for certainty is worth "
             "the most."),
            (f"Annualised volatility {vol['annualised_volatility']:.0%} against a long run "
             f"median of {vol['median_annualised_volatility']:.0%}, measured on the "
             f"{key} series.")))
    return out


def forecast_warnings(df, horizon_days=30):
    out = []
    for key in INDEX_KEYS:
        if key not in df.columns:
            continue
        f = fc.forecast(df, key, horizon_days)
        if f.get("has_skill"):
            continue
        cls = CLASS_BY_INDEX.get(key, key)
        out.append(_w(
            "medium", "forecast reliability",
            f"Do not act on the {cls} forecast at {horizon_days} days",
            (f"Tested against simply assuming the price does not change, our model scored "
             f"{f.get('skill_score')}. Anything at or below zero means it made mistakes at "
             f"least as large as doing nothing, so its forecast carries no information."),
            ("Decide on today's price and on the historical spread instead. The system will "
             "refuse to advise waiting while this is true, which is deliberate."),
            f"Skill score {f.get('skill_score')} at {horizon_days} days on the {key} series."))
    return out


def congestion_warnings():
    """Queues, as reported by the people who can actually see them.

    A port operator declares the waiting time at each of their handling areas through
    their own dashboard. Comparing that against the typical waiting time published for
    the port turns two separate numbers into the only congestion signal this system
    has that is not an assumption.
    """
    out = []
    threshold = float(ASSUMPTIONS.get("congestion_warning_extra_days", 1.0))
    for code, port in PORTS.items():
        d = decl.get(code)
        if not d:
            continue
        waits = [float(area["current_wait_days"]) for area in (d.get("areas") or [])
                 if area.get("current_wait_days") is not None]
        if not waits:
            continue
        declared = max(waits)
        typical = float(port.get("typical_wait_days") or 0.0)
        extra = declared - typical
        if extra < threshold:
            continue
        out.append(_w(
            "high" if extra >= 2 * threshold else "medium",
            "port congestion",
            f"{port['name']} is queueing longer than normal",
            (f"The operator of {port['name']} says ships are currently waiting "
             f"{declared:g} days for a berth. The figure published for this port is "
             f"{typical:g} days, so the queue is {extra:g} days longer than usual."),
            ("Every extra waiting day is charged at the daily hire rate, so check whether a "
             "nearby port lands the same cargo more cheaply this month even if it is "
             "normally the dearer of the two."),
            (f"OPERATOR DECLARED. Stated by {d.get('declared_by') or 'the port operator'} on "
             f"{str(d.get('updated_at'))[:10]}, against a published typical wait of "
             f"{typical:g} days.")))
    return out


def weather_warnings():
    out = []
    for code, port in PORTS.items():
        adv = weather.advisory(code) or {}
        days = float(adv.get("expected_weather_delay_days") or 0.0)
        if days < 1:
            continue
        fresh = ((adv.get("freshness") or {}).get("quay") or {}) if adv.get("freshness") else {}
        out.append(_w(
            "high" if days >= 3 else "medium",
            "weather",
            f"{port['name']} expects to lose {days:g} working day"
            f"{'' if days == 1 else 's'} to weather",
            adv.get("headline") or "Forecast conditions breach an operating limit.",
            ("Those days are already priced into the landed cost for this port as waiting "
             "charges. Plan the arrival around them, or compare a port whose forecast is "
             "clear."),
            (f"Forecast from {fresh.get('source') or adv.get('source') or 'the cached forecast'}"
             f"{', collected ' + str(fresh.get('fetched_at'))[:16] if fresh.get('fetched_at') else ''}.")))
    return out


def data_warnings(is_real_data, source_label, port_code=None):
    out = []
    if not is_real_data:
        out.append(_w(
            "high", "data quality",
            "Every price on this system is a stand-in, not a real market",
            ("The price history loaded here was generated to behave like a freight market "
             "rather than taken from one. Costs and comparisons computed from it are "
             "arithmetically correct and commercially meaningless."),
            ("Drop a real daily history into data/raw/baltic_indices.csv with columns date, "
             "BCI, BPI, BSI and BHSI. Everything on the system recomputes against it on the "
             "next restart, including the skill scores."),
            f"Loaded source. {source_label}"))
    if port_code and port_code in PORTS:
        port = PORTS[port_code]
        cites = port.get("citations", {}) or {}
        assumed = [k for k, v in cites.items() if "ASSUMPTION" in str(v).upper()]
        if assumed:
            out.append(_w(
                "medium", "data quality",
                f"{len(assumed)} of the figures for {port['name']} are unverified placeholders",
                ("These were chosen by this project as stand-ins and have not been confirmed "
                 "with the port authority or against a published document."),
                ("Confirm them with the port before this recommendation is used to commit "
                 "money. The port's own operator can also state them directly through the "
                 "port operator dashboard, which replaces the placeholder and records who "
                 "said so."),
                "Unverified fields. " + ", ".join(sorted(assumed)) + "."))
    return out


def concentration_warning(origin_code, origin_name, cargo_name, alternatives):
    """One origin carrying a whole programme is a risk in itself.

    The problem statement names five supply origins. A plan that draws everything
    from one of them is exposed to a single country's weather, industrial relations
    and export policy, and that exposure does not show up anywhere in a landed cost
    per tonne. It is the one risk on this page that the arithmetic cannot see.
    """
    if not alternatives:
        return None
    others = ", ".join(alternatives)
    return _w(
        "low", "supply concentration",
        f"This whole programme comes from one country",
        (f"Every tonne planned here loads in {origin_name}. A disruption there, whether "
         f"weather, a strike or an export restriction, stops the entire programme at once. "
         f"Nothing in the cost per tonne reflects that."),
        (f"{cargo_name} is also available in this system from {others}. Pricing the same "
         f"programme from one of those shows what a second source would cost, and that "
         f"difference is the price of the insurance."),
        f"Origins supplying {cargo_name}. {origin_name}, {others}.")


def report(df, is_real_data, source_label, horizon_days=30, port_code=None,
           origin_code=None, origin_name=None, cargo_name=None, alternatives=None):
    """Everything above, in one list, worst first."""
    items = []
    items += market_warnings(df)
    items += forecast_warnings(df, horizon_days)
    items += congestion_warnings()
    items += weather_warnings()
    items += data_warnings(is_real_data, source_label, port_code)
    if origin_code:
        c = concentration_warning(origin_code, origin_name or origin_code,
                                  cargo_name or "this material", alternatives or [])
        if c:
            items.append(c)

    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda w: (order.get(w["severity"], 3), w["category"]))
    counts = {s: sum(1 for w in items if w["severity"] == s)
              for s in ("high", "medium", "low")}
    return {
        "warnings": items,
        "counts": counts,
        "total": len(items),
        "headline": (
            f"{counts['high']} warning{'' if counts['high'] == 1 else 's'} that could change "
            f"the decision, {counts['medium']} to read before committing, "
            f"{counts['low']} for context."
            if items else "Nothing is currently flagged on any of the five things watched."),
    }
