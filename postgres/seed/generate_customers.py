"""Seed the upstream customers table once, then exit.

Generates the initial dataset and stops. Records that arrive afterwards are the
arrivals loop's job — see source_activity.py — and both use the same generation
rule so the source stays reproducible as a whole.

See adr/0012-let-the-simulated-upstream-keep-operating.md
"""

from __future__ import annotations

import sys

from customer_rows import build_csv
from db import connect, copy_rows, require_env, row_count


def main() -> int:
    target_rows = int(require_env("SEED_ROW_COUNT"))
    random_seed = int(require_env("SEED_RANDOM_SEED"))

    connection = connect()
    try:
        existing = row_count(connection)
        if existing:
            # Restarting onto an already-seeded volume is not a cold start, and
            # records may have arrived since. Reseeding would destroy them.
            print(f"customers already holds {existing} rows; leaving it alone")
            return 0

        print(f"seeding {target_rows} rows with seed {random_seed}")
        copy_rows(connection, build_csv(1, target_rows, random_seed))

        loaded = row_count(connection)
        if loaded != target_rows:
            raise RuntimeError(f"expected {target_rows} rows after seeding, found {loaded}")

        print(f"seeded {loaded} rows into customers")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
