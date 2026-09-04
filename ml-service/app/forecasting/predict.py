"""Point forecast plus prediction interval, from cached models."""
import numpy as np
from app.forecasting.features import build
from app.forecasting.train import _CACHE, EXOG, HORIZONS


def nearest_horizon(days):
    return min(HORIZONS, key=lambda h: abs(h - days))


def forecast(df, index_key, horizon_days):
    h = nearest_horizon(horizon_days)
    model = _CACHE["models"].get((index_key, h))
    met = _CACHE["metrics"].get((index_key, h))
    current = float(df[index_key].iloc[-1])

    if model is None or met is None:
        return {
            "index_key": index_key, "horizon_days": h, "current": current,
            "point": current, "lower": current, "upper": current,
            "skill_score": None, "has_skill": False,
            "note": "No trained model available. Falling back to persistence.",
        }

    X = build(df, index_key, EXOG)
    row = X.iloc[[-1]]
    if row.isna().any(axis=1).iloc[0]:
        point = current
    else:
        # Model outputs a forward return. Convert back to an index level.
        point = current * (1.0 + float(model.predict(row)[0]))

    sd = met["residual_std"]
    return {
        "index_key": index_key,
        "horizon_days": h,
        "current": round(current, 1),
        "point": round(point, 1),
        "lower": round(point - 1.28 * sd, 1),   # ~80 pct interval
        "upper": round(point + 1.28 * sd, 1),
        "skill_score": met["skill_score"],
        "has_skill": met["has_skill"],
        "model_mae": met["model_mae"],
        "baseline_mae": met["baseline_mae"],
        "note": None if met["has_skill"] else
                "This forecast failed its reliability test at this length of time. It is no "
                "better than simply assuming today's price holds, so it should not be leaned "
                "on.",
    }


def skill_table():
    rows = []
    for (k, h), m in sorted(_CACHE["metrics"].items()):
        rows.append({"index_key": k, **m})
    return rows
