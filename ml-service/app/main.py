"""FastAPI service. Forecasting, constraints, capacity, cost and decision."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from pathlib import Path

from app.data.loaders import load_rates
from app.forecasting.train import train_all, cache
from app.forecasting import predict as fc
from app.core import pipeline
from app.core import weather
from app.api.portal import router as portal_router
from app.config import PORTS, VESSELS, ORIGINS, ASSUMPTION_META, PLANTS, CARGOES

app = FastAPI(title="Freight Charter Decision Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Port operator dashboard and public port data. See app/api/portal.py.
app.include_router(portal_router)

STATIC = Path(__file__).resolve().parents[1] / "static"


class NoStoreStatic(StaticFiles):
    """Static files that are never cached by the browser.

    The stylesheet and the fonts are served from the same machine as the page, so
    caching buys nothing measurable, and a stale copy of a stylesheet during a
    demonstration is indistinguishable from a broken build. That has already cost
    this project half an hour once. The HTML is served with no-store for the same
    reason, so the two now agree.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


app.mount("/static", NoStoreStatic(directory=str(STATIC)), name="static")

STATE = {}


class RecommendRequest(BaseModel):
    cargo_type: str = Field(..., examples=["coking_coal"])
    quantity_tonnes: float = Field(..., gt=0)
    origin: str = Field(..., examples=["AU"])
    earliest_arrival: Optional[str] = None
    latest_arrival: Optional[str] = None
    destination_plant: Optional[str] = None
    destination_port: Optional[str] = None
    horizon_days: int = 30
    overrides: Optional[Dict[str, float]] = None


@app.on_event("startup")
def startup():
    df, label, is_real = load_rates()
    STATE["df"] = df
    STATE["label"] = label
    STATE["is_real"] = is_real
    train_all(df, label, is_real)
    print(f"[startup] rates loaded: {label} | real={is_real} | rows={len(df)}")

    # Warm the weather cache on a daemon thread. Nothing on the request path is
    # allowed to wait for the network, so the recommendation pipeline reads the
    # cache only. This is what puts something in it.
    weather.prime_in_background()


@app.get("/ml/health")
def health():
    return {"status": "ok", "data_source": STATE.get("label"),
            "is_real_data": STATE.get("is_real"), **cache()["meta"]}


@app.post("/ml/recommend")
def recommend(req: RecommendRequest):
    try:
        return pipeline.run(req.model_dump(), STATE["df"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ml/forecast")
def forecast(index_key: str = "BCI", horizon_days: int = 30):
    return fc.forecast(STATE["df"], index_key, horizon_days)


@app.get("/ml/skill")
def skill():
    return {"meta": cache()["meta"], "rows": fc.skill_table()}


@app.get("/ml/history")
def history(index_key: str = "BCI", days: int = 730):
    df = STATE["df"].tail(days)
    return {"index_key": index_key, "source": STATE["label"],
            "is_real_data": STATE["is_real"],
            "points": [{"date": str(d.date()), "value": float(v)}
                       for d, v in zip(df["date"], df[index_key])]}


@app.get("/ml/reference")
def reference():
    return {"ports": list(PORTS.values()), "vessel_classes": list(VESSELS.values()),
            "origins": list(ORIGINS.values()), "plants": list(PLANTS.keys()),
            "cargo_types": list(CARGOES.values()),
            "assumptions": ASSUMPTION_META}


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError):
    """Say out loud what the client actually sent when a request fails validation.

    A 422 with no body logged is nearly undebuggable from the server side. This
    turned a stale cached dashboard into a half-hour hunt once already, so the
    offending payload is now printed rather than guessed at.

    THE ctx FIELD MUST BE STRIPPED. Pydantic v2 puts the original exception OBJECT
    into error["ctx"]["error"] whenever a custom field_validator raises. That object
    is not JSON serialisable, so serialising exc.errors() unchanged raises inside the
    handler and the client receives a bare 500 instead of the readable message the
    validator went to the trouble of writing. Every custom validator in
    app/api/portal.py depends on this. Do not put ctx back.
    """
    clean = []
    for e in exc.errors():
        item = {k: v for k, v in e.items() if k != "ctx"}
        item["loc"] = [str(x) for x in e.get("loc", ())]
        clean.append(item)
    print(f"[422] {request.method} {request.url.path} rejected. "
          f"Errors: {clean}. Body received: {exc.body}")
    return JSONResponse(status_code=422, content={"detail": clean})


def _page(name: str) -> FileResponse:
    p = STATIC / name
    # no-store, because a cached copy of this page during a demo is indistinguishable
    # from a broken build. The file is local, so there is nothing to gain by caching it.
    return FileResponse(p, headers={"Cache-Control": "no-store, must-revalidate"})


@app.get("/")
def dashboard():
    """The business dashboard. Charterers and buyers. No sign in."""
    return _page("index.html")


@app.get("/port")
def port_dashboard():
    """The port operator dashboard. One port per password. See static/port.html."""
    return _page("port.html")
