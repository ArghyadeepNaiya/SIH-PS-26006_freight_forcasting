"""Naive persistence. Tomorrow equals today.

This is the number every other model must beat. It is built first, deliberately,
so that no later model can quietly claim credit for doing nothing.
"""
import numpy as np


def predict(series, horizon):
    """Forecast `horizon` steps ahead as the last observed value."""
    return np.full(horizon, series[-1], dtype=float)


def rolling_errors(values, horizon):
    """Absolute errors of persistence at a given horizon, across the whole series."""
    v = np.asarray(values, dtype=float)
    if len(v) <= horizon:
        return np.array([])
    return np.abs(v[horizon:] - v[:-horizon])
