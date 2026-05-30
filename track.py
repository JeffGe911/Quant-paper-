"""Append today's Alpaca account snapshot to nav.csv for performance tracking."""

import csv
import os
from datetime import date
from pathlib import Path

from alpaca.trading.client import TradingClient
from dotenv import load_dotenv

load_dotenv()

client = TradingClient(
    os.getenv("ALPACA_KEY"),
    os.getenv("ALPACA_SECRET"),
    paper=True,
)

OUTPUT = Path("nav.csv")


def snapshot():
    account = client.get_account()
    row = {
        "date": date.today().isoformat(),
        "equity": float(account.equity),
        "cash": float(account.cash),
        "last_equity": float(account.last_equity),
    }

    write_header = not OUTPUT.exists()
    with OUTPUT.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            w.writeheader()
        w.writerow(row)

    print(row)


if __name__ == "__main__":
    snapshot()
