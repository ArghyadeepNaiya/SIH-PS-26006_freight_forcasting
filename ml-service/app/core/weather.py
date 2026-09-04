"""Weather for a discharge port and its approach anchorage.

PROVIDER. Open-Meteo. Chosen because it needs no API key, no registration and no
billing account, which matters for a team that has to hand this project to judges
who will run it themselves. Two endpoints are used, the land forecast for wind and
rain, and the marine forecast for significant wave height.

STANDING RULE 4 OF THIS PROJECT SAYS NO LIVE EXTERNAL API CALL DURING A
DEMONSTRATION. This module obeys that in three layers.

1. Every response is cached to data/cache/weather as JSON with a fetch timestamp.
   A cache entry younger than the configured window is served without any network
   call at all.
2. Setting FREIGHT_WEATHER_OFFLINE=1 blocks the network entirely. A stale cache is
   then served and clearly labelled as stale. If there is no cache, a labelled
   unavailable response is returned rather than a fabricated forecast.
3. Every call has a hard timeout and every failure degrades to the cache. The
   dashboard never blocks and never breaks because the internet did.

Prime the cache before a demonstration with:

    python3 scripts/prime_weather_cache.py

WHAT THE FORECAST IS TURNED INTO. Raw wind and wave numbers do not help a charterer.
Days of lost handling do. Each forecast day is compared against the operating limits
in data/reference/weather_thresholds.json and counted as workable or not. The output
is a count of expected weather delay days over the forecast horizon, which is a
number that can be added to waiting time and therefore to demurrage.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from app.config import BASE, PORTS

CACHE = BASE / "data" / "cache" / "weather"
THRESHOLD_FILE = BASE / "data" / "reference" / "weather_thresholds.json"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
TIMEOUT_SECONDS = 6
FORECAST_DAYS = 7


def _cfg():
    with open(THRESHOLD_FILE) as f:
        return json.load(f)


def offline() -> bool:
    return os.environ.get("FREIGHT_WEATHER_OFFLINE", "").strip() in ("1", "true", "yes")


# --------------------------------------------------------------------------
# Fetching, with cache
# --------------------------------------------------------------------------

def _cache_path(key: str) -> Path:
    return CACHE / f"{key}.json"


def _read_cache(key: str):
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(key: str, payload: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = _cache_path(key)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, p)


def _http_json(url: str, params: dict):
    q = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(
        f"{url}?{q}",
        headers={"User-Agent": "SIH26006-freight-forecasting/0.1 (charter decision prototype)"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_point(lat: float, lon: float) -> dict:
    """One land forecast and one marine forecast for a single position."""
    land = _http_json(FORECAST_URL, {
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "daily": ["wind_speed_10m_max", "wind_gusts_10m_max", "precipitation_sum",
                  "weather_code", "temperature_2m_max"],
        "current": ["wind_speed_10m", "wind_direction_10m", "temperature_2m",
                    "precipitation", "weather_code"],
        "wind_speed_unit": "ms", "timezone": "Asia/Kolkata",
        "forecast_days": FORECAST_DAYS,
    })
    marine = None
    try:
        marine = _http_json(MARINE_URL, {
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "daily": ["wave_height_max", "wave_period_max", "swell_wave_height_max"],
            "timezone": "Asia/Kolkata", "forecast_days": FORECAST_DAYS,
        })
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        # The marine grid does not cover every coordinate. A missing wave forecast
        # degrades the advisory rather than failing it, and says so on screen.
        marine = None
    return {"land": land, "marine": marine}


def _point(key: str, lat: float, lon: float, max_age_hours: float, force: bool = False,
           cache_only: bool = False):
    """Cached fetch for one position. Returns (payload, freshness_dict).

    `cache_only` reads the cache and never touches the network, whatever the age of
    the entry. Every caller on the recommendation path uses it, because a
    recommendation must never sit waiting on somebody else's web service. The
    dedicated weather endpoints and the priming script are the only callers allowed
    to fetch.
    """
    cached = _read_cache(key)
    now = time.time()

    if cached and not force:
        age_h = (now - cached.get("fetched_at", 0)) / 3600.0
        if age_h < max_age_hours:
            return cached["data"], {
                "source": "cache", "age_hours": round(age_h, 2), "stale": False,
                "fetched_at": cached.get("fetched_at_iso"),
            }

    if cache_only and not force:
        if cached:
            age_h = (now - cached.get("fetched_at", 0)) / 3600.0
            return cached["data"], {
                "source": "cache", "age_hours": round(age_h, 2), "stale": True,
                "fetched_at": cached.get("fetched_at_iso"),
                "note": ("Served from cache without a network call. Refresh the "
                         "forecast to get a current one."),
            }
        return None, {
            "source": "unavailable", "stale": True,
            "note": ("Nothing is cached for this position yet and this request is not "
                     "allowed to fetch. Refresh the forecast, or run "
                     "scripts/prime_weather_cache.py."),
        }

    if offline() and not force:
        if cached:
            age_h = (now - cached.get("fetched_at", 0)) / 3600.0
            return cached["data"], {
                "source": "cache", "age_hours": round(age_h, 2), "stale": True,
                "fetched_at": cached.get("fetched_at_iso"),
                "note": ("Offline mode is on, so this is the last cached forecast and "
                         "may be out of date."),
            }
        return None, {
            "source": "unavailable", "stale": True,
            "note": ("Offline mode is on and nothing is cached for this position. "
                     "Run scripts/prime_weather_cache.py with a network connection."),
        }

    try:
        data = _fetch_point(lat, lon)
        _write_cache(key, {
            "fetched_at": now,
            "fetched_at_iso": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "lat": lat, "lon": lon, "data": data,
        })
        return data, {"source": "live", "age_hours": 0.0, "stale": False,
                      "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            OSError, ValueError) as e:
        if cached:
            age_h = (now - cached.get("fetched_at", 0)) / 3600.0
            return cached["data"], {
                "source": "cache", "age_hours": round(age_h, 2), "stale": True,
                "fetched_at": cached.get("fetched_at_iso"),
                "note": f"Live fetch failed, serving the cached forecast. {e}",
            }
        return None, {"source": "unavailable", "stale": True,
                      "note": f"Weather could not be fetched and nothing is cached. {e}"}


# --------------------------------------------------------------------------
# Turning a forecast into a berthing and handling advisory
# --------------------------------------------------------------------------

def _daily_rows(payload):
    """Flatten the land and marine daily arrays into one row per day."""
    if not payload or not payload.get("land"):
        return []
    d = payload["land"].get("daily") or {}
    dates = d.get("time") or []
    marine = ((payload.get("marine") or {}).get("daily")) or {}
    m_dates = marine.get("time") or []
    m_index = {t: i for i, t in enumerate(m_dates)}

    rows = []
    for i, day in enumerate(dates):
        j = m_index.get(day)
        rows.append({
            "date": day,
            "wind_speed_ms_max": _at(d.get("wind_speed_10m_max"), i),
            "wind_gust_ms_max": _at(d.get("wind_gusts_10m_max"), i),
            "precipitation_mm": _at(d.get("precipitation_sum"), i),
            "temperature_c_max": _at(d.get("temperature_2m_max"), i),
            "weather_code": _at(d.get("weather_code"), i),
            "wave_height_m_max": _at(marine.get("wave_height_max"), j),
            "swell_height_m_max": _at(marine.get("swell_wave_height_max"), j),
        })
    return rows


def _at(arr, i):
    if arr is None or i is None or i >= len(arr):
        return None
    return arr[i]


def assess(rows, thresholds, is_anchorage: bool):
    """Mark each forecast day workable or not, and say which limit was breached."""
    t = {k: v["value"] for k, v in thresholds["thresholds"].items()}
    out, lost = [], 0.0

    for r in rows:
        breaches = []
        wind = r.get("wind_speed_ms_max")
        gust = r.get("wind_gust_ms_max")
        wave = r.get("wave_height_m_max")
        rain = r.get("precipitation_mm")

        if wind is not None and wind >= t["wind_speed_ms_grab_crane_suspend"]:
            breaches.append(
                f"wind {wind:.1f} m/s reaches the {t['wind_speed_ms_grab_crane_suspend']} m/s "
                f"grab crane suspension limit")
        elif wind is not None and wind >= t["wind_speed_ms_berthing_suspend"]:
            breaches.append(
                f"wind {wind:.1f} m/s reaches the {t['wind_speed_ms_berthing_suspend']} m/s "
                f"berthing restriction limit")
        if gust is not None and gust >= t["wind_speed_ms_grab_crane_suspend"] + 5:
            breaches.append(f"gusts to {gust:.1f} m/s")
        if wave is not None:
            limit = (t["wave_height_m_lightering_suspend"] if is_anchorage
                     else t["wave_height_m_berthing_caution"])
            label = ("lightering suspension" if is_anchorage else "berthing caution")
            if wave >= limit:
                breaches.append(f"significant wave height {wave:.1f} m reaches the "
                                f"{limit} m {label} limit")
        if rain is not None and rain >= t["precipitation_mm_handling_suspend"]:
            breaches.append(f"rainfall {rain:.0f} mm reaches the "
                            f"{t['precipitation_mm_handling_suspend']} mm wet weather limit")

        workable = not breaches
        if not workable:
            lost += t["days_lost_per_suspended_day"]
        out.append({**r, "workable": workable, "breaches": breaches})

    total = len(out)
    if total == 0:
        band, headline = "unknown", "No forecast available for this position."
    elif lost == 0:
        band = "clear"
        headline = f"All {total} forecast days are workable at this position."
    elif lost / total <= 0.29:
        band = "caution"
        headline = (f"{int(lost)} of {total} forecast days breach an operating limit. "
                    f"Expect minor delay.")
    else:
        band = "disrupted"
        headline = (f"{int(lost)} of {total} forecast days breach an operating limit. "
                    f"Expect material delay to berthing or handling.")

    return {"days": out, "days_forecast": total, "delay_days": round(lost, 1),
            "risk_band": band, "headline": headline}


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def _uncap(sentence: str) -> str:
    """Lower the first letter of a sentence being embedded inside another one.

    Only the first letter, and only when the word is not already all capitals, so
    an acronym or a port name that legitimately starts a clause is left alone.
    """
    s = (sentence or "").strip()
    if not s or s[:2].isupper():
        return s
    return s[0].lower() + s[1:]


def for_port(port_code: str, force: bool = False, cache_only: bool = False) -> dict:
    """Weather at the quay and at the approach anchorage, plus the advisory.

    The anchorage point matters as much as the quay. A vessel waiting to come in,
    or lightering at anchorage as it must at Sagar and Sandheads, is exposed to sea
    state that the quay never feels.
    """
    port = PORTS.get(port_code)
    if port is None:
        raise ValueError(f"Unknown port code: {port_code}")

    cfg = _cfg()
    max_age = float(cfg["cache_hours"]["value"])
    offset = float(cfg["nearby_offset_deg"]["value"])

    # East coast of India, so seaward is east and south of the port position.
    near_lat = round(port["lat"] - offset * 0.4, 4)
    near_lon = round(port["lon"] + offset, 4)

    quay_data, quay_meta = _point(f"{port_code}_quay", port["lat"], port["lon"],
                                  max_age, force, cache_only)
    anch_data, anch_meta = _point(f"{port_code}_anchorage", near_lat, near_lon,
                                  max_age, force, cache_only)

    quay_rows = _daily_rows(quay_data)
    anch_rows = _daily_rows(anch_data)
    quay = assess(quay_rows, cfg, is_anchorage=False)
    anch = assess(anch_rows, cfg, is_anchorage=True)

    # The binding advisory is the worse of the two. A ship that cannot reach the
    # berth is delayed just as surely as one that cannot be discharged at it.
    delay = max(quay["delay_days"], anch["delay_days"])
    band = max([quay["risk_band"], anch["risk_band"]],
               key=lambda b: ["unknown", "clear", "caution", "disrupted"].index(b))

    current = ((quay_data or {}).get("land") or {}).get("current") or {}

    return {
        "port_code": port_code,
        "port_name": port["name"],
        "state": port.get("state"),
        "position": {"lat": port["lat"], "lon": port["lon"]},
        "anchorage_position": {"lat": near_lat, "lon": near_lon},
        "current": {
            "wind_speed_ms": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "temperature_c": current.get("temperature_2m"),
            "precipitation_mm": current.get("precipitation"),
        },
        "quay": quay,
        "anchorage": anch,
        "advisory": {
            "risk_band": band,
            "expected_weather_delay_days": delay,
            # Each part is a sentence in its own right, so its first letter is
            # lowered when it is glued into the middle of this one. Without this the
            # advisory reads "At the quay, All 7 forecast days are workable".
            "headline": (
                f"{port['name']}. At the quay, {_uncap(quay['headline'])} At the "
                f"approach anchorage, {_uncap(anch['headline'])}"
            ),
            "applies_to_lightering": bool(port.get("lightering_available")),
        },
        "freshness": {"quay": quay_meta, "anchorage": anch_meta,
                      "offline_mode": offline()},
        "thresholds": cfg["thresholds"],
        "provider": cfg["_provider"],
        "marine_data_available": bool((quay_data or {}).get("marine")
                                      or (anch_data or {}).get("marine")),
    }


def advisory(port_code: str) -> dict:
    """The advisory only, read from cache, for the recommendation pipeline.

    Never raises and never opens a socket. A port with nothing cached returns an
    advisory that says so, rather than a fabricated one.
    """
    try:
        w = for_port(port_code, cache_only=True)
    except (ValueError, KeyError, TypeError):
        w = None
    if not w or not w.get("quay", {}).get("days_forecast"):
        return {
            "available": False,
            "risk_band": "unknown",
            "expected_weather_delay_days": 0.0,
            "headline": ("No forecast is cached for this port, so no weather delay has "
                         "been added to the cost. This is not a claim that the weather "
                         "is good."),
            "freshness": (w or {}).get("freshness"),
        }
    adv = dict(w["advisory"])
    adv["available"] = True
    adv["freshness"] = w["freshness"]
    adv["current"] = w["current"]
    return adv


def delay_days(port_code: str) -> float:
    """Just the number, for the cost model. Never raises, never blocks on network.

    A port whose weather cannot be determined contributes zero delay rather than a
    guess. Inventing a delay would put a number on screen that no source supports,
    which standing rule 2 of this project forbids.
    """
    return float(advisory(port_code)["expected_weather_delay_days"])


def for_all_ports(force: bool = False, cache_only: bool = False) -> list:
    out = []
    for code in PORTS:
        try:
            out.append(for_port(code, force=force, cache_only=cache_only))
        except (ValueError, KeyError) as e:
            out.append({"port_code": code, "error": str(e)})
    return out


def prime_in_background() -> None:
    """Warm the cache for every port on a daemon thread at service startup.

    The dashboard therefore has a forecast to show almost immediately, while nothing
    on the request path ever waits for the network. If the machine is offline the
    thread fails quietly and every reader falls back to the cache or to a labelled
    unavailable advisory.
    """
    import threading

    def work():
        if offline():
            print("[weather] offline mode is on, so the cache was not primed.")
            return
        fetched = warm = 0
        for code in PORTS:
            try:
                w = for_port(code)
                if w["freshness"]["quay"]["source"] == "live":
                    fetched += 1
                elif not w["freshness"]["quay"].get("stale"):
                    warm += 1
            except (ValueError, KeyError, TypeError) as e:
                print(f"[weather] {code} could not be primed. {e}")
        print(f"[weather] cache ready for {fetched + warm} of {len(PORTS)} ports. "
              f"{fetched} fetched live, {warm} already fresh in the cache.")

    threading.Thread(target=work, name="weather-prime", daemon=True).start()
