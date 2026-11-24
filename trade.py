"""Weekly rebalance into top-N momentum sector ETFs via Alpaca paper API.

Uses diff-based position adjustment with notional (dollar-amount) orders,
which works with fractional shares and small account sizes.
"""

import math
import os
import time

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from dotenv import load_dotenv

from signals import TOP_N, get_targets

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

    if len(target_set) != TOP_N:
        raise ValueError(f"Expected {TOP_N} distinct targets, got {len(target_set)}")

    # Idempotency: cancel any open orders left over from a prior dispatch
    # attempt. Without this, a pending close from a crashed earlier run pins
    # all that symbol's shares as held_for_orders, so the next close_position
    # call raises APIError 40310000 ("insufficient qty available for order").
    cancelled = client.cancel_orders()
    if cancelled:
        print(f"Cancelled {len(cancelled)} pending order(s) from prior dispatch.")
        time.sleep(2)  # let Alpaca release the held_for_orders qty

    account = client.get_account()
    equity = float(account.equity)
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError(f"Invalid account equity: {equity}")
    target_value = equity / TOP_N

    print(f"Equity:  ${equity:,.2f}")
    print(f"Target per position:  ${target_value:,.2f}")
    print(f"Targets: {targets}\n")

    positions = {p.symbol: p for p in client.get_all_positions()}
    adjustments = {}
    for sym in targets:
        current_value = float(positions[sym].market_value) if sym in positions else 0.0
        diff_value = target_value - current_value
        if not math.isfinite(diff_value):
            raise ValueError(f"Invalid dollar adjustment for {sym}: {diff_value}")
        adjustments[sym] = diff_value

    # 1. Close positions no longer in the target set.
    for sym in list(positions):
        if sym not in target_set:
            print(f"  CLOSE  {sym}")
            client.close_position(sym)

    # 2. Adjust each target to the desired notional weight.
    for sym, diff_value in adjustments.items():
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
