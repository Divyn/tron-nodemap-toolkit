#!/usr/bin/env python3
"""
Peer / infra graph from the live TronScan nodemap: IP co-occurrence in one snapshot,
k-core numbers, and a simple core-vs-periphery label.

Run from this directory (needs fetch_tron_nodes.py and pip install -r requirements.txt):

  python peer_graph.py
      Default: small peer list — first SMALL_PEER_GRAPH_NODES IPs (sorted) from the nodemap.
  python peer_graph.py --allow-large
      Full nodemap (~7k nodes); slow and nearly complete graph and millions of edges.

Writes ./run1_nodes.csv and ./run1_stats.txt

repo: https://github.com/Divyn/tron-nodemap-toolkit/tree/main
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, DefaultDict

import networkx as nx

OUT_PREFIX = Path("./run1")

# Default co-occurrence graph size (sorted IPs from nodemap; deterministic “small peer list”).
SMALL_PEER_GRAPH_NODES = 1000


def load_tronscan_nodemap_snapshot(*, allow_large: bool) -> list[tuple[str, frozenset[str]]]:
    """
    One snapshot from fetch_tron_nodes.fetch_nodemap_rows() (live API).

    If allow_large is False, keep only the first SMALL_PEER_GRAPH_NODES IPs after sorting
    (stable, cheap co-occurrence clique — not a sampled P2P peer list from the wire).
    """
    from fetch_tron_nodes import fetch_nodemap_rows

    rows: list[dict[str, Any]] = fetch_nodemap_rows()
    ips: list[str] = []
    for row in rows:
        ip = str(row.get("ip", "")).strip()
        if ip and ip.lower() != "unknown":
            ips.append(ip)

    ips_sorted = sorted(set(ips))
    total = len(ips_sorted)
    if not allow_large and total > SMALL_PEER_GRAPH_NODES:
        ips_sorted = ips_sorted[:SMALL_PEER_GRAPH_NODES]
        print(
            f"Small peer graph: using {len(ips_sorted)} of {total} nodemap IPs "
            f"(sorted, cap={SMALL_PEER_GRAPH_NODES}). "
            "Pass --allow-large for the full nodemap.",
            file=sys.stderr,
        )
    elif allow_large and total > SMALL_PEER_GRAPH_NODES:
        print(
            f"Full nodemap graph: {total} nodes (expect long runtime and dense co-occurrence).",
            file=sys.stderr,
        )

    snap_id = "tronscan_nodemap_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return [(snap_id, frozenset(ips_sorted))]


def _pairs_for_snapshot(nodes: frozenset[str]) -> Iterator[tuple[str, str]]:
    ordered = sorted(nodes)
    return combinations(ordered, 2)


def build_cooccurrence_graph(snapshots: list[tuple[str, frozenset[str]]]) -> nx.Graph:
    weights: DefaultDict[tuple[str, str], float] = defaultdict(float)
    node_in_snapshots: DefaultDict[str, set[str]] = defaultdict(set)

    for snap_id, nodes in snapshots:
        n = len(nodes)
        for ip in nodes:
            node_in_snapshots[ip].add(snap_id)
        w_add = 1.0 / max(1, n * (n - 1) / 2) if n > 1 else 0.0
        for u, v in _pairs_for_snapshot(nodes):
            a, b = (u, v) if u < v else (v, u)
            weights[(a, b)] += w_add

    g = nx.Graph()
    for ip in node_in_snapshots:
        g.add_node(ip)
    for (u, v), w in weights.items():
        if w > 0:
            g.add_edge(u, v, weight=w, cooccurrence=w)
    nx.set_node_attributes(
        g,
        {ip: len(sids) for ip, sids in node_in_snapshots.items()},
        name="snapshot_count",
    )
    return g


def analyze_core_periphery(g: nx.Graph) -> tuple[dict[str, int], dict[str, str], int]:
    if g.number_of_nodes() == 0:
        return {}, {}, 0
    core_num = nx.core_number(g)
    k_max = max(core_num.values()) if core_num else 0
    labels = {n: "core" if core_num.get(n, 0) == k_max and k_max > 0 else "periphery" for n in g}
    return core_num, labels, k_max


def write_node_report(
    path: Path,
    g: nx.Graph,
    core_num: dict[str, int],
    labels: dict[str, str],
    k_max: int,
) -> None:
    deg = dict(g.degree())
    bc = nx.betweenness_centrality(g, normalized=True) if g.number_of_nodes() < 800 else {}
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ip",
                "degree",
                "core_number",
                "core_vs_periphery",
                "max_k_core",
                "betweenness_centrality",
                "snapshot_count",
            ]
        )
        for n in sorted(g.nodes()):
            w.writerow(
                [
                    n,
                    deg.get(n, 0),
                    core_num.get(n, 0),
                    labels.get(n, "periphery"),
                    k_max,
                    f"{bc.get(n, float('nan')):.6g}" if bc else "",
                    g.nodes[n].get("snapshot_count", ""),
                ]
            )


def write_graph_stats(
    path: Path,
    g: nx.Graph,
    k_max: int,
    core_num: dict[str, int] | None = None,
    *,
    graph_mode: str = "",
) -> None:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    comps = list(nx.connected_components(g))
    with path.open("w", encoding="utf-8") as f:
        if graph_mode:
            f.write(f"graph_mode\t{graph_mode}\n")
        f.write(f"nodes\t{n}\n")
        f.write(f"edges\t{m}\n")
        f.write(f"connected_components\t{len(comps)}\n")
        f.write(f"largest_component_size\t{max((len(c) for c in comps), default=0)}\n")
        f.write(f"max_k_core\t{k_max}\n")
        if n:
            f.write(f"avg_degree\t{2 * m / n:.4f}\n")
            f.write(f"density\t{nx.density(g):.6g}\n")
        if core_num and k_max > 0 and all(core_num.get(node, 0) == k_max for node in g):
            f.write(
                "\n# All nodes lie in the maximum k-core; the binary label is not discriminative.\n"
                "# Use degree, betweenness_centrality, or a sparser input (partial snapshots / crawl edges).\n"
            )


def main(*, allow_large: bool) -> None:
    snaps = load_tronscan_nodemap_snapshot(allow_large=allow_large)
    g = build_cooccurrence_graph(snaps)
    core_num, labels, k_max = analyze_core_periphery(g)
    prefix = OUT_PREFIX
    prefix.parent.mkdir(parents=True, exist_ok=True)
    mode = "full_nodemap" if allow_large else f"small_peer_list_cap_{SMALL_PEER_GRAPH_NODES}"
    write_node_report(prefix.with_name(prefix.name + "_nodes.csv"), g, core_num, labels, k_max)
    write_graph_stats(
        prefix.with_name(prefix.name + "_stats.txt"),
        g,
        k_max,
        core_num,
        graph_mode=mode,
    )
    print(f"Wrote {prefix.name}_nodes.csv and {prefix.name}_stats.txt under {prefix.parent}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TronScan nodemap co-occurrence peer graph.")
    ap.add_argument(
        "--allow-large",
        action="store_true",
        help=f"Use entire nodemap as one snapshot (slow, dense). Default: cap at {SMALL_PEER_GRAPH_NODES} sorted IPs.",
    )
    ns = ap.parse_args()
    main(allow_large=ns.allow_large)
