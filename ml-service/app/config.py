"""Central configuration and reference data loading."""
import json, os
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
REF = BASE / "data" / "reference"
RAW = BASE / "data" / "raw"
MODELS = BASE / "ml-service" / "models"


def _load(name):
    with open(REF / name) as f:
        return json.load(f)


PORTS = {p["code"]: p for p in _load("ports.json")["ports"]}
VESSELS = {v["name"]: v for v in _load("vessel_classes.json")["vessel_classes"]}
CARGOES = {c["code"]: c for c in _load("cargo_types.json")["cargo_types"]}
_routes = _load("routes.json")
ORIGINS = {o["code"]: o for o in _routes["origins"]}
DISTANCES = _routes["distances_nm"]
_ca = _load("cost_assumptions.json")
ASSUMPTIONS = {k: v["value"] for k, v in _ca["assumptions"].items()}
ASSUMPTION_META = _ca["assumptions"]
PLANTS = {p["name"]: p for p in _ca["plants"]}

INDEX_KEYS = ["BCI", "BPI", "BSI", "BHSI"]
CLASS_BY_INDEX = {v["index_key"]: k for k, v in VESSELS.items()}
