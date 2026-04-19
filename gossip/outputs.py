"""CSV and text report writers for gossip trace results."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_trace_csv(
    path: Path,
    nodes: pd.DataFrame,
    origin_ip: str,
    hop_of: dict[str, int],
    parent_of: dict[str, str],
    parent_km_of: dict[str, float],
    candidates_of: dict[str, list[tuple[str, float]]],
) -> None:
    row_by_ip = nodes.set_index("ip").to_dict("index")
    children: dict[str, list[str]] = {}
    for child, par in parent_of.items():
        children.setdefault(par, []).append(child)

    rows = []
    for ip, h in sorted(hop_of.items(), key=lambda kv: (kv[1], kv[0])):
        r = row_by_ip.get(ip, {})
        cands = candidates_of.get(ip, [])
        rows.append(
            {
                "ip": ip,
                "hop": h,
                "city": r.get("city", ""),
                "country": r.get("country", ""),
                "lat": r.get("latitude", ""),
                "lon": r.get("longitude", ""),
                "n_informant_candidates": len(cands),
                "informant_candidates": "; ".join(c for c, _ in cands[:8]),
                "nearest_parent_ip": parent_of.get(ip, ""),
                "nearest_parent_km": f"{parent_km_of[ip]:.1f}" if ip in parent_km_of else "",
                "n_children_in_tree": len(children.get(ip, [])),
                "children_sample": "; ".join(sorted(children.get(ip, []))[:8]),
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def write_rounds_txt(
    path: Path,
    origin_ip: str,
    origin_loc: str,
    link_km: float,
    graph_nodes: int,
    rounds: list[dict],
) -> None:
    reachable = rounds[-1]["cumulative"] if rounds else 0
    with path.open("w", encoding="utf-8") as f:
        f.write(
            "# Proximity-aware gossip: synchronous rounds over geo-linked listeners (toy; NOT TRON P2P).\n"
            f"# link_km={link_km:g}  edge iff haversine <= link_km.\n"
            f"# Origin: {origin_ip} ({origin_loc})\n\n"
            f"origin_ip\t{origin_ip}\n"
            f"origin_location\t{origin_loc}\n"
            f"link_km\t{link_km}\n"
            f"graph_nodes\t{graph_nodes}\n"
            f"reachable_from_origin\t{reachable}\n"
            f"unreachable\t{graph_nodes - reachable}\n\n"
            "round\tnew_nodes\tcumulative\tpct_graph_reached\tsample_new_ips\n"
        )
        for row in rounds:
            pct = 100.0 * row["cumulative"] / graph_nodes if graph_nodes else 0.0
            f.write(
                f"{row['round']}\t{row['new_nodes']}\t{row['cumulative']}"
                f"\t{pct:.2f}\t{'; '.join(row['sample_new_ips'])}\n"
            )
