"""Step 3: deliverable tonnes under a draft limit AND a hold volume limit.

THE CENTRAL INSIGHT OF THIS PROJECT LIVES HERE.

A voyage costs roughly the same whether the ship sails full or half full. So the
number that matters is cost divided by tonnes ACTUALLY DISCHARGED, not by nominal
capacity. At a draft-restricted port those two numbers diverge sharply.

There are TWO independent ceilings on how much cargo a vessel can carry.

1. Weight. Set by deadweight and, at a shallow port, by draft. This is what the
   draft interpolation below computes.
2. Volume. Set by the cubic capacity of the holds divided by the cargo's stowage
   factor. This is what makes cargo type matter economically.

Whichever ceiling is lower is the one that binds.

A cargo that hits the volume ceiling first is said to CUBE OUT. A cargo that hits
the weight ceiling first WEIGHS OUT. Iron ore at 0.40 m3/t always weighs out and
leaves most of the hold empty. Thermal coal at 1.30 m3/t cubes out on a Capesize,
which cannot reach its 170,000 t deadweight on coal no matter how deep the water is.

Lightering can relieve a WEIGHT restriction, because it lets the vessel load deeper
at origin and discharge the excess at anchorage. It can do nothing whatsoever about
a VOLUME restriction, because hold space is fixed. That asymmetry is modelled below.
"""
from app.config import ORIGINS, CARGOES

# Rule of thumb: a bulk carrier's deadweight scales roughly with draft. Well below
# design draft the relationship is close to linear in the operating range, so we
# use a linear approximation and expose it as an assumption.
LIGHT_DRAFT_FRACTION = 0.42   # approx draft when empty, as fraction of laden draft
MIN_ECONOMIC_LOAD = 0.30      # below this, calling the port makes no commercial sense


def deliverable(candidate, requested_tonnes, cargo_type=None, allow_lightering=True):
    """Return a dict describing how much cargo can actually be delivered."""
    v, p = candidate["vessel"], candidate["port"]
    origin = ORIGINS[candidate["origin_code"]]

    laden_draft = v["typical_laden_draft_m"]
    light_draft = laden_draft * LIGHT_DRAFT_FRACTION
    nominal = v["nominal_dwt"]

    def cap_for_draft(allowed_draft):
        if allowed_draft >= laden_draft:
            return nominal, 1.0
        if allowed_draft <= light_draft:
            return 0.0, 0.0
        frac = (allowed_draft - light_draft) / (laden_draft - light_draft)
        return nominal * frac, frac

    # --- Ceiling 1: weight, from draft at each end of the voyage ---
    load_cap, load_frac = cap_for_draft(origin["load_port_max_draft_m"])
    disch_cap, disch_frac = cap_for_draft(p["max_draft_m"])

    binding = "origin" if load_cap < disch_cap else "destination"
    hull_cap = min(load_cap, disch_cap)
    load_frac_final = min(load_frac, disch_frac)

    requires_lightering = False
    lightered_tonnes = 0.0

    # If the destination is the binding constraint and lightering is available,
    # the vessel can load more at origin and discharge the excess at anchorage.
    if allow_lightering and binding == "destination" and p.get("lightering_available") and disch_cap < load_cap:
        extra = min(load_cap, nominal) - disch_cap
        if extra > 0:
            requires_lightering = True
            lightered_tonnes = extra
            hull_cap = min(load_cap, nominal)
            load_frac_final = hull_cap / nominal

    # --- Ceiling 2: volume, from stowage factor. Lightering cannot relieve this. ---
    cargo = CARGOES.get(cargo_type) if cargo_type else None
    stowage_factor = cargo["stowage_factor_m3_per_t"] if cargo else None
    grain_m3 = v.get("grain_capacity_m3")
    volume_cap = None
    cubes_out = False

    if stowage_factor and grain_m3:
        volume_cap = grain_m3 / stowage_factor
        if volume_cap < hull_cap:
            # The holds fill before the deadweight or the draft is reached.
            cubes_out = True
            binding = "volume"
            hull_cap = volume_cap
            load_frac_final = hull_cap / nominal
            # Lightering moves weight off the ship. It cannot create hold space.
            requires_lightering = False
            lightered_tonnes = 0.0

    deliverable_tonnes = min(hull_cap, requested_tonnes)
    if requires_lightering:
        lightered_tonnes = min(lightered_tonnes, deliverable_tonnes)

    viable = load_frac_final >= MIN_ECONOMIC_LOAD and deliverable_tonnes > 0

    return {
        "nominal_capacity_tonnes": round(nominal),
        "deliverable_tonnes": round(deliverable_tonnes),
        "load_percentage": round(load_frac_final * 100, 1),
        "binding_constraint": binding,
        "binding_draft_m": (
            origin["load_port_max_draft_m"] if binding == "origin"
            else p["max_draft_m"] if binding == "destination"
            else None
        ),
        "vessel_laden_draft_m": laden_draft,
        "requires_lightering": requires_lightering,
        "lightered_tonnes": round(lightered_tonnes),
        # int, not float. This reaches the screen as a sentence, and "2.0 voyages
        # needed" is not something a person writes.
        "voyages_needed": int(max(1, -(-requested_tonnes // max(1, round(deliverable_tonnes))))) if deliverable_tonnes > 0 else None,
        "economically_viable": viable,
        "lightering_used": requires_lightering,
        # Stowage transparency. Every number on screen must be traceable.
        "stowage_factor_m3_per_t": stowage_factor,
        "grain_capacity_m3": grain_m3,
        "volume_capacity_tonnes": round(volume_cap) if volume_cap else None,
        "weight_capacity_tonnes": round(min(load_cap, disch_cap)),
        "cubes_out": cubes_out,
    }
