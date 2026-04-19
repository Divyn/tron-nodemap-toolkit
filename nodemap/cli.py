"""Command-line listing and CSV export for nodemap rows."""
from __future__ import annotations

import csv

from nodemap.client import fetch_nodemap_rows


def cli_fetch_and_save() -> None:
    print("Fetching TRON node map data...")
    try:
        rows = fetch_nodemap_rows()
    except ValueError as e:
        print(e)
        return
    except OSError as e:
        print(f"Fetch failed: {e}")
        return

    print(f"Found {len(rows)} nodes\n")

    print("=" * 50)
    print("ALL NODE IPs:")
    print("=" * 50)
    for r in rows:
        loc = (
            f" ({r['city']}, {r['country']})"
            if r["city"]
            else (f" ({r['country']})" if r["country"] else "")
        )
        print(f"  {r['ip']}{loc}")

    csv_path = "tron_nodes.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ip", "city", "country", "latitude", "longitude"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} nodes to {csv_path}")
