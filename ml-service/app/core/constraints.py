"""Step 2: hard physical feasibility. Deterministic, testable, provably correct.

Rejections are RETURNED, not discarded. Showing the user what was ruled out and why
is the most persuasive thing the product does.
"""
from app.config import PORTS


def check(candidate):
    """Return (feasible: bool, rejection: dict|None, notes: dict).

    Draft is checked separately in capacity.py because a draft shortfall does not
    always disqualify a vessel - it may simply mean partial loading.
    """
    v, p = candidate["vessel"], candidate["port"]
    cite = p.get("citations", {})

    # LOA - hard. A ship longer than the berth cannot berth. No workaround.
    if v["typical_loa_m"] > p["max_loa_m"]:
        return False, {
            "failed_constraint": "loa",
            "limit_value": p["max_loa_m"],
            "required_value": v["typical_loa_m"],
            "unit": "m",
            "explanation": (
                f"{candidate['vessel_class']} is typically {v['typical_loa_m']:.0f} m long. "
                f"{p['name']} accepts a maximum of {p['max_loa_m']:.0f} m."
            ),
            "source_citation": cite.get("max_loa_m", "no citation recorded"),
        }, {}

    # Beam - hard. Lock gates and channel width do not flex.
    if v["typical_beam_m"] > p["max_beam_m"]:
        return False, {
            "failed_constraint": "beam",
            "limit_value": p["max_beam_m"],
            "required_value": v["typical_beam_m"],
            "unit": "m",
            "explanation": (
                f"{candidate['vessel_class']} beam is typically {v['typical_beam_m']:.1f} m. "
                f"{p['name']} accepts a maximum of {p['max_beam_m']:.2f} m."
            ),
            "source_citation": cite.get("max_beam_m", "no citation recorded"),
        }, {}

    # DWT - hard.
    if v["nominal_dwt"] > p["max_dwt"]:
        return False, {
            "failed_constraint": "dwt",
            "limit_value": p["max_dwt"],
            "required_value": v["nominal_dwt"],
            "unit": "DWT",
            "explanation": (
                f"{candidate['vessel_class']} is typically {v['nominal_dwt']:,} DWT. "
                f"{p['name']} accepts a maximum of {p['max_dwt']:,} DWT."
            ),
            "source_citation": cite.get("max_dwt", "no citation recorded"),
        }, {}

    # Load-port draft - hard. A ship that cannot load fully at origin is a
    # different problem from one that cannot discharge fully at destination.
    return True, None, {}
