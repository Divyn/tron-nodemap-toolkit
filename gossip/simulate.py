"""Synchronous proximity-aware gossip on a geo graph."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from gossip.geo import haversine_matrix_km


def simulate_gossip(
    nodes: pd.DataFrame,
    origin_ip: str,
    *,
    link_km: float,
) -> tuple[
    dict[str, int],
    dict[str, str],
    dict[str, float],
    dict[str, list[tuple[str, float]]],
    list[dict[str, Any]],
]:
    """
    Run synchronous gossip on the geo graph.

    Returns:
        hop_of           ip -> hop (only for reachable nodes)
        parent_of        ip -> canonical parent ip (nearest hop-(h-1) neighbor)
        parent_km_of     ip -> distance to canonical parent
        candidates_of    ip -> [(parent_ip, distance_km), ...] for all hop-(h-1) neighbors
        rounds           list of {round, new_nodes, cumulative, pct, sample_new_ips}
    """
    geo = nodes.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    ip = geo["ip"].to_numpy()
    lat = geo["latitude"].to_numpy(dtype=float)
    lon = geo["longitude"].to_numpy(dtype=float)
    ip_to_idx = {v: i for i, v in enumerate(ip)}
    if origin_ip not in ip_to_idx:
        raise SystemExit(f"origin_ip {origin_ip!r} is not in the input with coords")

    D = haversine_matrix_km(lat, lon)
    adj = D <= link_km
    np.fill_diagonal(adj, False)

    n = len(ip)
    hop = np.full(n, -1, dtype=int)
    parent = np.full(n, -1, dtype=int)
    parent_km = np.full(n, np.nan, dtype=float)
    candidates: dict[int, list[tuple[int, float]]] = {}

    o = ip_to_idx[origin_ip]
    hop[o] = 0
    frontier = np.array([o])
    rounds: list[dict[str, Any]] = [
        {
            "round": 0,
            "new_nodes": 1,
            "cumulative": 1,
            "sample_new_ips": [origin_ip],
        }
    ]
    cum = 1
    r = 0
    while frontier.size:
        r += 1
        reach_mask = adj[frontier].any(axis=0)
        new_mask = reach_mask & (hop == -1)
        new_idx = np.where(new_mask)[0]
        if new_idx.size == 0:
            break
        for j in new_idx:
            cand = frontier[adj[frontier, j]]
            dists = D[cand, j]
            order = np.argsort(dists)
            cand_sorted = cand[order]
            dists_sorted = dists[order]
            candidates[int(j)] = [
                (int(c), float(d)) for c, d in zip(cand_sorted, dists_sorted)
            ]
            parent[j] = int(cand_sorted[0])
            parent_km[j] = float(dists_sorted[0])
            hop[j] = r
        cum += int(new_idx.size)
        rounds.append(
            {
                "round": r,
                "new_nodes": int(new_idx.size),
                "cumulative": cum,
                "sample_new_ips": sorted(ip[new_idx].tolist())[:8],
            }
        )
        frontier = new_idx

    hop_of = {ip[i]: int(hop[i]) for i in range(n) if hop[i] >= 0}
    parent_of = {ip[i]: ip[parent[i]] for i in range(n) if parent[i] >= 0}
    parent_km_of = {ip[i]: float(parent_km[i]) for i in range(n) if parent[i] >= 0}
    candidates_of = {
        ip[i]: [(ip[c], d) for c, d in cands] for i, cands in candidates.items()
    }
    return hop_of, parent_of, parent_km_of, candidates_of, rounds
