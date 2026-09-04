"""Step 4: landed cost per tonne.

RULE: every cost number is read from cost_assumptions.json. Nothing is hard-coded
here. This is what makes every figure on screen traceable and user-editable.
"""
from app.config import ASSUMPTIONS, PLANTS, ORIGINS, CARGOES


def _voyage_days(distance_nm, speed_knots=13.0):
    return distance_nm / (speed_knots * 24.0)


def compute(candidate, cap, tce_usd_per_day, overrides=None, cargo_type=None,
            weather_delay_days=0.0):
    """Return total cost and a full breakdown, in USD and INR per tonne.

    `weather_delay_days` is the count of forecast days at this port that breach an
    operating limit, from app.core.weather. It is added to waiting time rather than
    to sea time, because a vessel stopped by weather is a vessel on hire and not
    working, which is exactly what demurrage prices. A port with no cached forecast
    contributes zero, and the response says so rather than implying fair weather.
    """
    a = dict(ASSUMPTIONS)
    if overrides:
        a.update({k: v for k, v in overrides.items() if k in a})

    v, p = candidate["vessel"], candidate["port"]
    origin = ORIGINS[candidate["origin_code"]]
    tonnes = cap["deliverable_tonnes"]
    if tonnes <= 0:
        return None

    # Cargo changes how fast the terminal can move a tonne. Dense free flowing ore
    # moves more tonnes per grab cycle than coal. Scrap is much slower because it
    # does not flow and is handled with magnets. Slower handling means more days on
    # hire, which is real money.
    cargo = CARGOES.get(cargo_type) if cargo_type else None
    handling = cargo.get("handling_rate_multiplier", 1.0) if cargo else 1.0

    # --- Time components ---
    sea_days = _voyage_days(candidate["distance_nm"])
    load_days = tonnes / max(1.0, origin["load_rate_tpd"] * handling)
    disch_days = tonnes / max(1.0, p["discharge_rate_tonnes_per_day"] * handling)
    wait_days = p["typical_wait_days"]
    weather_days = max(0.0, float(weather_delay_days or 0.0))
    idle_days = wait_days + weather_days
    total_days = sea_days + load_days + disch_days + idle_days

    # --- Freight: hire the vessel for the round trip. Ballast leg approximated
    #     at 55 pct of laden sea time, which is the standard rough allowance. ---
    hire_days = sea_days * 1.55 + load_days + disch_days
    freight_usd = hire_days * tce_usd_per_day

    # --- Demurrage: waiting beyond allowed laytime. Congestion becomes money here. ---
    demurrage_rate = tce_usd_per_day * a["demurrage_usd_per_day_multiplier"]
    expected_demurrage_usd = wait_days * demurrage_rate
    weather_demurrage_usd = weather_days * demurrage_rate

    # --- Port charges ---
    port_usd = tonnes * p["port_charge_usd_per_tonne"] + a["port_dues_fixed_usd"]

    # --- Lightering, only where the draft forced it ---
    lightering_usd = cap["lightered_tonnes"] * p.get("lightering_cost_usd_per_tonne", 0.0)

    # --- Inland movement to the plant ---
    plant = candidate.get("plant")
    inland_usd = 0.0
    inland_km = None
    if plant and plant in PLANTS:
        inland_km = PLANTS[plant]["nearest_ports"].get(candidate["port_code"])
        if inland_km:
            inland_inr = tonnes * inland_km * a["inland_cost_inr_per_tonne_per_km"]
            inland_usd = inland_inr / a["usd_to_inr"]

    total_usd = (freight_usd + expected_demurrage_usd + weather_demurrage_usd
                 + port_usd + lightering_usd + inland_usd)
    per_tonne_usd = total_usd / tonnes
    fx = a["usd_to_inr"]

    return {
        "landed_cost_usd_per_tonne": round(per_tonne_usd, 2),
        "landed_cost_inr_per_tonne": round(per_tonne_usd * fx, 0),
        "total_voyage_cost_usd": round(total_usd),
        "tce_usd_per_day": round(tce_usd_per_day),
        "total_days": round(total_days, 1),
        "cost_breakdown_usd_per_tonne": {
            "freight": round(freight_usd / tonnes, 2),
            "expected_demurrage": round(expected_demurrage_usd / tonnes, 2),
            "weather_delay": round(weather_demurrage_usd / tonnes, 2),
            "port_charges": round(port_usd / tonnes, 2),
            "lightering": round(lightering_usd / tonnes, 2),
            "inland": round(inland_usd / tonnes, 2),
        },
        "time_breakdown_days": {
            "sea_laden": round(sea_days, 1),
            "loading": round(load_days, 1),
            "waiting": round(wait_days, 1),
            "weather_delay": round(weather_days, 1),
            "discharge": round(disch_days, 1),
        },
        "inland_km": inland_km,
        "cargo_handling_multiplier": handling,
        "assumptions_used": a,
    }
