"""Cross-sectional 12-1 momentum signal on a narrow AI-infrastructure universe.

The universe is three correlated buckets (compute / memory / power), and the
portfolio selector greedily picks top-N momentum subject to a per-bucket cap so
no single bucket can dominate the book.

CAVEAT: the universe is a curated thematic snapshot of names that exist today;
it embeds survivorship and thesis-construction bias. For live paper trading
that's the universe we'd actually trade, so the bias is honest about what the
strategy is.
"""

import pandas as pd
import yfinance as yf

# ============================================================
# UNIVERSE - AI-infrastructure thesis
# Three buckets: compute (chips) / memory & storage / power & energy
# ============================================================

# --- compute: GPUs/ASICs, foundry, equipment, networking ---
AI_CHIPS = [
    "NVDA", "AMD", "AVGO", "TSM", "ASML", "MRVL", "ARM",
    "QCOM", "INTC", "TXN", "AMAT", "LRCX", "KLAC", "ANET", "GFS",
]

# --- memory, storage & AI systems ---
MEMORY_STORAGE = [
    "MU", "WDC", "STX", "SNDK", "PSTG", "NTAP", "SMCI", "DELL",
]

# --- power & energy for the data-center buildout ---
POWER_ENERGY = [
    "VRT", "ETN", "GEV", "PWR", "POWL", "PH", "NVT",
    "VST", "CEG", "TLN", "NRG", "NEE",
]

# spicier / lower-float names - OFF by default.
OPTIONAL_SPICY = ["CRWV", "OKLO", "SMR"]

BUCKETS = {
    "chips":  AI_CHIPS,
    "memory": MEMORY_STORAGE,
    "power":  POWER_ENERGY,
}

UNIVERSE = AI_CHIPS + MEMORY_STORAGE + POWER_ENERGY

# reverse lookup: ticker -> bucket name
BUCKET_OF = {t: b for b, names in BUCKETS.items() for t in names}

# integrity checks
assert len(UNIVERSE) == len(set(UNIVERSE)), "duplicate ticker in UNIVERSE"
assert set(BUCKET_OF) == set(UNIVERSE), "BUCKET_OF / UNIVERSE mismatch"

# selection knobs
TOP_N = 10
MAX_PER_BUCKET = 6   # loosened from 5: allows one bucket to take 6/10 if momentum demands it

# Momentum window (12-1: 12-month look-back skipping the most recent month).
LOOKBACK = 252
SKIP = 21

# Sector-ETF baseline universe (used only by the reference backtests
# backtest.py / backtest_weighted.py; not traded live, not part of the AI thesis).
SECTOR_ETFS = [
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC",
]
SECTOR_TOP_N = 5


def apply_bucket_caps(ranked, top_n=TOP_N, max_per_bucket=MAX_PER_BUCKET):
    """Greedy top-N respecting per-bucket caps.
    `ranked`: tickers sorted best->worst by momentum. Returns chosen tickers
    in rank order; a bucket at its cap is skipped so the next best from another
    bucket is taken instead."""
    selected, counts = [], {b: 0 for b in BUCKETS}
    for t in ranked:
        b = BUCKET_OF.get(t)
        if b is None or counts[b] >= max_per_bucket:
            continue
        selected.append(t)
        counts[b] += 1
        if len(selected) == top_n:
            break
    return selected


def fetch_prices(tickers=None, days=450):
    """Pull auto-adjusted close prices from yfinance.

    days=450 (~310 trading rows) leaves comfortable margin above the
    LOOKBACK + SKIP = 273 rows the signal needs, so the iloc lookups below
    stay in bounds even around holidays and recent-IPO leading NaNs.
    """
    tickers = tickers or UNIVERSE
    end = pd.Timestamp.today()
    start = end - pd.Timedelta(days=days)
    df = yf.download(
        tickers, start=start, end=end,
        auto_adjust=True, progress=False,
    )
    # how="all" keeps recent-IPO tickers (e.g. SNDK, GEV) that are NaN in the
    # earliest rows; their momentum score comes out NaN and sorts to the
    # bottom, so they simply aren't selected until they have enough history.
    return df["Close"].dropna(how="all")


def momentum_score(prices, lookback=LOOKBACK, skip=SKIP):
    """Total return over `lookback` days, skipping the last `skip` days."""
    return prices.iloc[-skip] / prices.iloc[-(lookback + skip)] - 1


def get_targets(top_n=TOP_N):
    """Return (top_n tickers after the bucket caps, full ranked score Series).

    Signature/return type unchanged from prior versions so trade.py keeps
    importing cleanly.
    """
    prices = fetch_prices()
    scores = momentum_score(prices).sort_values(ascending=False)
    targets = apply_bucket_caps(scores.dropna().index, top_n=top_n)
    return targets, scores


if __name__ == "__main__":
    targets, scores = get_targets()
    ranked = scores.dropna()

    def line(t):
        return f"  {t:6s} {scores[t]:+8.2%}  [{BUCKET_OF[t]}]"

    print(f"12-1 momentum ranking  ({len(ranked)}/{len(UNIVERSE)} with full history)")
    print(f"Universe: {len(UNIVERSE)} AI-infra names  "
          f"|  buckets: {', '.join(f'{b}={len(n)}' for b, n in BUCKETS.items())}")
    print(f"Bucket cap: max {MAX_PER_BUCKET} per bucket\n")

    print(f"Top {TOP_N} (capped - target portfolio):")
    bucket_counts = {b: 0 for b in BUCKETS}
    for t in targets:
        print(line(t))
        bucket_counts[BUCKET_OF[t]] += 1
    print(f"\nBucket exposure: " +
          ", ".join(f"{b}={c}" for b, c in bucket_counts.items()))

    uncapped = list(ranked.index[:TOP_N])
    bumped = [t for t in uncapped if t not in targets]
    added = [t for t in targets if t not in uncapped]
    if bumped:
        print("\nBumped out by the bucket cap (in the uncapped top-10):")
        for t in bumped:
            print(line(t))
        print("Promoted in their place:")
        for t in added:
            print(line(t))
