# Sector Momentum Paper Trading

Minimal cross-sectional momentum strategy on the 11 SPDR sector ETFs,
executed weekly via Alpaca's paper trading API. ~200 lines of Python total.

## Strategy

- **Universe**: XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC
- **Signal**: 12-month total return skipping the most recent month (classic 12-1 momentum, Jegadeesh & Titman 1993)
- **Portfolio**: long top 5, equal-weight
- **Rebalance**: weekly (Monday after US open)
- **Sizing**: target value per position = account equity / 5 (scales automatically with NAV)

## Project layout

```
quant-paper/
├── signals.py       # universe + momentum scoring
├── trade.py         # Alpaca paper rebalance (diff-based, fractional shares)
├── track.py         # append daily equity to nav.csv
├── backtest.py      # vectorized backtest vs SPY since 2010
├── requirements.txt
├── .env.example
└── .github/workflows/
    ├── rebalance.yml   # weekly trade.py
    └── track.yml       # daily track.py + auto-commit nav.csv
```

## Setup

```bash
git clone <your-fork-url> && cd quant-paper
pip install -r requirements.txt
cp .env.example .env
# edit .env, paste your Alpaca paper API key + secret
```

Keys come from the Alpaca paper dashboard (Home page, "API Keys" section).
They start with `PK`.

## Run locally

```bash
python signals.py    # print current 12-1 momentum ranking
python backtest.py   # backtest since 2010, saves backtest.png
python trade.py      # submit rebalance orders to Alpaca paper
python track.py      # append today's equity to nav.csv
```

## Automation via GitHub Actions

1. Push this repo to GitHub (private is fine).
2. In repo Settings → Secrets and variables → Actions, add:
   - `ALPACA_KEY`
   - `ALPACA_SECRET`
3. The two workflows will run on schedule. You can also trigger them manually
   from the Actions tab via "Run workflow".

`track.yml` commits `nav.csv` back to the repo, so your equity history is
versioned and visible without leaving GitHub.

## Things to try next

- **Quality filter** — only hold ETFs trading above their 200-day MA (avoid bear regimes)
- **Risk-adjusted momentum** — rank by Sharpe (return / vol) instead of raw return
- **Expand universe** — top 50 S&P 500 names by liquidity, equal-weight top 10
- **Transaction cost model** — add 1-2 bps slippage + commission to the backtest
- **Layer in alternative signals** — anything orthogonal: macro, sentiment, your own factor

## Going live

When you want real money:

1. Open a live Alpaca account, complete KYC, fund with $1000+
2. Generate live API keys
3. Replace the keys in `.env` (or GitHub secrets)
4. In `trade.py`, change `paper=True` to `paper=False`
5. Push and let the workflow run

The position sizing logic already scales to whatever your equity is, so the
same code works at $1k or $1M.

## Notes / caveats

- 12-1 momentum on sector ETFs has decayed substantially post-2018; the backtest
  will show this. The point of running paper is to see how the live edge looks
  *today*, not to assume the historical Sharpe holds.
- Alpaca paper does not simulate dividends. Backtest uses auto-adjusted prices
  (includes dividends), so paper and backtest will diverge slightly.
- Pattern Day Trader rules apply on paper accounts below $25k equity. Since this
  is a weekly strategy you won't hit them, but be aware.
