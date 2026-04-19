#!/usr/bin/env python3
"""
Gossip traversal trace for a user-submitted TRON transaction.

Scenario (toy): a user submits a tx via RPC at TEST_ORIGIN (an IP + lat/lon
that is NOT in the listener nodemap). Assume SR propagation already happened.
We trace how the tx propagates outward through the listener network via the
geo-proximity gossip model (edge iff haversine <= LINK_KM; synchronous rounds),
and plot the traversal on a regional map.

Adjust constants below in code. No CLI flags.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from gossip import plot_interactive_map, simulate_gossip, write_rounds_txt, write_trace_csv

SRC = Path(__file__).resolve().parent

# ---- hardcoded config (edit in place) ----
INPUT = SRC / "tron_nodes.csv"
LINK_KM = 800.0
OUT_PREFIX = SRC / "run1_gossip_tx"

# Test origin = where the tx enters the network.
# RFC 5737 TEST-NET IP is guaranteed not to collide with real listener IPs.
TEST_ORIGIN: dict = {
    "ip": "203.0.113.42",
    "city": "RPC-entry",
    "country": "Test",
    "latitude": 50.1109,    # Frankfurt (edit freely)
    "longitude": 8.6821,
}

# Interactive map options (passed to gossip.interactive.plot_interactive_map)
SHOW_BROWSER = True          # fig.show() pops open default browser
SAVE_PICKLE = True           # also pickle the Figure for reload in Python
SHOW_UNREACHABLE_IN_VIEW = True


def main() -> None:
    nodes = pd.read_csv(INPUT)
    if TEST_ORIGIN["ip"] in set(nodes["ip"].astype(str)):
        raise SystemExit(f"test origin {TEST_ORIGIN['ip']} collides with listener set")

    nodes_plus = pd.concat([nodes, pd.DataFrame([TEST_ORIGIN])], ignore_index=True)
    origin_ip = TEST_ORIGIN["ip"]
    origin_loc = (
        f"{TEST_ORIGIN['city']}, {TEST_ORIGIN['country']} "
        f"({TEST_ORIGIN['latitude']}, {TEST_ORIGIN['longitude']})"
    )

    hop_of, parent_of, parent_km_of, candidates_of, rounds = simulate_gossip(
        nodes_plus, origin_ip, link_km=LINK_KM,
    )

    trace_csv = Path(f"{OUT_PREFIX}_trace.csv")
    rounds_txt = Path(f"{OUT_PREFIX}_rounds.txt")
    map_pkl = Path(f"{OUT_PREFIX}_map.pkl") if SAVE_PICKLE else None

    write_trace_csv(
        trace_csv, nodes_plus, origin_ip,
        hop_of, parent_of, parent_km_of, candidates_of,
    )
    write_rounds_txt(
        rounds_txt, origin_ip, origin_loc, LINK_KM,
        graph_nodes=len(nodes_plus), rounds=rounds,
    )
    plot_interactive_map(
        map_pkl,
        nodes_plus,
        origin_ip,
        hop_of,
        parent_of,
        parent_km_of,
        link_km=LINK_KM,
        origin_label=str(TEST_ORIGIN["city"]),
        show=SHOW_BROWSER,
        show_unreachable_in_view=SHOW_UNREACHABLE_IN_VIEW,
    )

    hop_hist = {
        h: sum(1 for v in hop_of.values() if v == h)
        for h in sorted(set(hop_of.values()))
    }
    print(f"tx entry          {origin_ip}  ({origin_loc})")
    print(f"link_km           {LINK_KM:g}")
    print(f"graph nodes       {len(nodes_plus)}")
    print(f"reachable         {len(hop_of)}")
    print(f"hop histogram     {hop_hist}")
    for p in (trace_csv, rounds_txt, map_pkl):
        if p is not None:
            print(f"wrote             {p}")


if __name__ == "__main__":
    main()
