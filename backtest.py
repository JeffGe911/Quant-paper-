"""Vectorized backtest of the 12-1 SECTOR-ETF momentum strategy vs SPY.

This is the pre-individual-stocks baseline (11 SPDR sector ETFs, equal-weight
top-5). The live strategy now trades individual stocks — see backtest_stocks.py
for the canonical, sector-capped stock backtest.

Outputs CAGR / Sharpe / max drawdown for both, and saves a cumulative-return plot.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

from signals import LOOKBACK, SKIP, SECTOR_ETFS, SECTOR_TOP_N as TOP_N

START = "2010-01-01"
END = None  # today
REBAL_FREQ = "W-MON"  # weekly, Monday close


def load_prices(start=START, end=END):
    tickers = SECTOR_ETFS + ["SPY"]
    df = yf.download(
        tickers, start=start, end=end,
        auto_adjust=True, progress=False,
    )["Close"]
    return df.dropna(how="all")


def build_weights(universe, top_n=TOP_N, lookback=LOOKBACK, skip=SKIP, rebal=REBAL_FREQ):
    """Construct a daily weight matrix from rebalance-date decisions."""
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
        winners = mom.sort_values(ascending=False).head(top_n).index

        weights.loc[dt, :] = 0.0
        weights.loc[dt, winners] = 1.0 / top_n
        if first_valid is None:
            first_valid = dt

    # Forward-fill: hold each rebalance's allocation until the next one.
    weights = weights.ffill().fillna(0.0)
    return weights, first_valid


def run_backtest(prices):
    universe = prices[SECTOR_ETFS].dropna()
    daily_ret = universe.pct_change().fillna(0.0)

    weights, first_valid = build_weights(universe)

    # Portfolio return = yesterday's weights * today's return.
    strat_ret = (weights.shift(1) * daily_ret).sum(axis=1)
    bench_ret = prices["SPY"].pct_change().fillna(0.0).reindex(strat_ret.index).fillna(0.0)

    if first_valid is not None:
        strat_ret = strat_ret.loc[first_valid:]
        bench_ret = bench_ret.loc[first_valid:]

    return strat_ret, bench_ret


def stats(ret, name):
    n = len(ret)
    if n == 0:
        print(f"{name}: no data")
        return None
    total = (1 + ret).prod() - 1
    yrs = n / 252
    cagr = (1 + total) ** (1 / yrs) - 1 if yrs > 0 else 0.0
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    cum = (1 + ret).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    print(f"{name:20s}  CAGR: {cagr:+7.2%}   Sharpe: {sharpe:5.2f}   MaxDD: {max_dd:7.2%}")
    return cum


def main():
    prices = load_prices()
    strat, bench = run_backtest(prices)

    print(f"\nBacktest window: {strat.index[0].date()} -> {strat.index[-1].date()}\n")
    s_cum = stats(strat, f"Sector ETF momentum (top-{TOP_N})")
    b_cum = stats(bench, "SPY benchmark")

    fig, ax = plt.subplots(figsize=(10, 5))
    s_cum.plot(ax=ax, label=f"Sector ETF momentum top-{TOP_N}", linewidth=1.4)
    b_cum.plot(ax=ax, label="SPY buy & hold", linewidth=1.4, alpha=0.75)
    ax.set_title("12-1 Sector-ETF Momentum vs SPY — cumulative return")
    ax.set_ylabel("Growth of $1")
    ax.set_xlabel("")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("backtest.png", dpi=120)
    print("\nSaved: backtest.png")


if __name__ == "__main__":
    main()
