import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core import candidates, constraints, capacity, cost_model
from app.config import PORTS, VESSELS

def find(origin, vessel, port_code):
    for c in candidates.generate(origin, "coking_coal"):
        if c["vessel_class"] == vessel and c["port_code"] == port_code:
            c["plant"] = "Durgapur"
            return c
    raise AssertionError("candidate not found")

print("="*66)
print("TEST 1: Capesize at Haldia must be REJECTED (this is the whole project)")
c = find("AU", "Capesize", "INHAL")
ok, rej, _ = constraints.check(c)
assert not ok, "Capesize should be rejected at Haldia"
print(f"  REJECTED on {rej['failed_constraint']}: {rej['explanation']}")
print(f"  cite: {rej['source_citation'][:70]}")

print("\nTEST 2: Panamax at Haldia is feasible but draft-limited")
c = find("AU", "Panamax", "INHAL")
ok, rej, _ = constraints.check(c)
assert ok, f"Panamax should pass hard constraints at Haldia, got {rej}"
cap = capacity.deliverable(c, 75000)
print(f"  nominal {cap['nominal_capacity_tonnes']:,} t -> deliverable {cap['deliverable_tonnes']:,} t "
      f"({cap['load_percentage']}%)  binding={cap['binding_constraint']} @ {cap['binding_draft_m']} m")
print(f"  lightering required: {cap['requires_lightering']} ({cap['lightered_tonnes']:,} t)")

print("\nTEST 3: Capesize at Dhamra loads full")
c2 = find("AU", "Capesize", "INDAH")
ok2, rej2, _ = constraints.check(c2)
assert ok2, f"Capesize should pass at Dhamra, got {rej2}"
cap2 = capacity.deliverable(c2, 75000)
print(f"  nominal {cap2['nominal_capacity_tonnes']:,} t -> deliverable {cap2['deliverable_tonnes']:,} t "
      f"({cap2['load_percentage']}%)")

print("\nTEST 4: landed cost comparison (the money slide)")
p_cost = cost_model.compute(c, cap, 20200.0)
c_cost = cost_model.compute(c2, cap2, 45600.0)
print(f"  Panamax  @ Haldia : ${p_cost['landed_cost_usd_per_tonne']:>7.2f}/t  "
      f"(INR {p_cost['landed_cost_inr_per_tonne']:>8,.0f}/t) on {cap['deliverable_tonnes']:,} t")
print(f"  Capesize @ Dhamra : ${c_cost['landed_cost_usd_per_tonne']:>7.2f}/t  "
      f"(INR {c_cost['landed_cost_inr_per_tonne']:>8,.0f}/t) on {cap2['deliverable_tonnes']:,} t")
print(f"  breakdown Panamax : {p_cost['cost_breakdown_usd_per_tonne']}")
print(f"  breakdown Capesize: {c_cost['cost_breakdown_usd_per_tonne']}")
print("\nTEST 5: stowage factor decides whether a cargo weighs out or cubes out")
cape = find("AU", "Capesize", "INDAH")   # 18 m draft, no draft restriction at all
ore = capacity.deliverable(cape, 999999, cargo_type="iron_ore", allow_lightering=False)
coal = capacity.deliverable(cape, 999999, cargo_type="thermal_coal", allow_lightering=False)
assert not ore["cubes_out"], "iron ore must weigh out"
assert coal["cubes_out"], "thermal coal must cube out on a Capesize"
assert ore["deliverable_tonnes"] > coal["deliverable_tonnes"], \
    "dense cargo must load more tonnes than bulky cargo on the same ship"
print(f"  iron ore     SF 0.40 -> {ore['deliverable_tonnes']:,} t ({ore['load_percentage']}%) "
      f"binding={ore['binding_constraint']}")
print(f"  thermal coal SF 1.30 -> {coal['deliverable_tonnes']:,} t ({coal['load_percentage']}%) "
      f"binding={coal['binding_constraint']}")
print(f"  volume ceiling {coal['volume_capacity_tonnes']:,} t vs weight ceiling "
      f"{coal['weight_capacity_tonnes']:,} t")

print("\nTEST 6: cubing out makes the cargo more expensive per tonne")
ore_cost = cost_model.compute(cape, ore, 30000.0, cargo_type="iron_ore")
coal_cost = cost_model.compute(cape, coal, 30000.0, cargo_type="thermal_coal")
assert coal_cost["landed_cost_usd_per_tonne"] > ore_cost["landed_cost_usd_per_tonne"], \
    "a cargo that cubes out must cost more per delivered tonne"
print(f"  iron ore     ${ore_cost['landed_cost_usd_per_tonne']:>6.2f}/t on {ore['deliverable_tonnes']:,} t")
print(f"  thermal coal ${coal_cost['landed_cost_usd_per_tonne']:>6.2f}/t on {coal['deliverable_tonnes']:,} t")

print("\nTEST 7: lightering cannot relieve a volume restriction")
lit = capacity.deliverable(cape, 999999, cargo_type="thermal_coal", allow_lightering=True)
assert not lit["requires_lightering"], "lightering must not be proposed for a cubing cargo"
print(f"  lightering requested but not used. requires_lightering={lit['requires_lightering']}")

print("\nALL CORE TESTS PASSED")
