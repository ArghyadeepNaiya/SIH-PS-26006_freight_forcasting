"""Port operator declarations. The store, and the rules for using them.

WHAT THIS SOLVES. Almost every port field in data/reference/ports.json other than
draft, LOA and beam is marked ASSUMPTION, because we could not verify it from a
public source. The port operator can verify it, because it is their port. This
module lets an authenticated operator declare the truth for their own port, and
then feeds those declarations back into the recommendation the businesses see.

THE PROVENANCE RULE. A declared value never silently replaces a published one. Every
field the pipeline uses carries a provenance label, one of three.

1. PUBLISHED. Taken from data/reference/ports.json with its own source citation.
2. OPERATOR DECLARED. Supplied by the authenticated operator of that port, with the
   date they declared it.
3. ASSUMPTION. Neither of the above. Our own placeholder, still unverified.

The businesses see which of the three every number is. That is what makes an
operator declaration worth more than an assumption without pretending it is worth
as much as a published port authority figure.
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock

from app.config import BASE, PORTS, VESSELS, CARGOES

STORE = BASE / "data" / "port_owners" / "declarations"
_LOCK = Lock()

# Fields an operator may declare at port level that override a reference value the
# cost model reads. Anything not on this list is informational only, by design.
OVERRIDABLE_PORT_FIELDS = (
    "discharge_rate_tonnes_per_day",
    "typical_wait_days",
    "port_charge_usd_per_tonne",
    "lightering_cost_usd_per_tonne",
)


def _path(port_code: str) -> Path:
    # Port codes come from the session, not the URL, but a traversal guard here
    # costs nothing and means this function is safe wherever it is called from.
    if not re.fullmatch(r"[A-Z0-9]{2,10}", port_code or ""):
        raise ValueError(f"Not a valid port code: {port_code!r}")
    return STORE / f"{port_code}.json"


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def get(port_code: str):
    """Return the stored declaration for a port, or None if it has never declared."""
    p = _path(port_code)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def save(port_code: str, payload: dict, declared_by: str) -> dict:
    """Write a declaration. The write is atomic, so a crash mid-save cannot
    leave a port holding half a declaration."""
    STORE.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record["port_code"] = port_code
    record["declared_by"] = declared_by
    record["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    record["provenance"] = "OPERATOR DECLARED"

    p = _path(port_code)
    tmp = p.with_suffix(".json.tmp")
    with _LOCK:
        with open(tmp, "w") as f:
            json.dump(record, f, indent=2)
        os.replace(tmp, p)
    return record


def all_declarations() -> dict:
    """Every declaration on file, keyed by port code."""
    out = {}
    if not STORE.exists():
        return out
    for f in sorted(STORE.glob("*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
            out[d.get("port_code", f.stem)] = d
        except (json.JSONDecodeError, OSError):
            # A corrupt file must not take the whole business dashboard down.
            continue
    return out


def blank(port_code: str) -> dict:
    """An empty declaration prefilled from the published reference record.

    The operator starts from what we currently believe about their port, so their
    job is to correct us rather than to type everything from nothing.
    """
    p = PORTS.get(port_code, {})
    return {
        "port_code": port_code,
        "declared_by": "",
        "updated_at": None,
        "areas": [],
        "cargo_demand": [],
        "operational": {
            "discharge_rate_tonnes_per_day": p.get("discharge_rate_tonnes_per_day"),
            "typical_wait_days": p.get("typical_wait_days"),
            "port_charge_usd_per_tonne": p.get("port_charge_usd_per_tonne"),
            "lightering_cost_usd_per_tonne": p.get("lightering_cost_usd_per_tonne"),
        },
        "operator_notes": "",
    }


# --------------------------------------------------------------------------
# Reading a declaration back into the pipeline
# --------------------------------------------------------------------------

def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def total_declared_area(decl) -> dict:
    """Total laydown area and storage tonnage across every declared area."""
    areas = (decl or {}).get("areas") or []
    return {
        "area_count": len(areas),
        "total_area_sq_m": round(sum(float(a.get("area_sq_m") or 0) for a in areas), 1),
        "total_storage_tonnes": round(
            sum(float(a.get("storage_capacity_tonnes") or 0) for a in areas), 1),
    }


def areas_for_vessel(decl, vessel_class: str):
    """Every declared area that says it can take this class of ship."""
    out = []
    for a in (decl or {}).get("areas") or []:
        accepts = a.get("accepts_vessel_classes") or []
        if vessel_class in accepts:
            out.append(a)
    return out


def available_window(area, window_start: date, window_end: date):
    """Does this area's declared availability window overlap the arrival window.

    An area with no dates declared is treated as available. An operator who has not
    said when the area frees up has not told us it is blocked, and inventing a
    blockage would be worse than admitting we do not know.
    """
    a_from = _parse_date(area.get("available_from"))
    a_to = _parse_date(area.get("available_to"))
    if a_from is None and a_to is None:
        return True, "no availability window declared, treated as open"
    if a_from and window_end < a_from:
        return False, f"area frees up on {a_from.isoformat()}, after the arrival window closes"
    if a_to and window_start > a_to:
        return False, f"area is released on {a_to.isoformat()}, before the arrival window opens"
    return True, (
        f"available {a_from.isoformat() if a_from else 'now'} to "
        f"{a_to.isoformat() if a_to else 'open ended'}"
    )


def berth_offer(port_code: str, vessel_class: str, window_start: date, window_end: date):
    """Decide what the operator of this port is offering this ship in this window.

    Returns a dict with a `status` of one of three values.

    1. `no_declaration`. The operator has never declared. The pipeline falls back to
       published and assumed reference values, exactly as it did before.
    2. `offered`. At least one declared area accepts this class and is free in the
       window. The best such area is returned.
    3. `refused`. The operator has declared areas, but none accepts this class, or
       none that accepts it is free in the window. This becomes a rejection the
       business sees, with the operator and the declaration date named.
    """
    decl = get(port_code)
    if not decl or not (decl.get("areas") or []):
        return {"status": "no_declaration", "declaration": decl}

    matching = areas_for_vessel(decl, vessel_class)
    if not matching:
        classes = sorted({c for a in decl["areas"]
                          for c in (a.get("accepts_vessel_classes") or [])})
        return {
            "status": "refused",
            "reason": "vessel_class_not_accepted",
            "declaration": decl,
            "explanation": (
                f"The operator of {PORTS.get(port_code, {}).get('name', port_code)} "
                f"declares {len(decl['areas'])} handling area"
                f"{'' if len(decl['areas']) == 1 else 's'}, and none of them accepts a "
                f"{vessel_class}. Declared classes are "
                f"{', '.join(classes) if classes else 'none'}."
            ),
        }

    free, blocked = [], []
    for a in matching:
        ok, note = available_window(a, window_start, window_end)
        (free if ok else blocked).append((a, note))

    if not free:
        first = blocked[0]
        return {
            "status": "refused",
            "reason": "no_area_available_in_window",
            "declaration": decl,
            "explanation": (
                f"The operator of {PORTS.get(port_code, {}).get('name', port_code)} "
                f"can take a {vessel_class}, but every yard that can is already committed "
                f"for the whole period the cargo would arrive in, "
                f"{window_start.isoformat()} to {window_end.isoformat()}. The nearest one, "
                f"{first[0].get('name', 'unnamed area')}, {first[1]}."
            ),
        }

    # Prefer the area that can physically take the deepest ship, then the largest.
    # A deeper berth is worth more than a bigger one, because draft is what caps
    # deliverable tonnes and therefore landed cost per tonne.
    free.sort(key=lambda t: (
        float(t[0].get("max_draft_m") or 0),
        float(t[0].get("area_sq_m") or 0),
    ), reverse=True)
    area, note = free[0]
    return {
        "status": "offered",
        "declaration": decl,
        "area": area,
        "availability_note": note,
        "alternatives": len(free) - 1,
    }


def effective_port(port_code: str, area=None) -> dict:
    """The port record the cost model should use, with provenance for every field.

    Published reference values are the base. Operator declarations override them.
    An area level declaration overrides a port level one, because the operator is
    telling us about the specific berth this ship would use.
    """
    base = dict(PORTS.get(port_code, {}))
    cites = dict(base.get("citations", {}))
    decl = get(port_code)

    provenance = {}
    for field in OVERRIDABLE_PORT_FIELDS:
        cite = cites.get(field, "")
        provenance[field] = {
            "value": base.get(field),
            "source": "ASSUMPTION" if "ASSUMPTION" in str(cite) else "PUBLISHED",
            "citation": cite or "no citation recorded",
        }
    provenance["max_draft_m"] = {
        "value": base.get("max_draft_m"),
        "source": "ASSUMPTION" if "ASSUMPTION" in str(cites.get("max_draft_m", "")) else "PUBLISHED",
        "citation": cites.get("max_draft_m", "no citation recorded"),
    }

    if decl:
        stamp = decl.get("updated_at", "unknown date")
        who = decl.get("declared_by") or "the port operator"
        op = decl.get("operational") or {}
        for field in OVERRIDABLE_PORT_FIELDS:
            val = op.get(field)
            if val is None or val == "":
                continue
            base[field] = float(val)
            provenance[field] = {
                "value": float(val),
                "source": "OPERATOR DECLARED",
                "citation": f"Declared by {who} for this port on {stamp}.",
            }

        if area:
            stamp_a = f"Declared by {who} for area {area.get('name', 'unnamed')} on {stamp}."
            for field in ("discharge_rate_tonnes_per_day",):
                val = area.get(field)
                if val not in (None, ""):
                    base[field] = float(val)
                    provenance[field] = {
                        "value": float(val), "source": "OPERATOR DECLARED",
                        "citation": stamp_a,
                    }
            if area.get("current_wait_days") not in (None, ""):
                base["typical_wait_days"] = float(area["current_wait_days"])
                provenance["typical_wait_days"] = {
                    "value": float(area["current_wait_days"]),
                    "source": "OPERATOR DECLARED",
                    "citation": stamp_a,
                }
            # A declared berth draft is only allowed to be MORE restrictive than the
            # published port maximum. An operator may tell us their berth is shoaled
            # today. An operator may not talk their way past a published port limit,
            # because the physical channel does not care what anyone declares.
            if area.get("max_draft_m") not in (None, ""):
                declared = float(area["max_draft_m"])
                published = float(base.get("max_draft_m") or declared)
                if declared < published:
                    base["max_draft_m"] = declared
                    provenance["max_draft_m"] = {
                        "value": declared, "source": "OPERATOR DECLARED",
                        "citation": (f"{stamp_a} This is below the published port maximum "
                                     f"of {published} m and is therefore applied."),
                    }
                else:
                    provenance["max_draft_m"]["citation"] += (
                        f" The operator declared {declared} m for this berth, which is not "
                        f"below the published port maximum, so the published figure stands."
                    )

    base["provenance"] = provenance
    return base


def demand_for(port_code: str, cargo_type: str):
    """What the operator says about demand for this cargo at this port.

    This is intelligence for the business, not an input to the cost. A port that is
    short of coking coal does not make coking coal cheaper to deliver there. It does
    tell a charterer where a cargo will find a buyer, which is a different and
    genuinely useful thing, so it is reported separately and never folded into the
    landed cost figure.
    """
    decl = get(port_code)
    if not decl:
        return None
    rows = decl.get("cargo_demand") or []
    if not rows:
        return None
    ordered = sorted(rows, key=lambda r: int(r.get("demand_rank") or 99))
    match = next((r for r in ordered if r.get("cargo_type") == cargo_type), None)
    top = ordered[0] if ordered else None
    cargo_name = (CARGOES.get(cargo_type) or {}).get("name", cargo_type)
    return {
        "declared_by": decl.get("declared_by") or "the port operator",
        "updated_at": decl.get("updated_at"),
        "this_cargo": match,
        "this_cargo_name": cargo_name,
        "top_cargo": top,
        "top_cargo_name": (CARGOES.get((top or {}).get("cargo_type")) or {}).get(
            "name", (top or {}).get("cargo_type")),
        "ranked": ordered,
    }


def public_summary() -> list:
    """Everything the business dashboard is allowed to see, for every port.

    Nothing here is secret. An operator declaring open capacity is advertising it.
    What is deliberately not exposed anywhere is the credential file, which this
    module never reads.
    """
    decls = all_declarations()
    out = []
    for code, port in PORTS.items():
        d = decls.get(code)
        totals = total_declared_area(d)
        ranked = sorted((d or {}).get("cargo_demand") or [],
                        key=lambda r: int(r.get("demand_rank") or 99))
        out.append({
            "port_code": code,
            "port_name": port["name"],
            "state": port.get("state"),
            "has_declaration": bool(d),
            "declared_by": (d or {}).get("declared_by"),
            "updated_at": (d or {}).get("updated_at"),
            "operator_notes": (d or {}).get("operator_notes") or "",
            **totals,
            "areas": [
                {
                    "name": a.get("name"),
                    "area_sq_m": a.get("area_sq_m"),
                    "storage_capacity_tonnes": a.get("storage_capacity_tonnes"),
                    "available_from": a.get("available_from"),
                    "available_to": a.get("available_to"),
                    "accepts_vessel_classes": a.get("accepts_vessel_classes") or [],
                    "max_draft_m": a.get("max_draft_m"),
                    "discharge_rate_tonnes_per_day": a.get("discharge_rate_tonnes_per_day"),
                    "current_wait_days": a.get("current_wait_days"),
                    "notes": a.get("notes") or "",
                }
                for a in (d or {}).get("areas") or []
            ],
            "cargo_demand": [
                {
                    **r,
                    "cargo_name": (CARGOES.get(r.get("cargo_type")) or {}).get(
                        "name", r.get("cargo_type")),
                }
                for r in ranked
            ],
            "operational": (d or {}).get("operational") or {},
        })
    return out
