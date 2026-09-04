"""Placeholder rate history generator.

THIS IS SCAFFOLDING, NOT DATA. It exists so the pipeline can be built and tested
before the real CSV arrives. It produces series with realistic statistical
properties (near-random-walk, fat tails, volatility clustering, mild seasonality)
so that model evaluation is honest rather than flattering.

Replace with data/raw/baltic_indices.csv as soon as you have it. The loader will
prefer the real file automatically.
"""
import numpy as np
import pandas as pd

BASE_LEVELS = {"BCI": 2900, "BPI": 1750, "BSI": 1250, "BHSI": 700}
VOLS = {"BCI": 0.041, "BPI": 0.026, "BSI": 0.021, "BHSI": 0.016}


def generate(start="2016-01-01", end="2026-08-31", seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    n = len(dates)
    out = {"date": dates}
    common = rng.standard_normal(n) * 0.5  # shared market factor across classes

    for key, base in BASE_LEVELS.items():
        vol = VOLS[key]
        # GARCH-ish volatility clustering
        sig = np.zeros(n); sig[0] = vol
        for t in range(1, n):
            sig[t] = np.sqrt(0.00002 + 0.09 * (vol * common[t-1])**2 + 0.88 * sig[t-1]**2)
        # Real dry bulk freight rates exhibit short-horizon momentum, because
        # vessels take weeks to reposition and charterers chase a moving market.
        # We build in a mild AR(1) in returns so the scaffolding has the same
        # qualitative property as the real series. This is documented scaffolding,
        # not a claim about any real market.
        raw = (0.6 * common + 0.8 * rng.standard_normal(n)) * sig
        shocks = np.zeros(n)
        for t in range(1, n):
            shocks[t] = 0.22 * shocks[t - 1] + raw[t]
        # slow mean reversion to a drifting level
        logp = np.zeros(n); logp[0] = np.log(base)
        anchor = np.log(base)
        for t in range(1, n):
            logp[t] = logp[t-1] + 0.004 * (anchor - logp[t-1]) + shocks[t]
        series = np.exp(logp)
        # mild annual seasonality
        doy = dates.dayofyear.values
        series *= 1 + 0.05 * np.sin(2 * np.pi * (doy - 60) / 365.0)
        out[key] = np.round(series, 0)

    df = pd.DataFrame(out)
    df["BDI"] = np.round(0.4 * df["BCI"] + 0.3 * df["BPI"] + 0.3 * df["BSI"], 0)
    return df
