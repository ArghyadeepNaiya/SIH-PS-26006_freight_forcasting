"""The eight-step request pipeline from ARCHITECTURE.md section 4.

1. candidate generation
2. hard constraint filtering (rejections are returned, not discarded)
3. capacity adjustment under draft limits
4. cost assembly
5. ranking by landed cost per tonne
6. timing decision
7. explanation assembly
8. response

TWO LIVE INPUTS JOIN THE PIPELINE AT STEP 2 AND STEP 4.

The first is the PORT OPERATOR DECLARATION, from app.core.declarations. The operator
of each port signs in to their own dashboard and declares how much laydown area they
have, when it is free, which vessel classes it takes, and what their real discharge
rate, waiting time and charges are. A declaration can do three things here. It can
override a reference number the cost model reads, always with the provenance label
OPERATOR DECLARED attached so the business can see where the figure came from. It can
add a rejection, when the operator says no area of theirs accepts this class or none
is free in the arrival window. It can add demand intelligence, which is reported
beside the ranking and deliberately never folded into it.

The second is the WEATHER ADVISORY, from app.core.weather. Forecast days that breach
an operating limit at the quay or the approach anchorage become expected delay days,
and delay days become demurrage. That is the only honest way to put weather into a
landed cost per tonne. The read is cache only, so a recommendation never waits on an
external service, and a port with nothing cached contributes zero delay and says so.
"""
from datetime import date, datetime, timedelta

from app.core import candidates as cand
from app.core import constraints, capacity, cost_model, decision
from app.core import declarations as decl
from app.core import weather
from app.config import VESSELS, ASSUMPTION_META, PORTS, CARGOES
from app.forecasting import predict as fc


DEFAULT_WINDOW_DAYS = 30


def _arrival_window(req):
    """The window the cargo must arrive in, and a sentence explaining it.

    An operator declares when an area is free between two dates, so a declaration
    can only be checked against a window. If the user gave neither date we use today
    through the decision horizon and say so on screen, rather than silently choosing
    dates on their behalf.
    """
    def parse(v):
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    start = parse(req.get("earliest_arrival"))
    end = parse(req.get("latest_arrival"))
    horizon = int(req.get("horizon_days", DEFAULT_WINDOW_DAYS) or DEFAULT_WINDOW_DAYS)

    if start and end and end < start:
        start, end = end, start
    if start is None and end is None:
        start = date.today()
        end = start + timedelta(days=horizon)
        note = (f"You did not say when the cargo has to arrive, so port availability was "
                f"checked from today, {start.isoformat()}, up to {end.isoformat()}, which is "
                f"the {horizon} days ahead you chose to decide over.")
    elif start is None:
        start = date.today()
        note = (f"Port availability was checked from today, {start.isoformat()}, up to the "
                f"latest arrival date you gave, {end.isoformat()}.")
    elif end is None:
        end = start + timedelta(days=horizon)
        note = (f"You gave an earliest arrival date but no latest one, so port availability "
                f"was checked from {start.isoformat()} across the {horizon} days ahead you "
                f"chose to decide over, up to {end.isoformat()}.")
    else:
        note = (f"Port availability was checked against the arrival dates you gave, "
                f"{start.isoformat()} to {end.isoformat()}.")
    return start, end, note


def _declaration_rejection(c, offer):
    """Turn an operator refusal into a rejection the business can read."""
    d = offer.get("declaration") or {}
    who = d.get("declared_by") or "the port operator"
    when = d.get("updated_at") or "an unrecorded date"
    return {
        "vessel_class": c["vessel_class"],
        "discharge_port": c["discharge_port"],
        "failed_constraint": "operator declaration",
        "limit_value": None,
        "required_value": None,
        "unit": "",
        "explanation": offer["explanation"],
        "source_citation": (f"OPERATOR DECLARED. Stated by {who} on {when} through the "
                            f"port operator dashboard. This is not a published port "
                            f"authority limit, it is what the port itself currently "
                            f"says it can take."),
    }


def _area_note(area, deliverable_tonnes):
    """A sentence about the declared area holding this parcel, or None."""
    if not area:
        return None
    name = area.get("name") or "an unnamed area"
    cap = area.get("storage_capacity_tonnes")
    bits = [f"The port is offering you {name}"]
    if area.get("area_sq_m"):
        bits.append(f"it covers {float(area['area_sq_m']):,.0f} square metres")
    if cap:
        cap = float(cap)
        if cap < deliverable_tonnes:
            bits.append(f"it holds {cap:,.0f} tonnes, which is less than the "
                        f"{deliverable_tonnes:,.0f} tonnes coming off this ship, so the "
                        f"material has to be moved out to the plant as it lands")
        else:
            bits.append(f"it holds {cap:,.0f} tonnes, enough for the whole load at once")
    return ". ".join(bits)


def _tce_from_index(index_value, index_key):
    """Convert an index level to an approximate daily time-charter equivalent.

    ASSUMPTION. Baltic publishes TCE alongside index points and the ratio differs
    by class. These multipliers are placeholders roughly calibrated to reported
    late-2026 levels. Replace with published TCE series when available.
    """
    mult = {"BCI": 9.1, "BPI": 9.0, "BSI": 12.6, "BHSI": 18.0}
    return index_value * mult.get(index_key, 10.0)


def _idle_summary(options):
    """Where the unproductive days are, and what moving the cargo would save.

    Idle time on a voyage is waiting for a berth plus waiting out weather, and the
    empty positioning leg is time on hire with no cargo aboard at all. The cost model
    already prices all three. What was missing was anybody adding them up and saying
    which port causes the fewest of them, which is the whole of the problem
    statement's idle scenario requirement in one paragraph.
    """
    if not options:
        return None
    best = options[0]
    b_idle = best.get("idle_and_empty_time") or {}

    # The least idle option, which is not always the cheapest one. Where they differ
    # the difference is worth stating, because idle days are the part of a voyage a
    # buyer can actually plan away.
    leanest = min(options, key=lambda o: (o.get("idle_and_empty_time") or {}).get("idle_days", 99))
    l_idle = leanest.get("idle_and_empty_time") or {}
    saving = round(b_idle.get("idle_cost_usd_per_tonne", 0)
                   - l_idle.get("idle_cost_usd_per_tonne", 0), 2)
    days_saved = round(b_idle.get("idle_days", 0) - l_idle.get("idle_days", 0), 1)

    if leanest is best or days_saved <= 0:
        alt = None
        headline = (f"The recommended voyage spends {b_idle.get('idle_days', 0):g} days "
                    f"waiting and {b_idle.get('ballast_days', 0):g} days sailing empty to "
                    f"collect the cargo. No other workable option wastes less time than that.")
    else:
        alt = {
            "vessel_class": leanest["vessel_class"],
            "discharge_port": leanest["discharge_port"],
            "idle_days": l_idle.get("idle_days"),
            "landed_cost_usd_per_tonne": leanest["landed_cost_usd_per_tonne"],
            "extra_cost_usd_per_tonne": round(
                leanest["landed_cost_usd_per_tonne"] - best["landed_cost_usd_per_tonne"], 2),
            "idle_days_saved": days_saved,
            "idle_saving_usd_per_tonne": saving,
        }
        headline = (f"The recommended voyage spends {b_idle.get('idle_days', 0):g} days "
                    f"waiting. A {leanest['vessel_class']} into "
                    f"{leanest['discharge_port']} would wait {days_saved:g} days less.")

    return {
        "headline": headline,
        "recommended": b_idle,
        "least_idle_alternative": alt,
        "note": ("Waiting days and weather days are already charged into every landed cost "
                 "on this page at the daily hire rate. They are pulled out here because they "
                 "are the part of a voyage that planning can remove, whereas the sailing "
                 "distance is not."),
    }


def _reject_draft(c, capd):
    """Reject a candidate that is physically able to berth but cannot load enough.

    The shortfall is either a WEIGHT problem (draft too shallow) or a VOLUME
    problem (the cargo cubes out). They read very differently to a user, so they
    are reported differently.
    """
    if capd["binding_constraint"] == "volume":
        return {
            "vessel_class": c["vessel_class"],
            "discharge_port": c["discharge_port"],
            "failed_constraint": "stowage",
            "limit_value": capd["volume_capacity_tonnes"],
            "required_value": capd["nominal_capacity_tonnes"],
            "unit": "t",
            "explanation": (
                f"At a stowage factor of {capd['stowage_factor_m3_per_t']} m3/t this "
                f"cargo fills the {capd['grain_capacity_m3']:,} m3 of hold space after "
                f"only {capd['volume_capacity_tonnes']:,} t, which is "
                f"{capd['load_percentage']}% of deadweight. The cargo cubes out, and "
                f"lightering cannot help because hold space is fixed."
            ),
            "source_citation": c["vessel"].get("citations", {}).get(
                "grain_capacity_m3", "no citation recorded"),
        }

    return {
        "vessel_class": c["vessel_class"],
        "discharge_port": c["discharge_port"],
        "failed_constraint": "draft",
        "limit_value": capd["binding_draft_m"],
        "required_value": capd["vessel_laden_draft_m"],
        "unit": "m",
        "explanation": (
            f"Draft limit of {capd['binding_draft_m']} m at the "
            f"{capd['binding_constraint']} allows only {capd['load_percentage']}% "
            f"loading, below the economic minimum for this class."
        ),
        "source_citation": c["port"].get("citations", {}).get(
            "max_draft_m", "no citation recorded"),
    }


def run(req, df):
    cargo = req["cargo_type"]
    qty = float(req["quantity_tonnes"])
    origin = req["origin"]
    plant = req.get("destination_plant")
    port_filter = req.get("destination_port")
    horizon = int(req.get("horizon_days", 30))
    overrides = req.get("overrides") or {}

    window_start, window_end, window_note = _arrival_window(req)

    # --- Step 1: candidates ---
    raw = cand.generate(origin, cargo)
    if port_filter:
        raw = [c for c in raw if c["port_code"] == port_filter]
    for c in raw:
        c["plant"] = plant

    # Weather and declarations are read once per port, not once per candidate, so
    # the same port cannot report two different forecasts inside one answer.
    port_codes = sorted({c["port_code"] for c in raw})
    weather_by_port = {code: weather.advisory(code) for code in port_codes}
    demand_by_port = {code: decl.demand_for(code, cargo) for code in port_codes}

    options, rejected = [], []
    forecasts = {}

    for c in raw:
        code = c["port_code"]

        # --- Step 2a: what is the operator of this port offering this ship ---
        offer = decl.berth_offer(code, c["vessel_class"], window_start, window_end)
        if offer["status"] == "refused":
            rejected.append(_declaration_rejection(c, offer))
            continue
        area = offer.get("area")

        # From here on the candidate carries the EFFECTIVE port record. Published
        # reference values, overridden by whatever the operator has declared, with a
        # provenance label on every field the cost model reads.
        c["port"] = decl.effective_port(code, area)
        c["declared_area"] = area

        # --- Step 2b: hard constraints ---
        ok, rej, _ = constraints.check(c)
        if not ok:
            rejected.append({
                "vessel_class": c["vessel_class"],
                "discharge_port": c["discharge_port"],
                **rej,
            })
            continue

        wx = weather_by_port.get(code) or {}
        weather_delay = float(wx.get("expected_weather_delay_days") or 0.0)

        # A port with lightering gives the charterer two genuinely different
        # commercial choices. Show both rather than silently picking one.
        if c["port"].get("lightering_available"):
            variants = [(False, ""), (True, " (lightered)")]
        else:
            variants = [(True, "")]

        any_viable = False
        for allow_light, suffix in variants:
            # --- Step 3: capacity under draft AND hold volume ---
            capd = capacity.deliverable(c, qty, cargo_type=cargo,
                                        allow_lightering=allow_light)
            if not capd["economically_viable"]:
                continue
            any_viable = True

            ikey = c["vessel"]["index_key"]
            if ikey not in forecasts:
                forecasts[ikey] = fc.forecast(df, ikey, horizon)
            f = forecasts[ikey]
            tce = _tce_from_index(f["current"], ikey)

            # --- Step 4: cost, including weather delay as demurrage ---
            cost = cost_model.compute(c, capd, tce, overrides, cargo_type=cargo,
                                      weather_delay_days=weather_delay)
            if cost is None:
                continue

            # --- Step 7 (partial): explanation ---
            note = []
            if capd["requires_lightering"]:
                note.append(f"{capd['lightered_tonnes']:,} tonnes have to be taken off at sea "
                            f"into smaller boats before this ship can come in")
            if capd["cubes_out"]:
                note.append(
                    f"the holds fill up at {capd['load_percentage']} percent of what this ship "
                    f"could carry by weight, because one tonne of this material takes up "
                    f"{capd['stowage_factor_m3_per_t']} cubic metres")
            elif capd["load_percentage"] < 90:
                note.append(
                    f"shallow water means it can only be filled to "
                    f"{capd['load_percentage']} percent")
            if capd["voyages_needed"] and capd["voyages_needed"] > 1:
                note.append(f"it would take {capd['voyages_needed']} separate trips to move "
                            f"the whole quantity")
            if weather_delay > 0:
                note.append(f"{weather_delay:g} day"
                            f"{' is' if weather_delay == 1 else 's are'} expected to be lost "
                            f"to weather")
            # Each clause is a sentence in its own right, so each one starts with a
            # capital letter. Joined without this they read as one broken sentence.
            reason = ". ".join(n[0].upper() + n[1:] for n in note) if note else \
                "It loads completely full, with nothing holding it back"

            # Skip the lightered variant when lightering changes nothing.
            if allow_light and suffix and not capd["requires_lightering"]:
                continue

            demand = demand_by_port.get(code)
            this_demand = (demand or {}).get("this_cargo")

            options.append({
                "vessel_class": c["vessel_class"],
                "discharge_port": c["discharge_port"] + suffix,
                "port_code": code,
                "origin": c["origin_name"],
                "distance_nm": c["distance_nm"],
                **capd,
                **cost,
                "reason": reason,
                # --- what the operator of this port declared ---
                "operator_declared": offer["status"] != "no_declaration",
                "declared_area": ({
                    "name": area.get("name"),
                    "area_sq_m": area.get("area_sq_m"),
                    "storage_capacity_tonnes": area.get("storage_capacity_tonnes"),
                    "available_from": area.get("available_from"),
                    "available_to": area.get("available_to"),
                    "availability_note": offer.get("availability_note"),
                    "alternatives": offer.get("alternatives", 0),
                    "notes": area.get("notes") or "",
                } if area else None),
                "declared_area_note": _area_note(area, capd["deliverable_tonnes"]),
                "provenance": c["port"].get("provenance", {}),
                # --- demand intelligence, reported beside the cost, never inside it ---
                "demand_rank": (this_demand or {}).get("demand_rank"),
                "demand_note": (this_demand or {}).get("notes") or "",
                "monthly_demand_tonnes": (this_demand or {}).get("monthly_demand_tonnes"),
                "indicative_price_inr_per_tonne": (this_demand or {}).get(
                    "indicative_price_inr_per_tonne"),
                # --- weather ---
                "weather_risk_band": wx.get("risk_band", "unknown"),
                "weather_delay_days": weather_delay,
                "weather_headline": wx.get("headline", ""),
                "weather_available": bool(wx.get("available")),
            })

        if not any_viable:
            capd = capacity.deliverable(c, qty, cargo_type=cargo, allow_lightering=True)
            rejected.append(_reject_draft(c, capd))

    # --- Step 5: ranking. Landed cost per tonne decides, exactly as before.
    # Operator demand rank breaks a tie and never outranks money, because a port
    # wanting a cargo does not make that cargo cheaper to deliver there. ---
    options.sort(key=lambda o: (o["landed_cost_usd_per_tonne"],
                                int(o["demand_rank"] or 99)))

    idle = _idle_summary(options)

    port_intel = _port_intelligence(cargo, options, weather_by_port,
                                    demand_by_port, port_codes)

    if not options:
        return {
            "recommendation": {
                "action": "fix_now",
                "headline": "There is no workable answer.",
                "reason": ("No size of ship can carry this material into any east coast port "
                           "under the limits those ports have. Every combination that was "
                           "tried is listed below with the reason it was refused."),
                "confidence_label": "Not applicable, because there is nothing to recommend",
                "drivers": [],
                "expected_saving_usd_per_tonne": 0.0,
            },
            "options": [],
            "rejected": rejected,
            "forecast_summary": None,
            "all_forecasts": forecasts,
            "assumptions": ASSUMPTION_META,
            "arrival_window": {"start": window_start.isoformat(),
                               "end": window_end.isoformat(), "note": window_note},
            "port_intelligence": port_intel,
            "idle_summary": None,
            "generated_at": str(date.today()),
        }

    best = options[0]
    f = forecasts[VESSELS[best["vessel_class"]]["index_key"]]

    # A smaller class that lands cheaper is the "split the cargo" signal.
    split = None
    best_dwt = VESSELS[best["vessel_class"]]["nominal_dwt"]
    for o in options[1:]:
        if VESSELS[o["vessel_class"]]["nominal_dwt"] < best_dwt:
            split = o
            break

    # --- Step 6: timing decision ---
    rec = decision.decide(best, f, f["skill_score"], f["horizon_days"], split, overrides)

    # The two live inputs earn a place among the drivers only when they actually
    # changed something about the best option.
    if best.get("weather_delay_days"):
        rec["drivers"].append(
            f"{best['weather_delay_days']:g} day"
            f"{'' if best['weather_delay_days'] == 1 else 's'} expected to be lost to weather "
            f"at {best['discharge_port']}")
    if best.get("demand_rank") == 1:
        rec["drivers"].append(
            f"{best['discharge_port']} says this is the material it most wants")
    rec["drivers"] = rec["drivers"][:4]

    # --- Step 8: response ---
    return {
        "recommendation": rec,
        "options": options[:10],
        "rejected": rejected,
        "forecast_summary": f,
        "all_forecasts": forecasts,
        "assumptions": ASSUMPTION_META,
        "arrival_window": {"start": window_start.isoformat(),
                           "end": window_end.isoformat(), "note": window_note},
        "port_intelligence": port_intel,
        "idle_summary": idle,
        "generated_at": str(date.today()),
    }


def _port_intelligence(cargo, options, weather_by_port, demand_by_port, port_codes):
    """The operator and weather picture per port, reported beside the ranking.

    This is the answer to a different question from the one the ranking answers. The
    ranking says where this cargo lands cheapest. This says where the port itself
    says it wants the cargo, and where the weather is about to cost somebody days.
    Both belong on screen, and neither is allowed to quietly become the other.
    """
    cheapest = {}
    for o in options:
        c = o["port_code"]
        if c not in cheapest or o["landed_cost_usd_per_tonne"] < cheapest[c]:
            cheapest[c] = o["landed_cost_usd_per_tonne"]

    cargo_name = (CARGOES.get(cargo) or {}).get("name", cargo)
    rows = []
    for code in port_codes:
        port = PORTS.get(code, {})
        d = demand_by_port.get(code)
        this = (d or {}).get("this_cargo")
        wx = weather_by_port.get(code) or {}
        rows.append({
            "port_code": code,
            "port_name": port.get("name", code),
            "state": port.get("state"),
            "has_declaration": bool(d),
            "declared_by": (d or {}).get("declared_by"),
            "updated_at": (d or {}).get("updated_at"),
            "demand_rank": (this or {}).get("demand_rank"),
            "monthly_demand_tonnes": (this or {}).get("monthly_demand_tonnes"),
            "indicative_price_inr_per_tonne": (this or {}).get(
                "indicative_price_inr_per_tonne"),
            "demand_note": (this or {}).get("notes") or "",
            "top_cargo_name": (d or {}).get("top_cargo_name"),
            "best_landed_cost_usd_per_tonne": cheapest.get(code),
            "weather_risk_band": wx.get("risk_band", "unknown"),
            "weather_delay_days": wx.get("expected_weather_delay_days", 0.0),
            "weather_headline": wx.get("headline", ""),
            "weather_available": bool(wx.get("available")),
        })

    # Ports that declared demand for this cargo first, best rank first. Ports that
    # said nothing follow, because silence is not a low ranking, it is an absence.
    rows.sort(key=lambda r: (r["demand_rank"] is None, r["demand_rank"] or 99,
                             r["port_name"]))
    declared = [r for r in rows if r["demand_rank"] is not None]

    if declared:
        top = declared[0]
        headline = (f"{top['port_name']} puts {cargo_name} at number "
                    f"{top['demand_rank']} on its own list of what it most wants to receive. "
                    f"That was stated by {top['declared_by']} on "
                    f"{str(top['updated_at'])[:10]}.")
    else:
        headline = (f"No port has told us it wants {cargo_name} yet, so the ranking below is "
                    f"based on cost alone.")

    return {"cargo_type": cargo, "cargo_name": cargo_name,
            "headline": headline, "ports": rows,
            "ports_with_declarations": len(declared)}
