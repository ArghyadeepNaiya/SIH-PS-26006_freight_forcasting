"""Tests for the port operator dashboard, its declarations, and the weather advisory.

Run from the ml-service directory:

    venv/bin/python tests/test_portal.py

These tests are hermetic. They point the credential file, the declaration store and
the weather cache at a temporary directory, so running them cannot read, overwrite or
leak the real passwords, the real declarations or the real forecast cache.

WHAT IS DELIBERATELY NOT TESTED HERE. Whether a click in a browser reaches a handler.
That question cannot be answered from Python, and answering it from Python is exactly
how a broken dashboard passed its tests on this project once before. It is answered
by scripts/browser_e2e.py, which drives a real Firefox.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import PORTS                                  # noqa: E402
from app.core import portal_auth as auth                      # noqa: E402
from app.core import declarations as decl                     # noqa: E402
from app.core import weather                                  # noqa: E402

PASSED, FAILED = [], []
TMP = tempfile.mkdtemp(prefix="portal-tests-")


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  {detail}" if detail else ""))


def redirect_to_tmp():
    """Point every file this module writes at a temporary directory."""
    auth.CRED_FILE = os.path.join(TMP, "credentials.json")
    auth.PLAINTEXT_FILE = os.path.join(TMP, "passwords.txt")
    # PBKDF2 at 240,000 rounds is deliberately slow. That is right in production and
    # wrong in a test suite, so the cost is lowered here and nowhere else.
    auth.PBKDF2_ROUNDS = 1000
    from pathlib import Path
    auth.CRED_FILE = Path(auth.CRED_FILE)
    auth.PLAINTEXT_FILE = Path(auth.PLAINTEXT_FILE)
    decl.STORE = Path(TMP) / "declarations"


redirect_to_tmp()
CODE = "INPRT"
OTHER = "INHAL"

print("=" * 70)
print("TEST GROUP 1. Passwords and sessions")
print("=" * 70)

passwords = {c: auth.make_passphrase() for c in PORTS}
auth.write_credentials(passwords, {c: f"{PORTS[c]['name']} operator" for c in PORTS})

check("a password is generated for every port", len(passwords) == len(PORTS),
      f"{len(passwords)} ports")
check("passwords are words and digits, so they can be read aloud and typed back",
      all(p.count("-") == 3 and p.split("-")[-1].isdigit() for p in passwords.values()),
      passwords[CODE])

creds = json.load(open(auth.CRED_FILE))["ports"]
check("no plaintext password is stored in the credential file",
      not any(passwords[c] in json.dumps(creds[c]) for c in creds))
check("every port gets its own random salt",
      len({creds[c]["salt"] for c in creds}) == len(creds))

check("the credential file is readable only by its owner",
      oct(os.stat(auth.CRED_FILE).st_mode)[-3:] == "600",
      oct(os.stat(auth.CRED_FILE).st_mode)[-3:])
check("the plaintext password file is readable only by its owner",
      oct(os.stat(auth.PLAINTEXT_FILE).st_mode)[-3:] == "600")

session = auth.login(CODE, passwords[CODE])
check("the right password signs the operator in", session["port_code"] == CODE)
check("the session resolves back to that port and no other",
      auth.resolve(session["token"]) == CODE)

try:
    auth.login(CODE, passwords[CODE] + "x")
    check("a wrong password is refused", False)
except auth.AuthError as e:
    check("a wrong password is refused", True, str(e)[:60])

try:
    auth.login("NOSUCH", "anything")
    check("an unknown port cannot be distinguished from a wrong password", False)
except auth.AuthError as e:
    check("an unknown port cannot be distinguished from a wrong password",
          "not recognised" in str(e), str(e)[:60])

try:
    auth.resolve("a-token-nobody-issued")
    check("a forged session token is refused", False)
except auth.AuthError:
    check("a forged session token is refused", True)

auth.logout(session["token"])
try:
    auth.resolve(session["token"])
    check("signing out really invalidates the token", False)
except auth.AuthError:
    check("signing out really invalidates the token", True)

# Lockout. The counter is reset first so this test does not depend on the ones above.
auth._FAILURES.clear()
locked = False
for _ in range(auth.MAX_FAILED_ATTEMPTS + 1):
    try:
        auth.login(CODE, "wrong")
    except auth.AuthError as e:
        locked = "Too many failed attempts" in str(e)
check("repeated wrong passwords lock the port out for a while", locked)
auth._FAILURES.clear()

print()
print("=" * 70)
print("TEST GROUP 2. Declarations, and the provenance rule")
print("=" * 70)

TODAY = date.today()
SAMPLE = {
    "declared_by": "Test operator",
    "operator_notes": "",
    "areas": [
        {"name": "Deep berth", "area_sq_m": 120000, "storage_capacity_tonnes": 300000,
         "available_from": TODAY.isoformat(),
         "available_to": (TODAY + timedelta(days=60)).isoformat(),
         "accepts_vessel_classes": ["Panamax", "Capesize"],
         "max_draft_m": 13.0, "discharge_rate_tonnes_per_day": 40000,
         "current_wait_days": 0.5, "notes": ""},
        {"name": "Winter yard", "area_sq_m": 40000, "storage_capacity_tonnes": 80000,
         "available_from": (TODAY + timedelta(days=120)).isoformat(),
         "available_to": None, "accepts_vessel_classes": ["Handysize"],
         "max_draft_m": None, "discharge_rate_tonnes_per_day": None,
         "current_wait_days": None, "notes": ""},
    ],
    "cargo_demand": [
        {"cargo_type": "coking_coal", "demand_rank": 1, "monthly_demand_tonnes": 400000,
         "indicative_price_inr_per_tonne": 14000, "notes": ""},
        {"cargo_type": "limestone", "demand_rank": 2, "monthly_demand_tonnes": 50000,
         "indicative_price_inr_per_tonne": 2500, "notes": ""},
    ],
    "operational": {"discharge_rate_tonnes_per_day": 40000, "typical_wait_days": 0.5,
                    "port_charge_usd_per_tonne": 2.75,
                    "lightering_cost_usd_per_tonne": 4.0},
}
saved = decl.save(CODE, SAMPLE, declared_by="Test operator")
check("a declaration is written and dated", bool(saved.get("updated_at")))
check("a declaration is stamped operator declared",
      saved["provenance"] == "OPERATOR DECLARED")

totals = decl.total_declared_area(decl.get(CODE))
check("declared area totals add up",
      totals["total_area_sq_m"] == 160000 and totals["total_storage_tonnes"] == 380000,
      str(totals))

check("a port that has not declared returns nothing rather than a guess",
      decl.get(OTHER) is None)

# --- provenance ---
eff = decl.effective_port(CODE)
check("a declared operating figure replaces the assumed one",
      eff["discharge_rate_tonnes_per_day"] == 40000)
check("and is labelled operator declared, with the declarer named",
      eff["provenance"]["discharge_rate_tonnes_per_day"]["source"] == "OPERATOR DECLARED"
      and "Test operator" in eff["provenance"]["discharge_rate_tonnes_per_day"]["citation"])

eff_undeclared = decl.effective_port(OTHER)
sources = {v["source"] for v in eff_undeclared["provenance"].values()}
check("an undeclared port keeps its published and assumed labels",
      "OPERATOR DECLARED" not in sources, str(sorted(sources)))

# --- the draft rule. Shallower is accepted, deeper is refused. ---
area_shallow = SAMPLE["areas"][0]
eff_shallow = decl.effective_port(CODE, area_shallow)
check("a berth declared shallower than the published limit is applied",
      eff_shallow["max_draft_m"] == 13.0
      and eff_shallow["provenance"]["max_draft_m"]["source"] == "OPERATOR DECLARED")

published = PORTS[CODE]["max_draft_m"]
eff_deep = decl.effective_port(CODE, dict(area_shallow, max_draft_m=published + 4))
check("a berth declared deeper than the published limit is NOT applied",
      eff_deep["max_draft_m"] == published,
      f"published {published} m stands")

print()
print("=" * 70)
print("TEST GROUP 3. What the operator is offering a given ship")
print("=" * 70)

ws, we = TODAY, TODAY + timedelta(days=30)

offer = decl.berth_offer(CODE, "Capesize", ws, we)
check("a class the operator accepts, in a window they are free, is offered",
      offer["status"] == "offered" and offer["area"]["name"] == "Deep berth",
      offer["status"])

offer = decl.berth_offer(CODE, "Supramax", ws, we)
check("a class no declared area accepts is refused, and the reason names the classes",
      offer["status"] == "refused" and offer["reason"] == "vessel_class_not_accepted",
      offer.get("explanation", "")[:90])

offer = decl.berth_offer(CODE, "Handysize", ws, we)
check("a class only an unavailable area accepts is refused on the window, not the class",
      offer["status"] == "refused" and offer["reason"] == "no_area_available_in_window",
      offer.get("explanation", "")[:90])

offer = decl.berth_offer(CODE, "Handysize", TODAY + timedelta(days=130),
                         TODAY + timedelta(days=160))
check("the same ship is offered a berth once the area frees up",
      offer["status"] == "offered", offer["status"])

offer = decl.berth_offer(OTHER, "Panamax", ws, we)
check("a port with no declaration falls back to published values, and says so",
      offer["status"] == "no_declaration")

# An area with no dates is open, not blocked. Silence is not a refusal.
decl.save("INDAH", {"declared_by": "T", "areas": [
    {"name": "Open yard", "area_sq_m": 1000, "accepts_vessel_classes": ["Capesize"]}],
    "cargo_demand": [], "operational": {}, "operator_notes": ""}, declared_by="T")
offer = decl.berth_offer("INDAH", "Capesize", ws, we)
check("an area with no dates declared is treated as open, not as blocked",
      offer["status"] == "offered")

# --- demand intelligence ---
d = decl.demand_for(CODE, "coking_coal")
check("the operator's demand ranking is reported for the cargo asked about",
      d["this_cargo"]["demand_rank"] == 1 and d["top_cargo_name"] == "Coking coal")
check("a cargo the operator did not rank returns no rank rather than a made up one",
      decl.demand_for(CODE, "steel_scrap")["this_cargo"] is None)

summary = {p["port_code"]: p for p in decl.public_summary()}
check("the public summary covers every port, declared or not",
      len(summary) == len(PORTS))
check("the public summary never carries a password, a hash or a salt",
      not any(k in json.dumps(summary) for k in ("salt", "hash", "password")))

print()
print("=" * 70)
print("TEST GROUP 4. Turning a forecast into delay days")
print("=" * 70)

cfg = weather._cfg()
t = {k: v["value"] for k, v in cfg["thresholds"].items()}

calm = [{"date": "2026-09-0%d" % i, "wind_speed_ms_max": 5.0, "wind_gust_ms_max": 8.0,
         "precipitation_mm": 1.0, "wave_height_m_max": 0.6, "swell_height_m_max": 0.4,
         "temperature_c_max": 31, "weather_code": 1} for i in range(1, 6)]
a = weather.assess(calm, cfg, is_anchorage=False)
check("a calm week costs no delay days", a["delay_days"] == 0.0 and a["risk_band"] == "clear")

blow = [dict(calm[0], wind_speed_ms_max=t["wind_speed_ms_grab_crane_suspend"] + 2)
        for _ in range(5)]
a = weather.assess(blow, cfg, is_anchorage=False)
check("a week over the crane wind limit costs a delay day for every day",
      a["delay_days"] == 5.0 and a["risk_band"] == "disrupted", str(a["delay_days"]))
check("and the breach is explained in words, with the limit quoted",
      "grab crane suspension limit" in a["days"][0]["breaches"][0],
      a["days"][0]["breaches"][0][:70])

# A wave height BETWEEN the two limits must separate them. The quay caution limit is
# the lower of the pair, so a sea state that troubles an approaching deep drafted ship
# can still be inside what a ship to ship transfer at anchorage will tolerate.
between = (t["wave_height_m_berthing_caution"] + t["wave_height_m_lightering_suspend"]) / 2
swell = [dict(calm[0], wave_height_m_max=between) for _ in range(4)]
at_anchor = weather.assess(swell, cfg, is_anchorage=True)
at_quay = weather.assess(swell, cfg, is_anchorage=False)
check("the quay and the anchorage are judged against their own different wave limits",
      at_quay["delay_days"] == 4.0 and at_anchor["delay_days"] == 0.0,
      f"at {between} m, quay loses {at_quay['delay_days']} days, "
      f"anchorage loses {at_anchor['delay_days']}")

over = [dict(calm[0], wave_height_m_max=t["wave_height_m_lightering_suspend"] + 0.3)
        for _ in range(4)]
check("sea state above the lightering limit stops work at the anchorage too",
      weather.assess(over, cfg, is_anchorage=True)["delay_days"] == 4.0)

check("a position with no forecast is reported as unknown, not as fine",
      weather.assess([], cfg, is_anchorage=False)["risk_band"] == "unknown")

# The advisory must never open a socket and must never invent a delay.
saved_cache = weather.CACHE
from pathlib import Path
weather.CACHE = Path(TMP) / "no-such-cache"
adv = weather.advisory(CODE)
check("a port with nothing cached contributes zero delay and says it does not know",
      adv["available"] is False and adv["expected_weather_delay_days"] == 0.0
      and "not a claim that the weather is good" in adv["headline"])
check("and the cost model therefore adds nothing for it",
      weather.delay_days(CODE) == 0.0)
weather.CACHE = saved_cache

print()
print("=" * 70)
print("TEST GROUP 5. The declaration reaches the recommendation")
print("=" * 70)

from app.core import candidates, constraints, capacity, cost_model     # noqa: E402


def candidate(vessel, port_code):
    for c in candidates.generate("AU", "coking_coal"):
        if c["vessel_class"] == vessel and c["port_code"] == port_code:
            c["plant"] = "Durgapur"
            return c
    raise AssertionError("candidate not found")


c = candidate("Panamax", CODE)
c["port"] = decl.effective_port(CODE, SAMPLE["areas"][0])
ok, _, _ = constraints.check(c)
cap = capacity.deliverable(c, 75000, cargo_type="coking_coal")
dry = cost_model.compute(c, cap, 20000.0, cargo_type="coking_coal",
                         weather_delay_days=0.0)
wet = cost_model.compute(c, cap, 20000.0, cargo_type="coking_coal",
                         weather_delay_days=3.0)
check("weather delay days raise the landed cost per tonne",
      wet["landed_cost_usd_per_tonne"] > dry["landed_cost_usd_per_tonne"],
      f"${dry['landed_cost_usd_per_tonne']}/t dry, ${wet['landed_cost_usd_per_tonne']}/t "
      f"with three lost days")
check("weather delay is broken out as its own cost line, not hidden in demurrage",
      wet["cost_breakdown_usd_per_tonne"]["weather_delay"] > 0
      and wet["cost_breakdown_usd_per_tonne"]["expected_demurrage"]
          == dry["cost_breakdown_usd_per_tonne"]["expected_demurrage"])
check("weather delay is broken out as its own time line",
      wet["time_breakdown_days"]["weather_delay"] == 3.0)

published_port = dict(PORTS[CODE])
c_pub = candidate("Panamax", CODE)
cap_pub = capacity.deliverable(c_pub, 75000, cargo_type="coking_coal")
cost_pub = cost_model.compute(c_pub, cap_pub, 20000.0, cargo_type="coking_coal")
check("the operator's faster discharge and shorter wait change what the business is quoted",
      dry["landed_cost_usd_per_tonne"] != cost_pub["landed_cost_usd_per_tonne"],
      f"${cost_pub['landed_cost_usd_per_tonne']}/t on our assumptions, "
      f"${dry['landed_cost_usd_per_tonne']}/t on the operator's declaration")

shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 70)
print(f"{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED. " + "; ".join(FAILED))
print("=" * 70)
sys.exit(1 if FAILED else 0)
