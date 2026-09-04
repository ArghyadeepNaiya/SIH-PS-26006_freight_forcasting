"""Expanding-window time series cross validation and skill scoring.

Random train/test splits are PROHIBITED in this project (NFR-06). Every metric
reported here is out-of-sample and respects time order.

skill_score = 1 - (model_error / baseline_error)
  > 0  : better than assuming nothing changes
  <= 0 : NO SKILL. The interface must show a no-skill notice at this horizon.
"""
import numpy as np
import pandas as pd
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
from app.forecasting.features import build


def expanding_cv(df, target_col, horizon, exog_cols=None, n_folds=5, min_train=750, kind="ridge"):
    """Return dict with model MAE, baseline MAE, skill score and residual std."""
    # Model the CHANGE, not the level. On a near-random-walk series, regressing
    # on the level lets the model chase the trend and lose badly to persistence.
    # Persistence is equivalent to predicting a change of zero, so this also makes
    # the comparison exact rather than approximate.
    X = build(df, target_col, exog_cols)
    level = df[target_col]
    y = (level.shift(-horizon) - level) / level          # forward return
    mask = X.notna().all(axis=1) & y.notna() & (level > 0)
    Xv, yv = X[mask].reset_index(drop=True), y[mask].reset_index(drop=True)
    base_now = level[mask].reset_index(drop=True)

    n = len(Xv)
    if n < min_train + 60:
        return None

    fold = (n - min_train) // n_folds
    if fold < 20:
        return None

    m_err, b_err, resid = [], [], []
    for k in range(n_folds):
        tr_end = min_train + k * fold
        te_end = tr_end + fold if k < n_folds - 1 else n
        model = make_model(kind)
        model.fit(Xv.iloc[:tr_end], yv.iloc[:tr_end])
        # Convert predicted returns back to price levels so that MAE is in
        # index points and directly comparable with the persistence baseline.
        lvl = base_now.iloc[tr_end:te_end].values
        pred = model.predict(Xv.iloc[tr_end:te_end]) * lvl + lvl
        actual = yv.iloc[tr_end:te_end].values * lvl + lvl
        naive = lvl                                   # persistence: no change
        m_err.append(np.abs(pred - actual))
        b_err.append(np.abs(naive - actual))
        resid.append(pred - actual)

    m_mae = float(np.mean(np.concatenate(m_err)))
    b_mae = float(np.mean(np.concatenate(b_err)))
    skill = 1.0 - (m_mae / b_mae) if b_mae > 0 else 0.0
    return {
        "horizon_days": horizon,
        "model_mae": round(m_mae, 2),
        "baseline_mae": round(b_mae, 2),
        "skill_score": round(skill, 4),
        "has_skill": bool(skill > 0.02),
        "residual_std": float(np.std(np.concatenate(resid))),
        "n_test": int(sum(len(e) for e in m_err)),
        "n_folds": n_folds,
    }
