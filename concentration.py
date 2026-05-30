"""Concentration monitor for the live momentum book.

For today's target portfolio (signals.get_targets - no Alpaca calls), reports
and logs:
  - per-bucket exposure (chips / memory / power) on the current book
  - which bucket(s) are AT the cap (binding) - the live signal that momentum
    wants to lean harder than MAX_PER_BUCKET allows
  - which names are held in each bucket
  - the bucket size of the universe (for context if buckets are tuned)

Appends one timestamped row to concentration_log.csv. Also lists each bucket's
membership so you can eyeball whether any name is mis-bucketed (the realistic
"VRT leak" check - code can't infer correct thematic exposure, only a human can).

No live orders.
"""

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from signals import (
    BUCKETS, BUCKET_OF, MAX_PER_BUCKET, TOP_N, UNIVERSE, get_targets,
)

LOG = Path("concentration_log.csv")
FIELDS = [
    "timestamp", "n_positions", "max_per_bucket",
    "chips_count", "memory_count", "power_count",
    "max_bucket_count", "binding_buckets",
    "bucket_holdings", "book",
]


def integrity_review():
    # Spec asserts already live in signals.py (no duplicates / BUCKET_OF == UNIVERSE).
    # This is the human-review surface: print each bucket's roster so the user can
    # eyeball mis-classifications.
    print(f"Integrity: UNIVERSE = {len(UNIVERSE)} names across {len(BUCKETS)} buckets")
    for b, names in BUCKETS.items():
        print(f"  {b:<7s} ({len(names):>2d}): {', '.join(names)}")


def monitor():
    targets, _ = get_targets()
    n = len(targets)
    bucket_counts = Counter(BUCKET_OF[t] for t in targets)
    # ensure all bucket keys present even if count is 0
    counts = {b: bucket_counts.get(b, 0) for b in BUCKETS}
    max_count = max(counts.values()) if counts else 0
    binding = [b for b, c in counts.items() if c == MAX_PER_BUCKET]

    # which names sit in each bucket on today's book
    holdings = {b: [t for t in targets if BUCKET_OF[t] == b] for b in BUCKETS}

    print(f"\nLive book ({n} positions): {', '.join(targets)}")
    print("Bucket exposure:")
    for b in BUCKETS:
        flag = "  <- AT CAP" if counts[b] == MAX_PER_BUCKET else ""
        names = ", ".join(holdings[b]) if holdings[b] else "(none)"
        print(f"  {b:<7s} {counts[b]}/{MAX_PER_BUCKET}{flag}    {names}")
    if binding:
        print(f"BINDING: bucket cap is biting in {', '.join(binding)} "
              f"(momentum wants more than {MAX_PER_BUCKET})")

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_positions": n,
        "max_per_bucket": MAX_PER_BUCKET,
        "chips_count": counts["chips"],
        "memory_count": counts["memory"],
        "power_count": counts["power"],
        "max_bucket_count": max_count,
        "binding_buckets": "|".join(binding),
        "bucket_holdings": "|".join(
            f"{b}:{','.join(holdings[b])}" for b in BUCKETS if holdings[b]
        ),
        "book": "|".join(targets),
    }
    write_header = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(row)
    print(f"\nLogged 1 row to {LOG}")


def main():
    integrity_review()
    monitor()


if __name__ == "__main__":
    main()
