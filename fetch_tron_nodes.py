"""
Fetch all TRON node IPs from TronScan's node map API. https://github.com/tronscan/tronscan-frontend/blob/master/document/api.md
Run: python fetch_tron_nodes.py
Outputs: tron_nodes.csv in the same directory

Other scripts can call fetch_nodemap_rows() for the same HTTP + parse logic without reading CSV.
peer_graph.py (same directory) calls fetch_nodemap_rows() when you run it.

repo: https://github.com/Divyn/tron-nodemap-toolkit/tree/main
"""

from __future__ import annotations

import json
import sys

from nodemap import cli_fetch_and_save, fetch_nodemap_rows

__all__ = ["fetch_nodemap_rows", "cli_fetch_and_save"]


if __name__ == "__main__":
    import argparse

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
