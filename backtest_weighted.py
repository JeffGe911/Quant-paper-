"""Backtest variant of the SECTOR-ETF baseline: weight top-N positions by
their momentum score instead of equal weight (cf. backtest.py). Tests whether
concentrating capital in the strongest sector signals captures more alpha.

Sector-ETF baseline only — the live individual-stock strategy is in
backtest_stocks.py.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from signals import LOOKBACK, SKIP, SECTOR_ETFS, SECTOR_TOP_N as TOP_N

START = "2010-01-01"
REBAL_FREQ = "W-MON"


def load_prices(start=START):
    df = yf.download(
        SECTOR_ETFS + ["SPY"], start=start,
        auto_adjust=True, progress=False,
    )["Close"]
    return df.dropna(how="all")


def scores_to_weights(top_scores):
    """Long-only weights proportional to score (clipped at 0).

    If all top-N scores are non-positive (rare; deep bear market),
    fall back to equal weight to keep the position count meaningful.
    """
    pos = top_scores.clip(lower=0)
    total = pos.sum()
    if total <= 0:
        return pd.Series(1.0 / len(top_scores), index=top_scores.index)
    return pos / total


def build_weights(universe, top_n=TOP_N, lookback=LOOKBACK, skip=SKIP, rebal=REBAL_FREQ):
    rebal_dates = universe.resample(rebal).last().index
    rebal_dates = rebal_dates[rebal_dates.isin(universe.index)]

    weights = pd.DataFrame(np.nan, index=universe.index, columns=universe.columns)
    first_valid = None

    for dt in rebal_dates:
        idx = universe.index.get_loc(dt)
        if idx < lookback + skip:
            continue
        end_px = universe.iloc[idx - skip]
        start_px = universe.iloc[idx - skip - lookback]
        mom = (end_px / start_px - 1).dropna()
        top = mom.sort_values(ascending=False).head(top_n)
        w = scores_to_weights(top)

        weights.loc[dt, :] = 0.0
        for sym, wt in w.items():
            weights.loc[dt, sym] = wt
        if first_valid is None:
            first_valid = dt

    weights = weights.ffill().fillna(0.0)
    return weights, first_valid


def run_backtest(prices):
    universe = prices[SECTOR_ETFS].dropna()
    daily_ret = universe.pct_change().fillna(0.0)

    weights, first_valid = build_weights(universe)

    strat_ret = (weights.shift(1) * daily_ret).sum(axis=1)
    bench_ret = prices["SPY"].pct_change().fillna(0.0).reindex(strat_ret.index).fillna(0.0)

    if first_valid is not None:
        strat_ret = strat_ret.loc[first_valid:]
        bench_ret = bench_ret.loc[first_valid:]

    return strat_ret, bench_ret


def stats(ret, name):
    n = len(ret)
    if n == 0:
        return None
    total = (1 + ret).prod() - 1
    yrs = n / 252
    cagr = (1 + total) ** (1 / yrs) - 1 if yrs > 0 else 0.0
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    cum = (1 + ret).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    print(f"{name:30s}  CAGR: {cagr:+7.2%}   Sharpe: {sharpe:5.2f}   MaxDD: {max_dd:7.2%}")
    return cum


def main():
    prices = load_prices()
    strat, bench = run_backtest(prices)

    print(f"\nBacktest window: {strat.index[0].date()} -> {strat.index[-1].date()}\n")
    s_cum = stats(strat, "Momentum (score-weighted)")
    b_cum = stats(bench, "SPY benchmark")

    fig, ax = plt.subplots(figsize=(10, 5))
    s_cum.plot(ax=ax, label="Momentum (score-weighted)", linewidth=1.4)
    b_cum.plot(ax=ax, label="SPY buy & hold", linewidth=1.4, alpha=0.75)
    ax.set_title("Score-Weighted Sector Momentum vs SPY")
    ax.set_ylabel("Growth of $1")
    ax.set_xlabel("")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("backtest_weighted.png", dpi=120)
    print("\nSaved: backtest_weighted.png")


if __name__ == "__main__":
    main()
