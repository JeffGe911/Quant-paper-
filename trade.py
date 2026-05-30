"""Weekly rebalance into top-N momentum sector ETFs via Alpaca paper API.

Uses diff-based position adjustment with notional (dollar-amount) orders,
which works with fractional shares and small account sizes.
"""

import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from dotenv import load_dotenv

from signals import TOP_N, fetch_prices, get_targets

load_dotenv()

client = TradingClient(
    os.getenv("ALPACA_KEY"),
    os.getenv("ALPACA_SECRET"),
    paper=True,
)

MIN_TRADE_USD = 5.0  # skip rebalance adjustments smaller than this


def rebalance():
    targets, _ = get_targets()
    target_set = set(targets)

    account = client.get_account()
    equity = float(account.equity)
    target_value = equity / TOP_N

    prices = fetch_prices()
    latest = prices.iloc[-1]

    print(f"Equity:  ${equity:,.2f}")
    print(f"Target per position:  ${target_value:,.2f}")
    print(f"Targets: {targets}\n")

    positions = {p.symbol: float(p.qty) for p in client.get_all_positions()}

    # 1. Close positions no longer in the target set.
    for sym in list(positions):
        if sym not in target_set:
            print(f"  CLOSE  {sym}")
            client.close_position(sym)
            positions.pop(sym)

    # 2. Adjust each target to the desired notional weight.
    for sym in targets:
        target_shares = target_value / float(latest[sym])
        current_shares = positions.get(sym, 0.0)
        diff_value = (target_shares - current_shares) * float(latest[sym])

        if abs(diff_value) < MIN_TRADE_USD:
            print(f"  SKIP   {sym}  (diff ${diff_value:+,.2f} under threshold)")
            continue

        side = OrderSide.BUY if diff_value > 0 else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=sym,
            notional=round(abs(diff_value), 2),
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        print(f"  {side.value:5s}  {sym}  ${abs(diff_value):,.2f}  ({str(order.id)[:8]})")


if __name__ == "__main__":
    rebalance()
