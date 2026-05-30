"""Canonical backtest of the live AI-infrastructure 12-1 momentum strategy.

Universe and bucket-cap logic are imported from signals.py (single source of
truth), so this backtest reflects exactly what trade.py will trade. Runs the
strategy BOTH with the bucket cap (MAX_PER_BUCKET) and uncapped, and prints a
side-by-side of CAGR / Sharpe / MaxDD so the cost/benefit of the cap is explicit.

CAVEAT: the AI-infra universe is a curated thematic snapshot and embeds
thesis-construction bias. Recent-IPO names (e.g. GEV 2024, SNDK 2025, CEG 2022)
simply don't participate in earlier rebalances - they're dropped where price
history is missing. A production backtest should use point-in-time constituents.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

from signals import LOOKBACK, SKIP, TOP_N, UNIVERSE, MAX_PER_BUCKET, apply_bucket_caps

UNCAPPED = 10_000          # max_per_bucket value that disables the cap
END = "2024-12-31"
START = "2015-01-01"       # need >= LOOKBACK + SKIP days before the first signal
REBAL_FREQ = "W-MON"


def load_prices(start=START, end=END):
    df = yf.download(
        UNIVERSE + ["SPY"], start=start, end=end,
        auto_adjust=True, progress=False,
    )["Close"]
    return df.dropna(how="all")


def build_weights(universe, top_n=TOP_N, lookback=LOOKBACK, skip=SKIP,
                  rebal=REBAL_FREQ, max_per_bucket=MAX_PER_BUCKET):
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

        # Drop tickers missing either endpoint (didn't trade yet / delisted gap).
        mom = (end_px / start_px - 1).dropna()
        if len(mom) < top_n:
            continue

        ranked = mom.sort_values(ascending=False).index
        winners = apply_bucket_caps(ranked, top_n=top_n, max_per_bucket=max_per_bucket)

        if not winners:
            continue
        weights.loc[dt, :] = 0.0
        weights.loc[dt, winners] = 1.0 / len(winners)
        if first_valid is None:
            first_valid = dt

    weights = weights.ffill().fillna(0.0)
    return weights, first_valid


def metrics(ret):
    n = len(ret)
    total = (1 + ret).prod() - 1
    yrs = n / 252
    cagr = (1 + total) ** (1 / yrs) - 1 if yrs > 0 else 0.0
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    cum = (1 + ret).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    return {"cagr": cagr, "sharpe": sharpe, "max_dd": max_dd, "cum": cum}


def main():
    print(f"Universe: {len(UNIVERSE)} AI-infra stocks  |  Top-N: {TOP_N}  |  "
          f"bucket cap: {MAX_PER_BUCKET}")
    print("Loading prices (30-60s for ~35 tickers)...")
    prices = load_prices()
    universe = prices.reindex(columns=UNIVERSE)  # NaN cols for not-yet-listed names
    daily_ret = universe.pct_change(fill_method=None).fillna(0.0)
    bench_all = prices["SPY"].pct_change(fill_method=None).fillna(0.0)
    n_with_data = int(universe.notna().any().sum())
    print(f"Loaded {n_with_data}/{len(UNIVERSE)} tickers with data, {len(universe)} rows\n")

    runs = [
        (f"Capped (max {MAX_PER_BUCKET}/bucket)", MAX_PER_BUCKET),
        ("Uncapped (raw top-10)", UNCAPPED),
    ]

    results = {}
    curves = {}
    window_start = None
    for label, mpb in runs:
        weights, first_valid = build_weights(universe, max_per_bucket=mpb)
        strat = (weights.shift(1) * daily_ret).sum(axis=1).loc[first_valid:]
        m = metrics(strat)
        results[label] = m
        curves[label] = m["cum"]
        window_start = first_valid

    bench_m = metrics(bench_all.loc[window_start:])
    curves["SPY benchmark"] = bench_m["cum"]

    print(f"Backtest window: {window_start.date()} -> {universe.index[-1].date()}\n")
    print(f"{'Strategy':28s}{'CAGR':>10s}{'Sharpe':>9s}{'MaxDD':>10s}")
    print("-" * 57)
    for label, _ in runs:
        m = results[label]
        print(f"{label:28s}{m['cagr']:>+10.2%}{m['sharpe']:>9.2f}{m['max_dd']:>+10.2%}")
    print(f"{'SPY benchmark':28s}{bench_m['cagr']:>+10.2%}{bench_m['sharpe']:>9.2f}{bench_m['max_dd']:>+10.2%}")

    capped = results[runs[0][0]]
    uncapped = results[runs[1][0]]
    print("\nCap trade-off (capped minus uncapped):")
    print(f"  CAGR   {capped['cagr'] - uncapped['cagr']:+.2%}   (cost of the cap if negative)")
    print(f"  Sharpe {capped['sharpe'] - uncapped['sharpe']:+.2f}")
    print(f"  MaxDD  {capped['max_dd'] - uncapped['max_dd']:+.2%}   (positive = shallower drawdown saved)")

    fig, ax = plt.subplots(figsize=(10, 5))
    curves[runs[0][0]].plot(ax=ax, label=runs[0][0], linewidth=1.5)
    curves[runs[1][0]].plot(ax=ax, label=runs[1][0], linewidth=1.3, alpha=0.8)
    curves["SPY benchmark"].plot(ax=ax, label="SPY buy & hold", linewidth=1.3, alpha=0.7)
    ax.set_title(f"AI-Infra 12-1 Momentum: Capped vs Uncapped vs SPY (top-{TOP_N})")
    ax.set_ylabel("Growth of $1")
    ax.set_xlabel("")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("backtest_stocks.png", dpi=120)
    print("\nSaved: backtest_stocks.png")


if __name__ == "__main__":
    main()
