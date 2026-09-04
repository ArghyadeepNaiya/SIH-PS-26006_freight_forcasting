"""Step 1 of the request pipeline: generate every vessel-class x port combination."""
from app.config import PORTS, VESSELS, DISTANCES, ORIGINS


def generate(origin_code: str, cargo_type: str):
    """Return list of raw candidates. No filtering yet - filtering is constraints.py."""
    origin = ORIGINS.get(origin_code)
    if origin is None:
        raise ValueError(f"Unknown origin: {origin_code}")
    if cargo_type not in origin["cargo"]:
        raise ValueError(
            f"{origin['name']} does not supply {cargo_type}. Available: {origin['cargo']}"
        )
    out = []
    for vname, v in VESSELS.items():
        for pcode, p in PORTS.items():
            dist = DISTANCES.get(origin_code, {}).get(pcode)
            if dist is None:
                continue
            out.append({
                "vessel_class": vname,
                "vessel": v,
                "discharge_port": p["name"],
                "port_code": pcode,
                "port": p,
                "origin_code": origin_code,
                "origin_name": origin["name"],
                "distance_nm": dist,
            })
    return out
