"""The same cargo, priced from every country that can supply it.

The problem statement names five supply origins and says the difficulty is the
varying dynamics between them. Until now this service answered "what is the best way
to bring this cargo from Australia" and had no way of answering "should it come from
Australia at all". Those are different questions and the second one is worth more,
because the sailing distance from Mozambique is roughly half the distance from the
United States and that difference dwarfs most of the others in the model.

The comparison is done by running the ordinary pipeline once per origin and reading
the best option out of each. Nothing is approximated for speed. That means every
origin's answer carries the same constraint checks, the same operator declarations
and the same weather as a single origin answer would, so a number here can be clicked
through to on the recommendation screen and it will agree.
"""
from app.config import ORIGINS, CARGOES
from app.core import pipeline


def by_origin(req, df):
    """Rank every origin that supplies this cargo by landed cost at the plant gate."""
    cargo = req["cargo_type"]
    cargo_name = (CARGOES.get(cargo) or {}).get("name", cargo)
    suppliers = [o for o in ORIGINS.values() if cargo in o["cargo"]]
    if not suppliers:
        raise ValueError(f"No origin in this system supplies {cargo_name}.")

    rows, failures = [], []
    for o in suppliers:
        try:
            res = pipeline.run({**req, "origin": o["code"]}, df)
        except ValueError as e:
            failures.append({"origin_code": o["code"], "origin": o["name"],
                             "reason": str(e)})
            continue
        opts = res.get("options") or []
        if not opts:
            failures.append({
                "origin_code": o["code"], "origin": o["name"],
                "reason": ("No ship can carry this cargo from here into any east coast port "
                           "within the limits those ports have.")})
            continue
        b = opts[0]
        rows.append({
            "origin_code": o["code"],
            "origin": o["name"],
            "vessel_class": b["vessel_class"],
            "discharge_port": b["discharge_port"],
            "distance_nm": b["distance_nm"],
            "deliverable_tonnes": b["deliverable_tonnes"],
            "load_percentage": b["load_percentage"],
            "total_days": b["total_days"],
            "landed_cost_usd_per_tonne": b["landed_cost_usd_per_tonne"],
            "landed_cost_inr_per_tonne": b["landed_cost_inr_per_tonne"],
            "load_port_max_draft_m": o.get("load_port_max_draft_m"),
            "load_rate_tpd": o.get("load_rate_tpd"),
            "unproductive_share_percent": (
                b.get("idle_and_empty_time") or {}).get("unproductive_share_percent"),
        })

    rows.sort(key=lambda r: r["landed_cost_usd_per_tonne"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
        r["extra_vs_cheapest_usd_per_tonne"] = round(
            r["landed_cost_usd_per_tonne"] - rows[0]["landed_cost_usd_per_tonne"], 2)

    if len(rows) >= 2:
        spread = rows[-1]["landed_cost_usd_per_tonne"] - rows[0]["landed_cost_usd_per_tonne"]
        headline = (f"{rows[0]['origin']} lands {cargo_name} most cheaply, at "
                    f"${rows[0]['landed_cost_usd_per_tonne']:.2f} a tonne. The dearest of the "
                    f"{len(rows)} available origins costs ${spread:.2f} a tonne more, which "
                    f"is the size of the choice being made here.")
    elif rows:
        headline = (f"{rows[0]['origin']} is the only origin in this system that supplies "
                    f"{cargo_name} and can reach an east coast port.")
    else:
        headline = f"No origin in this system can currently deliver {cargo_name}."

    return {
        "cargo_type": cargo,
        "cargo_name": cargo_name,
        "headline": headline,
        "origins": rows,
        "unavailable": failures,
        "note": ("Each row is a full run of the same pipeline used by the recommendation "
                 "screen, with the same constraint checks, the same operator declarations "
                 "and the same weather. Sailing distance is usually what separates these "
                 "numbers, because it sets both the hire days and the fuel."),
    }
