"""What the market has actually done, measured rather than predicted.

WHY THIS MODULE IS SEPARATE FROM app/forecasting.

The forecasting package answers "where will this index be in N days", and on this
data it usually answers "we do not know", because a freight index is close to a
random walk and our model does not beat persistence. That verdict is honest and it
is not going to change by wishing.

But a buyer who has to move six hundred thousand tonnes over the next six months
still has to decide something, and the decision they actually face is not "what
will the rate be on the fourteenth of March". It is "should I fix these eight
voyages on a term contract at a known rate, or take whatever the spot market gives
me on each of the eight days I need a ship". That question can be answered without
any forecasting skill at all, because it is a question about the DISTRIBUTION of
outcomes rather than about their central point.

So everything here is descriptive statistics of the historical series. No model is
fitted, nothing is predicted, and no skill is claimed. The three things measured are

1. How much the average spot level over a coming period has historically differed
   from the level on the day the period started. That distribution is what a term
   contract is competing against.
2. How volatile the index is right now compared with its own history, which is what
   decides whether locking a rate is worth paying for.
3. Whether the index has a repeatable month of the year pattern, tested against the
   noise in the same data rather than asserted from a chart.

Every function takes a plain pandas series and returns plain floats, so each one can
be checked by hand against the CSV.
"""
import numpy as np
import pandas as pd


def _clean(series):
    s = pd.Series(series).astype(float)
    return s[s > 0].reset_index(drop=True)


def coverage_ratios(series, period_days):
    """Historical ratios of "average spot over the next period" to "spot today".

    For every day in the history that has a full period after it, this computes the
    mean index level over the following `period_days` trading days, divided by the
    level on that day. A ratio of 1.08 means that on that occasion, a buyer who
    fixed at that day's rate for the whole period would have paid 8 percent less
    than one who bought the same period on the spot market day by day.

    This is a proper out of sample statement about the past. It uses no information
    from inside the period it is describing beyond the average it is measuring, and
    it never touches the future of the series relative to the day being measured.
    """
    s = _clean(series)
    w = int(max(1, period_days))
    if len(s) < w + 30:
        return np.array([])
    # Mean of days t+1 .. t+w, expressed against the level at day t.
    fwd_mean = s.shift(-1).rolling(w).mean().shift(-(w - 1))
    ratio = (fwd_mean / s).dropna()
    return ratio.to_numpy()


def period_outlook(series, period_days):
    """Summarise those ratios into the numbers a buyer can act on.

    `expected` is the median rather than the mean, because the ratios are a
    positive, right skewed quantity and the median is the value a buyer should plan
    around. The mean is reported beside it so the skew is visible rather than
    hidden.
    """
    r = coverage_ratios(series, period_days)
    if r.size < 30:
        return None
    return {
        "period_days": int(period_days),
        "observations": int(r.size),
        "expected_ratio": float(np.median(r)),
        "mean_ratio": float(np.mean(r)),
        "p10_ratio": float(np.percentile(r, 10)),
        "p90_ratio": float(np.percentile(r, 90)),
        "sd_ratio": float(np.std(r, ddof=1)),
        # How often the spot market over the period came out ABOVE the level you
        # could have fixed at on day one. This is the probability that fixing was
        # the cheaper choice, measured, not modelled.
        "share_above_one": float(np.mean(r > 1.0)),
    }


def realised_volatility(series, window_days=21, trading_days_per_year=252):
    """Annualised volatility of daily log returns over the most recent window."""
    s = _clean(series)
    if len(s) < window_days + 2:
        return None
    lr = np.diff(np.log(s.to_numpy()))
    recent = lr[-window_days:]
    return float(np.std(recent, ddof=1) * np.sqrt(trading_days_per_year))


def volatility_regime(series, window_days=21, high_percentile=0.75):
    """Today's volatility against every other day this index has ever had.

    A number like "38 percent annualised" means nothing to a buyer on its own. What
    means something is that it sits above three quarters of the days this index has
    ever seen, which is why the percentile is what the interface shows.
    """
    s = _clean(series)
    if len(s) < window_days + 260:
        return None
    lr = pd.Series(np.diff(np.log(s.to_numpy())))
    rolling = lr.rolling(window_days).std(ddof=1) * np.sqrt(252)
    rolling = rolling.dropna()
    if rolling.empty:
        return None
    current = float(rolling.iloc[-1])
    pct = float((rolling < current).mean())
    if pct >= max(high_percentile, 0.9):
        band, plain = "high", ("Prices are moving more violently than on nine days out of "
                               "ten in this index's whole history.")
    elif pct >= high_percentile:
        band, plain = "elevated", ("Prices are moving more than usual. Committing to a rate "
                                   "is worth more than it normally is.")
    elif pct <= 0.25:
        band, plain = "calm", ("Prices are unusually steady, so there is less to gain from "
                               "locking a rate right now.")
    else:
        band, plain = "normal", "Prices are moving about as much as they usually do."
    return {
        "window_days": int(window_days),
        "annualised_volatility": current,
        "percentile_of_history": pct,
        "band": band,
        "plain": plain,
        "median_annualised_volatility": float(rolling.median()),
    }


def seasonality(dates, series, min_years=3, rotations=199, alpha=0.05):
    """Month of the year effects, tested against the noise in the same series.

    WHY THIS IS NOT A SIMPLE AVERAGE WITH ERROR BARS.

    Two earlier versions of this function were wrong in the same direction, and both
    were caught by handing it a pure random walk, which by construction has no
    seasonality at all, and watching what it claimed to find.

    The first averaged daily deviations and divided by the square root of the number
    of DAYS in each month. That treats twenty two trading days in one March as
    twenty two independent observations of March, when consecutive days are nearly
    the same number. It reported eight meaningful months out of twelve, in noise.

    The second averaged to one number per month per year, which is the right unit,
    and still reported three out of twelve, because the deviations from a centred
    one year average stay correlated from month to month and from year to year.

    What is used now makes no assumption about independence at all. The calendar is
    ROTATED. The deviation series is circularly shifted by many different offsets
    while the dates stay where they are, which destroys the alignment between the
    series and the months of the year while leaving every other property of the
    series, including all of its autocorrelation, exactly as it was. Each rotation
    produces the largest month effect that this series throws up by chance alone. If
    the real, unrotated alignment produces a larger effect than almost all of those,
    the pattern is in the calendar rather than in the wandering. If it does not, the
    honest answer is that there is no month effect to report, and that is what the
    interface then says.

    Taking the LARGEST month effect as the statistic also handles the fact that
    twelve months are being tested at once, which is the other way a chart of monthly
    averages fools people.
    """
    s = _clean(series)
    d = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    n = min(len(s), len(d))
    s, d = s.iloc[:n], d.iloc[:n]
    if n < 400:
        return None

    # Deviation from a centred one year average removes the level and the trend, so
    # what is left is the within-year shape rather than the direction of the market.
    trend = s.rolling(253, center=True, min_periods=130).mean()
    dev = (s / trend - 1.0).dropna()
    months = d.loc[dev.index].dt.month.to_numpy()
    years = d.loc[dev.index].dt.year
    n_years = int(years.nunique())
    if n_years < min_years:
        return None

    values = dev.to_numpy()
    m_index = [np.flatnonzero(months == m) for m in range(1, 13)]
    counts = np.array([len(ix) for ix in m_index])

    def month_means(vals):
        return np.array([vals[ix].mean() if len(ix) else np.nan for ix in m_index])

    observed = month_means(values)

    # The null distribution of "the largest monthly deviation this series produces by
    # chance". Offsets are evenly spaced rather than random, so the same history
    # always gives the same answer, which matters when the number is shown on screen
    # during a demonstration.
    length = len(values)
    step = max(1, length // (rotations + 1))
    year_len = 253                      # trading days in a year, the rotation period
    guard = 30                          # how close to a whole year is too close

    null_max = []
    for i in range(1, rotations + 1):
        shift = (i * step) % length
        # A shift of nearly a whole number of years puts the calendar back roughly
        # where it started, so that rotation still contains the very effect it is
        # supposed to be a null for. Leaving those in makes the null distribution too
        # wide and the test unable to detect anything, which is how this was found:
        # a five percent seasonal wave deliberately built into the scaffolding data
        # went undetected until these rotations were excluded.
        offset = shift % year_len
        if shift == 0 or offset < guard or offset > year_len - guard:
            continue
        null_max.append(np.nanmax(np.abs(month_means(np.roll(values, shift)))))
    null_max = np.array(null_max)
    if len(null_max) < 30:
        return None

    observed_max = float(np.nanmax(np.abs(observed)))
    p_value = float((np.sum(null_max >= observed_max) + 1) / (len(null_max) + 1))
    # One threshold for all twelve months, from the same null distribution.
    threshold = float(np.quantile(null_max, 1.0 - alpha)) if len(null_max) else float("inf")

    rows = []
    for i, m in enumerate(range(1, 13)):
        if counts[i] < 15:
            continue
        mean = float(observed[i])
        rows.append({
            "month": int(m),
            "month_name": ["January", "February", "March", "April", "May", "June", "July",
                           "August", "September", "October", "November", "December"][m - 1],
            "mean_deviation": mean,
            "observations": int(counts[i]),
            "years_observed": int(years[months == m].nunique()),
            "meaningful": bool(abs(mean) > threshold),
        })
    if not rows:
        return None

    meaningful = [r for r in rows if r["meaningful"]]
    cheapest = min(rows, key=lambda r: r["mean_deviation"])
    dearest = max(rows, key=lambda r: r["mean_deviation"])
    return {
        "years_covered": n_years,
        "months": rows,
        "meaningful_months": len(meaningful),
        "cheapest_month": cheapest,
        "dearest_month": dearest,
        "any_meaningful": bool(meaningful),
        "threshold": threshold,
        "p_value": p_value,
        "rotations": int(len(null_max)),
        "test": ("Calendar rotation test. The largest month effect in the real calendar is "
                 f"compared against the largest one produced by {len(null_max)} rotations of "
                 "the same series, which have no calendar meaning by construction."),
    }


def optimal_coverage(expected_ratio, term_ratio, sd_ratio, risk_aversion):
    """How much of a programme to fix on a term contract, and why.

    The buyer pays a known `term_ratio` on the covered share and an unknown spot
    average on the rest. Writing k for the covered share, expected cost is

        k * term + (1 - k) * expected_spot

    and the uncertainty left in the bill is proportional to (1 - k) * sd. Trading
    the two off with a mean variance objective

        minimise  k * term + (1 - k) * expected + lambda * ((1 - k) * sd) ** 2

    has one interior solution, obtained by differentiating and setting to zero,

        1 - k = (term - expected) / (2 * lambda * sd ** 2)

    which is clipped into the range zero to one. The shape of the answer is the part
    worth saying out loud. Cover everything when the term rate is at or below where
    spot is expected to sit, because it is then both cheaper and safer. Cover less as
    the owner asks a larger premium for that certainty, and cover more when spot is
    volatile, because volatility is what the premium is buying protection from. With
    no risk aversion the answer collapses to all or nothing, which is exactly why the
    risk aversion figure is written down in cost_assumptions.json as a policy choice
    rather than buried here.
    """
    sd = max(float(sd_ratio or 0.0), 1e-9)
    lam = float(risk_aversion or 0.0)
    if lam <= 0:
        return 1.0 if term_ratio <= expected_ratio else 0.0
    uncovered = (float(term_ratio) - float(expected_ratio)) / (2.0 * lam * sd * sd)
    return float(min(1.0, max(0.0, 1.0 - uncovered)))
