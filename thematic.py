"""Discretionary 'thematic' sleeve — an independent ledger of subjective,
high-conviction positions held alongside the systematic momentum book.

WHY a separate ledger instead of trading the same Alpaca account:
trade.py closes any Alpaca position not in the momentum top-N, so a
discretionary holding on that account would be liquidated on the next
weekly rebalance. Recording thematic positions here (marked to market via
yfinance) sidesteps that conflict and keeps the two sleeves' P&L
attributable independently. If you later want this sleeve to trade real
paper orders, give it its own Alpaca account or teach trade.py to exclude
thematic symbols from its close-logic.

Usage:
    python thematic.py add AMD 10 --thesis "AI inference share gains"
    python thematic.py add AMD 10 --price 118.40   # override fill price
    python thematic.py close AMD                    # mark closed at live price
    python thematic.py status                       # mark-to-market P&L (default)
"""

import argparse
import json
from datetime import date
from pathlib import Path

import yfinance as yf

LEDGER = Path("thematic_ledger.json")


def load_ledger():
    if not LEDGER.exists():
        return {"open": [], "closed": []}
    return json.loads(LEDGER.read_text())


def save_ledger(ledger):
    LEDGER.write_text(json.dumps(ledger, indent=2))


def latest_price(ticker):
    """Most recent auto-adjusted close for a single ticker."""
    px = yf.download(ticker, period="5d", auto_adjust=True, progress=False)["Close"]
    return float(px.dropna().iloc[-1])


def latest_prices(tickers):
    if not tickers:
        return {}
    df = yf.download(tickers, period="5d", auto_adjust=True, progress=False)["Close"]
    last = df.dropna(how="all").iloc[-1]
    if len(tickers) == 1:
        return {tickers[0]: float(last)}
    return {t: float(last[t]) for t in tickers}


def add(ticker, shares, price=None, thesis=""):
    ticker = ticker.upper()
    ledger = load_ledger()
    if any(p["ticker"] == ticker for p in ledger["open"]):
        raise SystemExit(f"{ticker} already open — close it first or use a new ticker.")
    fill = price if price is not None else latest_price(ticker)
    ledger["open"].append({
        "ticker": ticker,
        "shares": shares,
        "entry_price": round(fill, 2),
        "entry_date": date.today().isoformat(),
        "thesis": thesis,
    })
    save_ledger(ledger)
    print(f"ADD   {ticker}  {shares} sh @ ${fill:,.2f}  (cost ${shares * fill:,.2f})")
    if thesis:
        print(f"      thesis: {thesis}")


def close(ticker, price=None):
    ticker = ticker.upper()
    ledger = load_ledger()
    pos = next((p for p in ledger["open"] if p["ticker"] == ticker), None)
    if pos is None:
        raise SystemExit(f"No open thematic position in {ticker}.")
    exit_px = price if price is not None else latest_price(ticker)
    pnl = (exit_px - pos["entry_price"]) * pos["shares"]
    ledger["open"].remove(pos)
    ledger["closed"].append({
        **pos,
        "exit_price": round(exit_px, 2),
        "exit_date": date.today().isoformat(),
        "realized_pnl": round(pnl, 2),
    })
    save_ledger(ledger)
    ret = exit_px / pos["entry_price"] - 1
    print(f"CLOSE {ticker}  {pos['shares']} sh @ ${exit_px:,.2f}  "
          f"P&L ${pnl:+,.2f} ({ret:+.2%})")


def status():
    ledger = load_ledger()
    open_pos = ledger["open"]
    if not open_pos:
        print("No open thematic positions.")
    else:
        prices = latest_prices([p["ticker"] for p in open_pos])
        cost_total = mv_total = 0.0
        print(f"{'TICKER':8s}{'SHARES':>9s}{'ENTRY':>12s}{'LAST':>12s}"
              f"{'MKT VAL':>14s}{'UNREAL P&L':>16s}{'RET':>9s}")
        for p in open_pos:
            last = prices[p["ticker"]]
            cost = p["entry_price"] * p["shares"]
            mv = last * p["shares"]
            pnl = mv - cost
            cost_total += cost
            mv_total += mv
            print(f"{p['ticker']:8s}{p['shares']:>9.4g}{p['entry_price']:>12,.2f}"
                  f"{last:>12,.2f}{mv:>14,.2f}{pnl:>+16,.2f}{mv / cost - 1:>+9.2%}")
        tot_pnl = mv_total - cost_total
        print("-" * 80)
        print(f"{'TOTAL':8s}{'':>9s}{'':>12s}{'':>12s}{mv_total:>14,.2f}"
              f"{tot_pnl:>+16,.2f}{mv_total / cost_total - 1:>+9.2%}")

    realized = sum(c["realized_pnl"] for c in ledger["closed"])
    if ledger["closed"]:
        print(f"\nRealized P&L (closed, {len(ledger['closed'])} trades): ${realized:+,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Discretionary thematic sleeve ledger.")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="open a discretionary position")
    p_add.add_argument("ticker")
    p_add.add_argument("shares", type=float)
    p_add.add_argument("--price", type=float, default=None, help="fill price (default: live)")
    p_add.add_argument("--thesis", default="", help="why you're holding it")

    p_close = sub.add_parser("close", help="close a discretionary position")
    p_close.add_argument("ticker")
    p_close.add_argument("--price", type=float, default=None, help="exit price (default: live)")

    sub.add_parser("status", help="mark-to-market open positions (default)")

    args = parser.parse_args()
    if args.cmd == "add":
        add(args.ticker, args.shares, args.price, args.thesis)
    elif args.cmd == "close":
        close(args.ticker, args.price)
    else:  # status or no subcommand
        status()


if __name__ == "__main__":
    main()
