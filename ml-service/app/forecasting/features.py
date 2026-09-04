"""Feature engineering for the learned model. Lags, rolling stats, calendar."""
import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 5, 10, 21, 42, 63]
WINDOWS = [5, 21, 63]


def build(df, target_col, exog_cols=None):
    X = pd.DataFrame(index=df.index)
    s = df[target_col]

    for l in LAGS:
        X[f"lag_{l}"] = s.shift(l)
    for w in WINDOWS:
        X[f"mean_{w}"] = s.shift(1).rolling(w).mean()
        X[f"std_{w}"] = s.shift(1).rolling(w).std()
        X[f"ret_{w}"] = s.shift(1) / s.shift(1 + w) - 1.0
    X["mom_5_21"] = X["mean_5"] / X["mean_21"] - 1.0
    X["mom_21_63"] = X["mean_21"] / X["mean_63"] - 1.0
    X["level_vs_63"] = s.shift(1) / X["mean_63"] - 1.0

    d = pd.to_datetime(df["date"])
    X["month"] = d.dt.month
    X["dow"] = d.dt.dayofweek
    X["doy_sin"] = np.sin(2 * np.pi * d.dt.dayofyear / 365.0)
    X["doy_cos"] = np.cos(2 * np.pi * d.dt.dayofyear / 365.0)

    for c in (exog_cols or []):
        if c in df.columns:
            X[f"x_{c}_lag1"] = df[c].shift(1)
            X[f"x_{c}_ret21"] = df[c].shift(1) / df[c].shift(22) - 1.0
    return X
