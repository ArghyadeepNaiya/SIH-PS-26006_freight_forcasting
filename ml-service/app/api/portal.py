"""HTTP surface for the port operator dashboard and the public port data.

THE TWO HALVES OF THIS FILE.

The first half is behind a password. An authenticated port operator can read and
write the declaration for THEIR OWN PORT AND NO OTHER. The port code is never taken
from the request body or the URL. It is taken from the session token, so there is no
request an operator can construct that edits somebody else's port.

The second half is deliberately public. What an operator declares about free area,
availability and cargo demand is an advertisement, and the whole point of collecting
it is that charterers and buyers see it. The credential file is never read by
anything in this half, and no endpoint here returns a hash, a salt or a token.

Validation is strict and the error messages are written to be read aloud. A port
operator filling this in has a paper berth plan beside them, not a JSON schema.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.config import PORTS, VESSELS, CARGOES
from app.core import declarations as decl
from app.core import portal_auth as auth
from app.core import weather

router = APIRouter()

VESSEL_NAMES = list(VESSELS.keys())
CARGO_CODES = list(CARGOES.keys())


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    port_code: str = Field(..., examples=["INPRT"])
    password: str = Field(..., examples=["winch-yardarm-anchor-8725"])


class Area(BaseModel):
    """One handling or laydown area the operator is declaring."""
    name: str = Field(..., min_length=1, max_length=80)
    area_sq_m: float = Field(..., gt=0, le=10_000_000)
    storage_capacity_tonnes: Optional[float] = Field(None, ge=0, le=10_000_000)
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    accepts_vessel_classes: List[str] = Field(default_factory=list)
    max_draft_m: Optional[float] = Field(None, gt=0, le=30)
    discharge_rate_tonnes_per_day: Optional[float] = Field(None, gt=0, le=500_000)
    current_wait_days: Optional[float] = Field(None, ge=0, le=90)
    notes: str = Field("", max_length=600)

    @field_validator("available_from", "available_to")
    @classmethod
    def _date_shape(cls, v):
        if v in (None, ""):
            return None
        try:
            datetime.strptime(v[:10], "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                "Dates must be written as four digit year, then month, then day, "
                "separated by hyphens. For example 2026-10-01."
            )
        return v[:10]

    @field_validator("accepts_vessel_classes")
    @classmethod
    def _known_classes(cls, v):
        unknown = [c for c in v if c not in VESSEL_NAMES]
        if unknown:
            raise ValueError(
                f"Unknown vessel class {', '.join(unknown)}. The classes this system "
                f"models are {', '.join(VESSEL_NAMES)}."
            )
        return v


class CargoDemand(BaseModel):
    """One line of the operator's own demand ranking for their port."""
    cargo_type: str
    demand_rank: int = Field(..., ge=1, le=20)
    monthly_demand_tonnes: Optional[float] = Field(None, ge=0, le=50_000_000)
    indicative_price_inr_per_tonne: Optional[float] = Field(None, ge=0, le=10_000_000)
    notes: str = Field("", max_length=600)

    @field_validator("cargo_type")
    @classmethod
    def _known_cargo(cls, v):
        if v not in CARGO_CODES:
            raise ValueError(
                f"Unknown cargo type {v}. This system models "
                f"{', '.join(CARGO_CODES)}."
            )
        return v


class Operational(BaseModel):
    """Port level operating figures. These override reference values in the cost model."""
    discharge_rate_tonnes_per_day: Optional[float] = Field(None, gt=0, le=500_000)
    typical_wait_days: Optional[float] = Field(None, ge=0, le=90)
    port_charge_usd_per_tonne: Optional[float] = Field(None, ge=0, le=1000)
    lightering_cost_usd_per_tonne: Optional[float] = Field(None, ge=0, le=1000)


class DeclarationRequest(BaseModel):
    declared_by: str = Field(..., min_length=2, max_length=120)
    areas: List[Area] = Field(default_factory=list)
    cargo_demand: List[CargoDemand] = Field(default_factory=list)
    operational: Operational = Field(default_factory=Operational)
    operator_notes: str = Field("", max_length=2000)

    @field_validator("areas")
    @classmethod
    def _area_dates_ordered(cls, areas):
        for a in areas:
            if a.available_from and a.available_to and a.available_to < a.available_from:
                raise ValueError(
                    f"Area {a.name} is declared available from {a.available_from} "
                    f"until {a.available_to}, which ends before it starts."
                )
        return areas

    @field_validator("cargo_demand")
    @classmethod
    def _one_line_per_cargo(cls, rows):
        seen = set()
        for r in rows:
            if r.cargo_type in seen:
                raise ValueError(
                    f"{r.cargo_type} appears twice in the demand list. Give each cargo "
                    f"one line with one rank."
                )
            seen.add(r.cargo_type)
        return rows


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def _session_port(authorization: Optional[str]) -> str:
    """The port code this request is allowed to touch, from the bearer token alone."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    try:
        return auth.resolve(token)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


# ---------------------------------------------------------------------------
# Authenticated half. Port operators only, and only their own port.
# ---------------------------------------------------------------------------

@router.get("/ml/portal/status")
def portal_status():
    """Non-secret provisioning summary for the sign-in page."""
    st = auth.provisioning_status()
    st["ports"] = [{"code": c, "name": p["name"], "state": p.get("state")}
                   for c, p in PORTS.items()]
    return st


@router.post("/ml/portal/login")
def portal_login(req: LoginRequest):
    try:
        return auth.login(req.port_code, req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/ml/portal/logout")
def portal_logout(authorization: Optional[str] = Header(None)):
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    auth.logout(token)
    return {"signed_out": True}


@router.get("/ml/portal/declaration")
def portal_get_declaration(authorization: Optional[str] = Header(None)):
    """Everything the operator's dashboard needs to draw itself, in one request.

    The current declaration if there is one, otherwise a blank prefilled from the
    published reference record so the operator corrects us rather than typing from
    nothing. Plus the vessel classes and cargo types they may choose from, so the
    form is never out of step with the reference data.
    """
    code = _session_port(authorization)
    port = PORTS.get(code, {})
    current = decl.get(code)
    return {
        "port_code": code,
        "port_name": port.get("name", code),
        "state": port.get("state"),
        "has_declaration": bool(current),
        "declaration": current or decl.blank(code),
        "published_reference": {
            "max_draft_m": port.get("max_draft_m"),
            "max_loa_m": port.get("max_loa_m"),
            "max_beam_m": port.get("max_beam_m"),
            "max_dwt": port.get("max_dwt"),
            "lightering_available": port.get("lightering_available"),
            "citations": port.get("citations", {}),
        },
        "vessel_classes": [
            {"name": v["name"], "nominal_dwt": v["nominal_dwt"],
             "typical_laden_draft_m": v["typical_laden_draft_m"],
             "typical_loa_m": v["typical_loa_m"]}
            for v in VESSELS.values()
        ],
        "cargo_types": [{"code": c["code"], "name": c["name"]} for c in CARGOES.values()],
        "effective": decl.effective_port(code),
        "totals": decl.total_declared_area(current),
    }


@router.put("/ml/portal/declaration")
def portal_put_declaration(req: DeclarationRequest,
                           authorization: Optional[str] = Header(None)):
    """Save this operator's declaration. The port code comes from the session."""
    code = _session_port(authorization)
    payload = req.model_dump()

    # A declared berth draft deeper than the published port maximum is refused here
    # as well as ignored downstream, so the operator finds out at the moment they
    # type it rather than wondering later why nothing changed.
    published = PORTS.get(code, {}).get("max_draft_m")
    if published:
        for a in payload["areas"]:
            if a.get("max_draft_m") and float(a["max_draft_m"]) > float(published) + 0.001:
                raise HTTPException(status_code=400, detail=(
                    f"Area {a['name']} is declared at {a['max_draft_m']} m of draft, "
                    f"which is deeper than the published maximum for this port of "
                    f"{published} m. A berth may be declared shallower than the port "
                    f"limit, for instance when it has shoaled, but not deeper, because "
                    f"the approach channel governs. Correct the figure, or ask the "
                    f"project team to update the published port record with a source."
                ))

    saved = decl.save(code, payload, declared_by=req.declared_by)
    return {
        "saved": True,
        "port_code": code,
        "updated_at": saved["updated_at"],
        "totals": decl.total_declared_area(saved),
        "message": (
            f"Saved. {len(payload['areas'])} handling area"
            f"{'' if len(payload['areas']) == 1 else 's'} and "
            f"{len(payload['cargo_demand'])} cargo demand line"
            f"{'' if len(payload['cargo_demand']) == 1 else 's'} are now visible to "
            f"charterers on the business dashboard, labelled as operator declared."
        ),
        "declaration": saved,
    }


@router.get("/ml/portal/weather")
def portal_weather(refresh: bool = Query(False),
                   authorization: Optional[str] = Header(None)):
    """The full forecast for this operator's own port and its approach anchorage."""
    code = _session_port(authorization)
    return weather.for_port(code, force=bool(refresh), cache_only=not refresh)


# ---------------------------------------------------------------------------
# Public half. No authentication, and nothing secret is reachable from here.
# ---------------------------------------------------------------------------

@router.get("/ml/ports/declarations")
def public_declarations():
    """What every port operator has declared, for the business dashboard."""
    rows = decl.public_summary()
    return {
        "ports": rows,
        "ports_declared": sum(1 for r in rows if r["has_declaration"]),
        "ports_total": len(rows),
        "provenance_note": (
            "Everything on this page marked operator declared was entered by the "
            "operator of that port through their own password protected dashboard. "
            "It is not a published port authority figure and is not independently "
            "verified. It is dated, and it is attributed."
        ),
    }


@router.get("/ml/weather")
def public_weather(refresh: bool = Query(False)):
    """The advisory for every port. Cache only unless a refresh is asked for."""
    rows = weather.for_all_ports(force=bool(refresh), cache_only=not refresh)
    return {
        "ports": rows,
        "offline_mode": weather.offline(),
        "provider": "Open-Meteo forecast and marine APIs. No API key required.",
        "note": (
            "Wind, rain and wave forecasts are compared against the operating limits "
            "in data/reference/weather_thresholds.json. A day that breaches a limit "
            "is counted as a day of lost handling, and lost days are priced as "
            "demurrage in the landed cost."
        ),
    }


@router.get("/ml/weather/{port_code}")
def public_weather_one(port_code: str, refresh: bool = Query(False)):
    try:
        return weather.for_port(port_code.upper(), force=bool(refresh),
                                cache_only=not refresh)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
