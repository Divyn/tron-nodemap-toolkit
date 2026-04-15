#!/usr/bin/env python3
"""
Proximity-aware gossip: simulating waves over geo-linked TRON listeners.

TronScan nodemap → edges where great-circle distance <= --link-km between listeners
with coordinates; synchronous gossip rounds (toy — NOT TRON P2P or measured RTT).

Run from this directory (needs fetch_tron_nodes.py, pip install networkx):

  python peer_graph.py --link-km 800
  python peer_graph.py --link-km 400 --allow-large   # all nodemap IPs; O(n^2)

Writes ./run1_nodes.csv, ./run1_stats.txt, and ./run1_simulation.txt (round-by-round toy gossip).

repo: https://github.com/Divyn/tron-nodemap-toolkit/tree/main
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import deque
from pathlib import Path
from typing import Any

import networkx as nx

OUT_PREFIX = Path("./run1")
SMALL_PEER_GRAPH_NODES = 2000


def _parse_lat_lon(row: dict[str, Any]) -> tuple[float | None, float | None]:
    lat_v, lon_v = row.get("latitude", ""), row.get("longitude", "")
    try:
        lat = float(lat_v)
        lon = float(lon_v)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None, None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(max(0.0, a))))


def region_country_label(row: dict[str, Any]) -> str:
    c = str(row.get("country", "")).strip()
    return c if c else "UNKNOWN_COUNTRY"


def region_grid_label(row: dict[str, Any], *, grid_degrees: float) -> str:
    lat, lon = _parse_lat_lon(row)
    if lat is None:
        return "UNKNOWN_GRID"
    g = max(grid_degrees, 1e-6)
    ilat = int(math.floor(lat / g))
    ilon = int(math.floor(lon / g))
    return f"grid_{g}deg_{ilat}_{ilon}"


def load_capped_nodemap_rows(*, allow_large: bool) -> list[dict[str, Any]]:
    from fetch_tron_nodes import fetch_nodemap_rows

    raw_rows: list[dict[str, Any]] = fetch_nodemap_rows()
    by_ip: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        ip = str(row.get("ip", "")).strip()
        if not ip or ip.lower() == "unknown":
            continue
        if ip not in by_ip:
            by_ip[ip] = row

    ips_sorted = sorted(by_ip.keys())
    total = len(ips_sorted)
    if not allow_large and total > SMALL_PEER_GRAPH_NODES:
        ips_sorted = ips_sorted[:SMALL_PEER_GRAPH_NODES]
        print(
            f"Using {len(ips_sorted)} of {total} nodemap IPs (sorted, cap={SMALL_PEER_GRAPH_NODES}). "
            "Pass --allow-large for the full nodemap.",
            file=sys.stderr,
        )
    elif allow_large and total > SMALL_PEER_GRAPH_NODES:
        print(
            f"Full nodemap: {total} nodes (O(n^2) edge checks).",
            file=sys.stderr,
        )

    return [by_ip[ip] for ip in ips_sorted]


def build_geo_proximity_graph(
    capped_rows: list[dict[str, Any]],
    *,
    link_km: float,
) -> nx.Graph:
    """Undirected graph: edge if both endpoints have valid coords and haversine <= link_km."""
    g = nx.Graph()
    points: list[tuple[str, float, float]] = []
    for row in capped_rows:
        ip = str(row.get("ip", "")).strip()
        lat, lon = _parse_lat_lon(row)
        g.add_node(ip)
        if lat is not None:
            points.append((ip, lat, lon))

    n = len(points)
    for i in range(n):
        ip_i, la_i, lo_i = points[i]
        for j in range(i + 1, n):
            ip_j, la_j, lo_j = points[j]
            d = haversine_km(la_i, lo_i, la_j, lo_j)
            if d <= link_km:
                g.add_edge(ip_i, ip_j, weight_km=d)

    return g


def bfs_hops_from(g: nx.Graph, origin: str) -> dict[str, int]:
    """Shortest-path hop count from origin (unweighted edges = one relay hop)."""
    if origin not in g:
        return {}
    dist: dict[str, int] = {origin: 0}
    q: deque[str] = deque([origin])
    while q:
        u = q.popleft()
        du = dist[u]
        for v in g[u]:
            if v not in dist:
                dist[v] = du + 1
                q.append(v)
    return dist


def propagation_rounds(g: nx.Graph, origin: str) -> list[tuple[int, int, int, frozenset[str]]]:
    """
    Synchronous gossip waves on the geo graph (same as BFS layers).

    Each round, every node that already has the toy tx attempts to pass it to all
    geo-linked neighbors who have not received it yet.

    Returns rows: (round, new_nodes_this_round, cumulative_reached, sample_of_new_ips).
    Round 0: only origin (new=1, cum=1).
    """
    if origin not in g:
        return []

    seen: set[str] = {origin}
    frontier: set[str] = {origin}
    out: list[tuple[int, int, int, frozenset[str]]] = [(0, 1, 1, frozenset({origin}))]
    r = 0
    while frontier:
        r += 1
        nxt: set[str] = set()
        for u in frontier:
            for v in g[u]:
                if v not in seen:
                    nxt.add(v)
        if not nxt:
            break
        seen |= nxt
        frontier = nxt
        sample = frozenset(sorted(nxt)[:8])
        out.append((r, len(nxt), len(seen), sample))
    return out


def resolve_origin_ip(
    capped_rows: list[dict[str, Any]],
    g: nx.Graph,
    *,
    override: str | None,
) -> str | None:
    """Toy injection IP: --origin-ip if valid, else first capped row with valid coords."""
    if override:
        ip = override.strip()
        if ip not in g:
            raise SystemExit(f"--origin-ip {ip!r} not in graph (unknown IP or not in capped set).")
        return ip
    for row in capped_rows:
        lat, lon = _parse_lat_lon(row)
        if lat is not None:
            return str(row.get("ip", "")).strip()
    return None


def component_labels(g: nx.Graph) -> dict[str, int]:
    comps = list(nx.connected_components(g))
    out: dict[str, int] = {}
    for idx, comp in enumerate(comps):
        for node in comp:
            out[node] = idx
    return out


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
    capped_rows: list[dict[str, Any]],
    *,
    grid_degrees: float,
    link_km: float,
    core_num: dict[str, int],
    labels: dict[str, str],
    k_max: int,
    comp_by_ip: dict[str, int],
    hops: dict[str, int],
    origin_ip: str | None,
) -> None:
    grid_key = f"region_grid_{grid_degrees:g}deg"
    deg = dict(g.degree())
    bc = nx.betweenness_centrality(g, normalized=True) if g.number_of_nodes() < 800 else {}
    row_by_ip = {str(r.get("ip", "")).strip(): r for r in capped_rows}

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ip",
                "city",
                "country",
                "latitude",
                "longitude",
                "region_country",
                grid_key,
                "link_km_max",
                "degree",
                "geo_component",
                "sim_hops_from_origin",
                "sim_origin_ip",
                "core_number",
                "core_vs_periphery",
                "max_k_core",
                "betweenness_centrality",
            ]
        )
        for ip in sorted(g.nodes()):
            row = row_by_ip.get(ip, {})
            hop = hops.get(ip, "")
            w.writerow(
                [
                    ip,
                    row.get("city", ""),
                    row.get("country", ""),
                    row.get("latitude", ""),
                    row.get("longitude", ""),
                    region_country_label(row) if row else "UNKNOWN_COUNTRY",
                    region_grid_label(row, grid_degrees=grid_degrees) if row else "UNKNOWN_GRID",
                    link_km,
                    deg.get(ip, 0),
                    comp_by_ip.get(ip, ""),
                    hop if hop != "" else "",
                    origin_ip or "",
                    core_num.get(ip, 0),
                    labels.get(ip, "periphery"),
                    k_max,
                    f"{bc.get(ip, float('nan')):.6g}" if bc else "",
                ]
            )


def write_simulation_report(
    path: Path,
    g: nx.Graph,
    capped_rows: list[dict[str, Any]],
    *,
    link_km: float,
    origin_ip: str | None,
    rounds: list[tuple[int, int, int, frozenset[str]]],
) -> None:
    row_by_ip = {str(r.get("ip", "")).strip(): r for r in capped_rows}
    n_total = g.number_of_nodes()

    def loc(ip: str) -> str:
        r = row_by_ip.get(ip, {})
        city, country = str(r.get("city", "")).strip(), str(r.get("country", "")).strip()
        if city and country:
            return f"{city}, {country}"
        return country or city or "?"

    with path.open("w", encoding="utf-8") as f:
        f.write(
            "# Proximity-aware gossip: simulating waves over geo-linked TRON listeners (toy; NOT TRON P2P).\n"
        )
        f.write(f"# link_km={link_km:g}  edges = haversine <= link_km between listeners with coords.\n")
        f.write(f"# Model: synchronous rounds; each round all informed nodes relay to all geo-neighbors.\n")
        f.write(f"# Origin (injection): {origin_ip or 'none'}\n\n")

        if not rounds or not origin_ip:
            f.write("no_simulation\tno origin with coordinates in capped set, or origin not in graph\n")
            return

        f.write(f"origin_location\t{loc(origin_ip)}\n")
        f.write(f"graph_nodes\t{n_total}\n")
        final_cum = rounds[-1][2]
        f.write(f"reachable_from_origin\t{final_cum}\n")
        f.write(f"unreachable_isolated_or_other_component\t{n_total - final_cum}\n\n")
        f.write("round\tnew_nodes\tcumulative\tpct_graph_reached\tsample_new_ips\n")
        for rnd, new_k, cum, sample in rounds:
            pct = 100.0 * cum / n_total if n_total else 0.0
            sample_s = "; ".join(sample) if sample else ""
            f.write(f"{rnd}\t{new_k}\t{cum}\t{pct:.2f}\t{sample_s}\n")


def print_simulation_table(
    rounds: list[tuple[int, int, int, frozenset[str]]],
    *,
    origin_ip: str | None,
    row_by_ip: dict[str, dict[str, Any]],
    n_graph_nodes: int,
) -> None:
    if not rounds or not origin_ip:
        print("Simulation: no origin.", file=sys.stderr)
        return

    def loc(ip: str) -> str:
        r = row_by_ip.get(ip, {})
        c = str(r.get("country", "")).strip() or "?"
        return c

    print("", file=sys.stderr)
    print(
        f"Proximity-aware gossip (geo links) — origin {origin_ip} ({loc(origin_ip)})",
        file=sys.stderr,
    )
    print("round  new  cumulative  %graph  sample_new_ips", file=sys.stderr)
    for rnd, new_k, cum, sample in rounds:
        pct = 100.0 * cum / n_graph_nodes if n_graph_nodes else 0.0
        sample_s = ", ".join(sample) if sample else ""
        print(f"{rnd:5d}  {new_k:3d}  {cum:10d}  {pct:5.1f}%  {sample_s}", file=sys.stderr)


def write_graph_stats(
    path: Path,
    g: nx.Graph,
    k_max: int,
    core_num: dict[str, int] | None,
    *,
    graph_mode: str,
    link_km: float,
    origin_ip: str | None,
) -> None:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    comps = list(nx.connected_components(g))
    with path.open("w", encoding="utf-8") as f:
        f.write(f"graph_mode\t{graph_mode}\n")
        f.write(f"link_km\t{link_km}\n")
        f.write(f"sim_origin_ip\t{origin_ip or ''}\n")
        f.write(f"nodes\t{n}\n")
        f.write(f"edges\t{m}\n")
        f.write(f"connected_components\t{len(comps)}\n")
        f.write(f"largest_component_size\t{max((len(c) for c in comps), default=0)}\n")
        f.write(f"max_k_core\t{k_max}\n")
        if n:
            f.write(f"avg_degree\t{2 * m / n:.4f}\n")
            f.write(f"density\t{nx.density(g):.6g}\n")
        f.write(
            "\n# Geo proximity graph: edge iff haversine distance <= link_km and both have lat/lon.\n"
            "# sim_hops_from_origin = unweighted shortest path from sim_origin_ip (toy tx propagation).\n"
            "# Not real TRON P2P or mempool routing.\n"
        )


def main(
    *,
    allow_large: bool,
    link_km: float,
    grid_degrees: float,
    origin_ip: str | None,
    print_simulation: bool,
) -> None:
    if link_km <= 0:
        raise SystemExit("--link-km must be positive")

    capped_rows = load_capped_nodemap_rows(allow_large=allow_large)
    g = build_geo_proximity_graph(capped_rows, link_km=link_km)
    core_num, labels, k_max = analyze_core_periphery(g)
    comp_by_ip = component_labels(g)
    origin = resolve_origin_ip(capped_rows, g, override=origin_ip)
    hops = bfs_hops_from(g, origin) if origin else {}
    rounds = propagation_rounds(g, origin) if origin else []

    prefix = OUT_PREFIX
    prefix.parent.mkdir(parents=True, exist_ok=True)
    mode = f"geo_link_{link_km:g}km_" + ("full_nodemap" if allow_large else f"cap_{SMALL_PEER_GRAPH_NODES}")

    row_by_ip = {str(r.get("ip", "")).strip(): r for r in capped_rows}
    write_node_report(
        prefix.with_name(prefix.name + "_nodes.csv"),
        g,
        capped_rows,
        grid_degrees=grid_degrees,
        link_km=link_km,
        core_num=core_num,
        labels=labels,
        k_max=k_max,
        comp_by_ip=comp_by_ip,
        hops=hops,
        origin_ip=origin,
    )
    write_graph_stats(
        prefix.with_name(prefix.name + "_stats.txt"),
        g,
        k_max,
        core_num,
        graph_mode=mode,
        link_km=link_km,
        origin_ip=origin,
    )
    write_simulation_report(
        prefix.with_name(prefix.name + "_simulation.txt"),
        g,
        capped_rows,
        link_km=link_km,
        origin_ip=origin,
        rounds=rounds,
    )
    if print_simulation:
        print_simulation_table(
            rounds,
            origin_ip=origin,
            row_by_ip=row_by_ip,
            n_graph_nodes=g.number_of_nodes(),
        )
    print(
        f"Wrote {prefix.name}_nodes.csv, {prefix.name}_stats.txt, {prefix.name}_simulation.txt "
        f"under {prefix.parent}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=(
            "Proximity-aware gossip: simulating waves over geo-linked TRON listeners (toy model)."
        )
    )
    ap.add_argument(
        "--link-km",
        type=float,
        default=800.0,
        metavar="KM",
        help="Add edge between two listeners if haversine distance <= KM (default: 800).",
    )
    ap.add_argument(
        "--allow-large",
        action="store_true",
        help=f"Use entire nodemap (default: cap at {SMALL_PEER_GRAPH_NODES} sorted IPs).",
    )
    ap.add_argument(
        "--grid-degrees",
        type=float,
        default=1.0,
        metavar="D",
        help="Degrees per cell for region_grid_* column in nodes CSV (default: 1.0).",
    )
    ap.add_argument(
        "--origin-ip",
        type=str,
        default=None,
        metavar="IP",
        help="Toy tx injection node (must appear in capped nodemap). Default: first sorted IP with lat/lon.",
    )
    ap.add_argument(
        "--print-simulation",
        action="store_true",
        help="Print round-by-round gossip table to stderr.",
    )
    ns = ap.parse_args()
    main(
        allow_large=ns.allow_large,
        link_km=ns.link_km,
        grid_degrees=ns.grid_degrees,
        origin_ip=ns.origin_ip,
        print_simulation=ns.print_simulation,
    )
