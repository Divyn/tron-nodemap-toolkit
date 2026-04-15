"""
Fetch all TRON node IPs from TronScan's node map API. https://github.com/tronscan/tronscan-frontend/blob/master/document/api.md
Run: python fetch_tron_nodes.py
Outputs: tron_nodes.csv in the same directory

Other scripts can call fetch_nodemap_rows() for the same HTTP + parse logic without reading CSV.
peer_graph.py (same directory) calls fetch_nodemap_rows() when you run it.
"""

import json
import csv
import urllib.request
from typing import Any

URL = "https://apilist.tronscan.org/api/nodemap"


def fetch_nodemap_rows(*, timeout: int = 30) -> list[dict[str, Any]]:
    """
    GET TronScan nodemap JSON and return one dict per node:
    ip, city, country, latitude, longitude.

    Raises urllib.error.URLError on network failure. Returns [] only if the API
    returns an empty list (unexpected format raises ValueError).
    """
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    if isinstance(data, dict) and "data" in data:
        nodes = data["data"]
    elif isinstance(data, list):
        nodes = data
    else:
        raise ValueError(
            "Unexpected nodemap response format. Keys: "
            f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
        )

    rows: list[dict[str, Any]] = []
    for node in nodes:
        ip = node.get("ip", node.get("host", node.get("address", "unknown")))
        rows.append(
            {
                "ip": ip,
                "city": node.get("city", ""),
                "country": node.get("country", ""),
                "latitude": node.get("lat", node.get("latitude", "")),
                "longitude": node.get("lng", node.get("longitude", "")),
            }
        )
    return rows


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

    # Print all IPs
    print("=" * 50)
    print("ALL NODE IPs:")
    print("=" * 50)
    for r in rows:
        loc = f" ({r['city']}, {r['country']})" if r["city"] else (f" ({r['country']})" if r["country"] else "")
        print(f"  {r['ip']}{loc}")

    # Save to CSV
    csv_path = "tron_nodes.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ip", "city", "country", "latitude", "longitude"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} nodes to {csv_path}")


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Fetch TronScan TRON nodemap.")
    ap.add_argument(
        "--json-stdout",
        action="store_true",
        help="Print one JSON array of row objects to stdout (no CSV, no per-IP listing).",
    )
    ns = ap.parse_args()
    if ns.json_stdout:
        try:
            rows = fetch_nodemap_rows()
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Fetch failed: {e}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(rows))
    else:
        cli_fetch_and_save()
