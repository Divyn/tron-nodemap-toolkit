"""Matplotlib figures for gossip tree and hop expansion."""
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")


def plot_tree(
    path: Path,
    nodes: pd.DataFrame,
    origin_ip: str,
    hop_of: dict[str, int],
    parent_of: dict[str, str],
    link_km: float,
) -> None:
    pos = {
        r["ip"]: (r["longitude"], r["latitude"])
        for _, r in nodes.iterrows()
        if pd.notna(r["longitude"])
    }
    max_hop = max(hop_of.values()) if hop_of else 0
    cmap = plt.get_cmap("plasma")

    fig, ax = plt.subplots(figsize=(13, 10))
    unreach = nodes[nodes["ip"].apply(lambda i: i not in hop_of)]
    ax.scatter(
        unreach["longitude"],
        unreach["latitude"],
        s=4,
        c="#e5e5e5",
        alpha=0.6,
        edgecolors="none",
    )

    for child, par in parent_of.items():
        if child in pos and par in pos:
            x1, y1 = pos[par]
            x2, y2 = pos[child]
            ax.plot(
                [x1, x2],
                [y1, y2],
                "-",
                lw=0.35,
                color=cmap(hop_of[child] / max(max_hop, 1)),
                alpha=0.55,
            )

    for h in range(max_hop + 1):
        layer_ips = [i for i, v in hop_of.items() if v == h]
        xs = [pos[i][0] for i in layer_ips if i in pos]
        ys = [pos[i][1] for i in layer_ips if i in pos]
        ax.scatter(
            xs,
            ys,
            s=220 if h == 0 else 22,
            c=[cmap(h / max(max_hop, 1))],
            edgecolors="black",
            linewidths=1.1 if h == 0 else 0.3,
            marker="*" if h == 0 else "o",
            label=f"hop {h} (n={len(layer_ips)})",
            zorder=5 if h == 0 else 3,
        )

    ax.set_xlim(95, 145)
    ax.set_ylim(15, 50)
    ax.set_title(
        f"Gossip propagation tree (nearest-parent reconstruction)\n"
        f"origin {origin_ip} · link_km={link_km:g} · reachable={len(hop_of)}",
        fontweight="bold",
    )
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.grid(alpha=0.25, linestyle=":")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_regional_map(
    path: Path,
    nodes: pd.DataFrame,
    origin_ip: str,
    hop_of: dict[str, int],
    parent_of: dict[str, str],
    *,
    link_km: float,
    origin_label: str,
    pad_degrees: float = 6.0,
    fig_size: tuple[float, float] = (13, 9),
    dpi: int = 160,
    n_city_labels: int = 12,
) -> None:
    """Regional map of the gossip traversal, auto-zoomed to the reachable component."""
    reach_ips = list(hop_of.keys())
    reach = nodes[nodes["ip"].isin(reach_ips)].copy()
    reach["hop"] = reach["ip"].map(hop_of)
    max_hop = max(hop_of.values()) if hop_of else 0

    lon_min = float(reach["longitude"].min()) - pad_degrees
    lon_max = float(reach["longitude"].max()) + pad_degrees
    lat_min = float(reach["latitude"].min()) - pad_degrees
    lat_max = float(reach["latitude"].max()) + pad_degrees
    lon_min = max(lon_min, -180.0)
    lon_max = min(lon_max, 180.0)
    lat_min = max(lat_min, -85.0)
    lat_max = min(lat_max, 85.0)

    fig, ax = plt.subplots(figsize=fig_size)
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_facecolor("#eaf3fa")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.grid(alpha=0.3, linestyle=":", color="#888")

    in_view = nodes[
        (nodes["longitude"].between(lon_min, lon_max))
        & (nodes["latitude"].between(lat_min, lat_max))
        & (~nodes["ip"].isin(reach_ips))
        & (nodes["ip"] != origin_ip)
    ]
    ax.scatter(
        in_view["longitude"],
        in_view["latitude"],
        s=5,
        c="#bdbdbd",
        alpha=0.5,
        linewidths=0,
        zorder=2,
        label=f"unreachable listeners ({len(in_view)} in view)",
    )

    cmap = plt.get_cmap("plasma")
    ip_to_pos = dict(zip(nodes["ip"], zip(nodes["longitude"], nodes["latitude"])))
    for child, par in parent_of.items():
        if child in ip_to_pos and par in ip_to_pos:
            x1, y1 = ip_to_pos[par]
            x2, y2 = ip_to_pos[child]
            ax.plot(
                [x1, x2],
                [y1, y2],
                "-",
                lw=0.35,
                alpha=0.55,
                color=cmap(hop_of[child] / max(max_hop, 1)),
                zorder=3,
            )

    for h in range(1, max_hop + 1):
        layer = reach[reach["hop"] == h]
        ax.scatter(
            layer["longitude"],
            layer["latitude"],
            s=20,
            c=[cmap(h / max(max_hop, 1))],
            edgecolors="black",
            linewidths=0.25,
            zorder=4,
            label=f"hop {h} ({len(layer)})",
        )

    o_lon, o_lat = ip_to_pos[origin_ip]
    ax.scatter(
        [o_lon],
        [o_lat],
        marker="*",
        s=380,
        c="red",
        edgecolors="black",
        linewidths=1.2,
        zorder=6,
        label=f"tx entry {origin_ip}",
    )

    annotations: list[tuple[float, float, str, dict]] = []
    annotations.append(
        (
            o_lon,
            o_lat,
            origin_label,
            {
                "xytext": (10, 12),
                "color": "darkred",
                "fontweight": "bold",
            },
        )
    )

    city_key = reach["city"].fillna("").str.strip() + ", " + reach["country"].fillna("").str.strip()
    reach_named = reach.assign(_city=city_key)
    reach_named = reach_named[reach_named["_city"].str.strip(", ") != ""]
    top_cities = (
        reach_named.groupby("_city")
        .agg(n=("ip", "size"), lon=("longitude", "mean"), lat=("latitude", "mean"))
        .sort_values("n", ascending=False)
        .head(n_city_labels)
    )
    for name, row in top_cities.iterrows():
        annotations.append(
            (
                float(row["lon"]),
                float(row["lat"]),
                f"{name} ({int(row['n'])})",
                {"xytext": (6, 6), "color": "#111"},
            )
        )

    for x, y, text, kw in annotations:
        ax.annotate(
            text,
            xy=(x, y),
            xycoords="data",
            xytext=kw["xytext"],
            textcoords="offset points",
            fontsize=8.5,
            color=kw.get("color", "#222"),
            fontweight=kw.get("fontweight", "normal"),
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#888", alpha=0.85, lw=0.4),
            arrowprops=dict(arrowstyle="-", lw=0.4, color="#666"),
            zorder=7,
        )

    ax.set_title(
        f"TRON tx gossip traversal from RPC entry point\n"
        f"origin {origin_ip}  ·  link_km={link_km:g}  ·  reachable={len(hop_of)}  ·  hops={max_hop}",
        fontsize=12,
        fontweight="bold",
    )
    ax.legend(loc="lower left", fontsize=8, framealpha=0.92)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def plot_hop_expansion(
    path: Path,
    nodes: pd.DataFrame,
    origin_ip: str,
    hop_of: dict[str, int],
) -> None:
    max_hop = max(hop_of.values()) if hop_of else 0
    cols = 3
    rows = int(np.ceil((max_hop + 1) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 3.2 * rows))
    axes = np.array(axes).reshape(-1)
    geo = nodes.dropna(subset=["latitude", "longitude"])
    o = nodes[nodes["ip"] == origin_ip]

    for h in range(max_hop + 1):
        ax = axes[h]
        ax.scatter(
            geo["longitude"],
            geo["latitude"],
            s=4,
            c="#dcdcdc",
            alpha=0.6,
            edgecolors="none",
        )
        up_to = [ip for ip, v in hop_of.items() if v <= h]
        this = [ip for ip, v in hop_of.items() if v == h]
        up_to_df = geo[geo["ip"].isin(up_to)]
        this_df = geo[geo["ip"].isin(this)]
        ax.scatter(
            up_to_df["longitude"],
            up_to_df["latitude"],
            s=10,
            c="#1f77b4",
            alpha=0.55,
        )
        ax.scatter(
            this_df["longitude"],
            this_df["latitude"],
            s=22,
            c="red",
            edgecolors="black",
            linewidths=0.3,
            label=f"new at hop {h}: {len(this)}",
        )
        if len(o):
            ax.scatter(
                o["longitude"],
                o["latitude"],
                marker="*",
                s=180,
                c="gold",
                edgecolors="black",
                linewidths=0.7,
                zorder=5,
            )
        ax.set_xlim(-180, 180)
        ax.set_ylim(-60, 85)
        ax.set_title(f"Hop {h} — cumulative {len(up_to)}", fontsize=10)
        ax.grid(alpha=0.25, linestyle=":")
        ax.legend(loc="lower left", fontsize=7)
        ax.set_xticks([])
        ax.set_yticks([])
    for j in range(max_hop + 1, len(axes)):
        axes[j].axis("off")

    origin_loc = ""
    if len(o):
        origin_loc = f" ({o.iloc[0]['city']}, {o.iloc[0]['country']})"
    fig.suptitle(
        f"Gossip wave expansion from {origin_ip}{origin_loc}",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
