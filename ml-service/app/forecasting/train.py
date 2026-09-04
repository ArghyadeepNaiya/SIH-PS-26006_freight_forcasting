"""Train one model per vessel class per horizon, cache metrics and models."""
import pickle
import numpy as np
import numpy as _np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline


def make_model(kind="ridge"):
    """Ridge is the default. On near-random-walk series a heavily regularised
    linear model consistently beats a boosted tree, which has far too much
    capacity for the amount of signal present. GBM is kept as a comparator."""
    if kind == "gbm":
        return HistGradientBoostingRegressor(
            max_iter=120, learning_rate=0.03, max_depth=3,
            min_samples_leaf=100, l2_regularization=5.0, random_state=7)
    return make_pipeline(StandardScaler(),
                         RidgeCV(alphas=_np.logspace(0, 4, 20)))
from app.config import MODELS, INDEX_KEYS
from app.forecasting.features import build
from app.forecasting.evaluate import expanding_cv

HORIZONS = [7, 14, 30, 60, 90]
EXOG = ["BDI"]

_CACHE = {"models": {}, "metrics": {}, "meta": {}}


def train_all(df, source_label, is_real):
    MODELS.mkdir(parents=True, exist_ok=True)
    models, metrics = {}, {}
    for key in INDEX_KEYS:
        if key not in df.columns:
            continue
        for h in HORIZONS:
            m = expanding_cv(df, key, h, exog_cols=EXOG)
            if m is None:
                continue
            metrics[(key, h)] = m
            X = build(df, key, EXOG)
            level = df[key]
            y = (level.shift(-h) - level) / level      # train on forward return
            mask = X.notna().all(axis=1) & y.notna() & (level > 0)
            model = make_model("ridge")
            model.fit(X[mask], y[mask])
            models[(key, h)] = model
    _CACHE["models"] = models
    _CACHE["metrics"] = metrics
    _CACHE["meta"] = {
        "source": source_label,
        "is_real_data": is_real,
        "rows": int(len(df)),
        "date_from": str(df["date"].min().date()),
        "date_to": str(df["date"].max().date()),
        "horizons": HORIZONS,
    }
    with open(MODELS / "cache.pkl", "wb") as f:
        pickle.dump({"metrics": metrics, "meta": _CACHE["meta"]}, f)
    return _CACHE


def cache():
    return _CACHE
