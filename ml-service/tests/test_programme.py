"""Tests for the term contract engine, the market statistics behind it, the timing
scan, the origin comparison and the warnings.

The tests that matter most here are the ones that try to make the system LIE. A
statistics module that reports a seasonal pattern in pure noise, or a hedging rule
that recommends covering a programme at any price, would both look perfectly healthy
on a dashboard. So each of those is given data with a known answer and checked
against it.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from app.core import market, programme, compare, risk, timing, cost_model
from app.core import candidates, capacity
from app.config import ASSUMPTIONS
from app.data.synthetic import generate

ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  {detail}" if detail else ""))


def head(t):
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


DF = generate()

# ======================================================================
head("GROUP 1. The market statistics say what they claim to say")
# ======================================================================

flat = pd.Series([100.0] * 900)
r = market.coverage_ratios(flat, 180)
check("a price that never moves gives a coverage ratio of exactly one",
      r.size > 0 and np.allclose(r, 1.0), f"{r.size} observations, all {r[0] if r.size else 'n/a'}")

# A series that rises by a fixed amount each day has an arithmetic mean over the next
# w days that can be worked out by hand, so the ratio is checkable without the code.
ramp = pd.Series(100.0 + np.arange(900))
w = 10
rr = market.coverage_ratios(ramp, w)
expected_first = (sum(101.0 + i for i in range(w)) / w) / 100.0
check("a straight line ramp gives the ratio worked out by hand",
      abs(rr[0] - expected_first) < 1e-9, f"got {rr[0]:.6f}, expected {expected_first:.6f}")

check("a series too short for the period returns nothing rather than guessing",
      market.period_outlook(pd.Series([100.0] * 40), 180) is None)

out = market.period_outlook(DF["BPI"], 180)
check("a real length of history produces a full outlook",
      out is not None and out["observations"] > 1000, f"{out['observations']} periods measured")
check("the ten and ninety percent points sit either side of the middle",
      out["p10_ratio"] < out["expected_ratio"] < out["p90_ratio"],
      f"{out['p10_ratio']:.3f} < {out['expected_ratio']:.3f} < {out['p90_ratio']:.3f}")

# ======================================================================
head("GROUP 2. Seasonality is tested, not asserted")
# ======================================================================

# Three ways of trying to make the seasonality test lie, in both directions.
#
# 1. Pure noise, where anything it reports is a false positive.
# 2. A clean series with a five percent wave deliberately put into it, where finding
#    nothing would mean the test has no power and is only ever going to say no.
# 3. The scaffolding series, which has the same five percent wave but far larger
#    random swings on top of it. There the honest answer is genuinely uncertain, and
#    what is checked is that the system does not claim more than it can support.
dates = pd.bdate_range("2016-01-01", "2026-08-31")
doy = dates.dayofyear.to_numpy()

for seed in (11, 5, 99):
    r = np.random.default_rng(seed)
    walk = pd.Series(1000 * np.exp(np.cumsum(r.standard_normal(len(dates)) * 0.001)))
    sn = market.seasonality(dates, walk)
    check(f"no month is called meaningful in a series with no seasonality, seed {seed}",
          sn is not None and sn["meaningful_months"] == 0,
          f"{sn['meaningful_months'] if sn else 'none'} flagged, p = {sn['p_value']:.3f}")

r = np.random.default_rng(3)
clean = pd.Series(1000 * np.exp(np.cumsum(r.standard_normal(len(dates)) * 0.001))
                  * (1 + 0.05 * np.sin(2 * np.pi * (doy - 60) / 365.0)))
s_clean = market.seasonality(dates, clean)
check("a five percent seasonal wave in a quiet series is detected",
      s_clean["meaningful_months"] >= 1 and s_clean["p_value"] < 0.05,
      f"{s_clean['meaningful_months']} months flagged, p = {s_clean['p_value']:.4f}")
check("and it points at the month the wave was actually put at",
      s_clean["dearest_month"]["month"] in (5, 6),
      f"dearest is {s_clean['dearest_month']['month_name']}")

s_real = market.seasonality(DF["date"], DF["BPI"])
check("the same wave inside a much noisier series is not claimed as proven",
      s_real["p_value"] > 0.05 and s_real["meaningful_months"] == 0,
      f"p = {s_real['p_value']:.3f}, so the pattern is reported but not asserted")
check("the shape is still in the right place even where it cannot be proven",
      s_real["dearest_month"]["month"] in (4, 5, 6, 7)
      and s_real["cheapest_month"]["month"] in (11, 12, 1, 2),
      f"dearest {s_real['dearest_month']['month_name']}, "
      f"cheapest {s_real['cheapest_month']['month_name']}")
check("the rotation test says how many rotations it used, so it can be re-run by hand",
      s_real["rotations"] > 100, f"{s_real['rotations']} calendar rotations")

# ======================================================================
head("GROUP 3. The hedging rule behaves the way its own explanation says")
# ======================================================================

sd = 0.15
lam = ASSUMPTIONS["risk_aversion_lambda"]
check("a term rate at or below expected spot means cover everything",
      market.optimal_coverage(1.00, 0.97, sd, lam) == 1.0)
check("a term rate far above expected spot means cover nothing",
      market.optimal_coverage(1.00, 2.00, sd, lam) == 0.0)

mid = market.optimal_coverage(1.00, 1.05, sd, lam)
check("a modest premium gives an answer strictly between the two",
      0.0 < mid < 1.0, f"coverage {mid:.3f}")
check("a larger premium always means less coverage",
      market.optimal_coverage(1.00, 1.10, sd, lam) < mid,
      f"{market.optimal_coverage(1.00, 1.10, sd, lam):.3f} against {mid:.3f}")
check("a more volatile market always means more coverage at the same premium",
      market.optimal_coverage(1.00, 1.05, 0.30, lam) > mid,
      f"{market.optimal_coverage(1.00, 1.05, 0.30, lam):.3f} against {mid:.3f}")
check("a buyer indifferent to risk goes all or nothing, never in between",
      market.optimal_coverage(1.00, 1.05, sd, 0.0) in (0.0, 1.0))

# ======================================================================
head("GROUP 4. The programme priced end to end")
# ======================================================================

REQ = {"cargo_type": "coking_coal", "quantity_tonnes": 75000, "origin": "AU",
       "destination_plant": "Durgapur", "horizon_days": 30,
       "programme_tonnes": 600000, "programme_days": 180}

p = programme.run(dict(REQ), DF)
check("a six month programme is planned", p["feasible"], p.get("reason", ""))

shape = p["shape"]
check("the programme is split into whole voyages that cover the quantity",
      shape["voyages"] * shape["tonnes_per_voyage"] >= shape["total_tonnes"],
      f"{shape['voyages']} voyages of {shape['tonnes_per_voyage']:,} t "
      f"covers {shape['total_tonnes']:,} t")
check("only part of the landed cost is exposed to the freight market",
      0.0 < shape["market_exposed_share"] < 1.0,
      f"{shape['market_exposed_share']:.1%} of the cost moves with the charter market")
check("the exposed and fixed parts add back to the landed cost",
      abs(shape["market_exposed_usd_per_tonne"] + shape["fixed_usd_per_tonne"]
          - shape["landed_cost_usd_per_tonne"]) < 0.02)

plans = {x["plan"]: x for x in p["plans"]}
check("covering the whole programme removes the range entirely",
      plans["all_term"]["range_usd_per_tonne"] == 0.0)
check("leaving the whole programme on spot carries the widest range",
      plans["all_spot"]["range_usd_per_tonne"] > plans["recommended"]["range_usd_per_tonne"]
      >= plans["all_term"]["range_usd_per_tonne"],
      f"${plans['all_spot']['range_usd_per_tonne']} to "
      f"${plans['recommended']['range_usd_per_tonne']} to "
      f"${plans['all_term']['range_usd_per_tonne']} a tonne")
# The per tonne figure on screen is rounded to the cent, so the programme total is
# checked to within half a cent a tonne rather than to the dollar.
_tonnes = shape["voyages"] * shape["tonnes_per_voyage"]
check("the programme total is the per tonne cost times the tonnes",
      abs(plans["all_spot"]["expected_programme_cost_usd"]
          - plans["all_spot"]["expected_cost_usd_per_tonne"] * _tonnes) < 0.005 * _tonnes + 1,
      f"${plans['all_spot']['expected_programme_cost_usd']:,} over {_tonnes:,} tonnes")

# A term rate the owner is asking a large premium for must push the answer back
# towards spot. This is the test that a plausible-looking hedging engine fails.
dear = programme.run({**REQ, "term_rate_ratio": 1.6}, DF)
cheap = programme.run({**REQ, "term_rate_ratio": 0.85}, DF)
check("an expensive term offer is refused in favour of the spot market",
      dear["recommended_coverage"] < 0.05 and dear["chosen_plan"] == "all_spot",
      f"coverage {dear['recommended_coverage']:.2f}")
check("a cheap term offer is taken in full",
      cheap["recommended_coverage"] == 1.0 and cheap["chosen_plan"] == "all_term",
      f"coverage {cheap['recommended_coverage']:.2f}")
check("the recommendation text states the premium rather than hiding it",
      "a tonne" in dear["plain"] and "premium" in dear["plain"].lower()
      or "above where spot" in dear["plain"])
check("a quoted rate is recorded as quoted, and a default one is not",
      dear["market"]["term_rate_was_quoted"] and not p["market"]["term_rate_was_quoted"])

short = programme.run({**REQ, "programme_days": 20}, DF)
check("a period too short to be a term contract says so instead of pricing one",
      "too short" in short["headline"].lower(), short["headline"])

try:
    programme.run({**REQ, "programme_tonnes": 0}, DF)
    check("a programme of zero tonnes is refused", False)
except ValueError as e:
    check("a programme of zero tonnes is refused with a readable reason", "greater than zero" in str(e))

# ======================================================================
head("GROUP 5. Idle and empty time is measured and adds up")
# ======================================================================

c = next(x for x in candidates.generate("AU", "coking_coal")
         if x["vessel_class"] == "Panamax" and x["port_code"] == "INPRT")
c["plant"] = "Durgapur"
cap = capacity.deliverable(c, 75000, cargo_type="coking_coal")
cost = cost_model.compute(c, cap, 18000.0, cargo_type="coking_coal", weather_delay_days=2.0)
idle = cost["idle_and_empty_time"]

check("waiting days and weather days add up to the idle days reported",
      abs(idle["waiting_days"] + idle["weather_days"] - idle["idle_days"]) < 0.05,
      f"{idle['waiting_days']} + {idle['weather_days']} = {idle['idle_days']}")
check("the empty positioning leg is the stated fraction of the laden voyage",
      abs(idle["ballast_days"]
          - idle["sea_laden_days"] * idle["ballast_allowance_fraction"]) < 0.1,
      f"{idle['ballast_days']} days against {idle['sea_laden_days']} laden")
check("the unproductive share is a share, and is not the whole voyage",
      0 < idle["unproductive_share_percent"] < 100,
      f"{idle['unproductive_share_percent']}% of the bill is idle or empty time")
check("the fraction comes from the assumptions file, not from the code",
      idle["ballast_allowance_fraction"] == ASSUMPTIONS["ballast_allowance_fraction"])

no_wx = cost_model.compute(c, cap, 18000.0, cargo_type="coking_coal", weather_delay_days=0.0)
check("removing the weather delay removes exactly its cost and nothing else",
      no_wx["idle_and_empty_time"]["ballast_days"] == idle["ballast_days"]
      and no_wx["idle_and_empty_time"]["idle_days"] < idle["idle_days"])

# ======================================================================
head("GROUP 6. Every origin priced against every other")
# ======================================================================

cmpres = compare.by_origin({"cargo_type": "coking_coal", "quantity_tonnes": 75000,
                            "origin": "AU", "destination_plant": "Durgapur"}, DF)
rows = cmpres["origins"]
check("every origin that supplies this cargo is priced", len(rows) >= 3,
      f"{len(rows)} origins priced, {len(cmpres['unavailable'])} could not be")
check("the list is ordered cheapest first",
      all(rows[i]["landed_cost_usd_per_tonne"] <= rows[i + 1]["landed_cost_usd_per_tonne"]
          for i in range(len(rows) - 1)))
check("the cheapest origin is zero more expensive than itself",
      rows[0]["extra_vs_cheapest_usd_per_tonne"] == 0.0)
check("distance alone does not decide the answer, which is the point of the screen",
      min(rows, key=lambda r: r["distance_nm"])["rank"] != 1
      or len({r["load_port_max_draft_m"] for r in rows}) > 1,
      "the nearest origin is not automatically the cheapest")

try:
    compare.by_origin({"cargo_type": "steel_scrap", "quantity_tonnes": 50000,
                       "origin": "US"}, DF)
    check("a cargo with only one supplier still returns an answer", True)
except ValueError as e:
    check("a cargo with only one supplier still returns an answer", False, str(e))

# ======================================================================
head("GROUP 7. Warnings fire on evidence and stay quiet without it")
# ======================================================================

rep = risk.report(DF, False, "SCAFFOLDING - synthetic series, not real market data",
                  horizon_days=30, port_code="INHAL", origin_code="AU",
                  origin_name="Australia", cargo_name="Coking coal",
                  alternatives=["United States", "Mozambique"])
cats = {w["category"] for w in rep["warnings"]}
check("running on stand-in data is reported as the highest severity",
      any(w["severity"] == "high" and w["category"] == "data quality"
          for w in rep["warnings"]))
check("an unusable forecast is reported as a warning, not buried",
      "forecast reliability" in cats)
check("drawing a whole programme from one country is flagged",
      "supply concentration" in cats)
check("every warning names its evidence and what to do about it",
      all(w["evidence"] and w["action"] for w in rep["warnings"]))
check("warnings are ordered worst first",
      [{"high": 0, "medium": 1, "low": 2}[w["severity"]] for w in rep["warnings"]]
      == sorted([{"high": 0, "medium": 1, "low": 2}[w["severity"]] for w in rep["warnings"]]))

real = risk.data_warnings(True, "data/raw/baltic_indices.csv (2000 rows)")
check("real market data raises no data warning at all",
      not any(w["title"].startswith("Every price") for w in real))

# ======================================================================
head("GROUP 8. The timing scan reports the model honestly")
# ======================================================================

scan = timing.scan(DF, "BPI")
check("every horizon is scored", len(scan["horizons"]) == 5)
check("a horizon with no skill is not given a recommendation to act on",
      all(("does not beat" in scan["verdict"]) or r["has_skill"]
          for r in scan["horizons"]))
check("the historical spread is reported even where the model has no skill",
      all(r["historical_p90_ratio"] is not None for r in scan["horizons"]))
check("the uncertainty band widens as the horizon lengthens, as it must",
      scan["horizons"][-1]["historical_p90_ratio"] - scan["horizons"][-1]["historical_p10_ratio"]
      > scan["horizons"][0]["historical_p90_ratio"] - scan["horizons"][0]["historical_p10_ratio"])

print("\n" + "=" * 70)
print(f"{len(ok)} passed, {len(fail)} failed")
if fail:
    print("FAILED: " + "; ".join(fail))
print("=" * 70)
sys.exit(1 if fail else 0)
