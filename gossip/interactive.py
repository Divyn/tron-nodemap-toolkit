"""Interactive Plotly (Python) map of the gossip traversal.

Produces a native plotly.graph_objects.Figure. Call .show() to open it in
the user's default browser (Python-driven, no pre-rendered HTML file).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.cm as mpl_cm
import matplotlib.colors as mcolors
import pandas as pd
import plotly.graph_objects as go


def _hex_from_cmap(value: float, cmap_name: str = "plasma") -> str:
    cmap = mpl_cm.get_cmap(cmap_name)
    return mcolors.to_hex(cmap(value))


def plot_interactive_map(
    path: Optional[Path],
    nodes: pd.DataFrame,
    origin_ip: str,
    hop_of: dict[str, int],
    parent_of: dict[str, str],
    parent_km_of: dict[str, float] | None,
    *,
    link_km: float,
    origin_label: str = "",
    show: bool = True,
    show_unreachable_in_view: bool = True,
) -> go.Figure:
    """
    Build a Plotly interactive scattergeo figure of the gossip traversal.

    `path` — optional: if given, pickle the figure object there (`.pkl`), so
             it can be reloaded later with pickle.load. No HTML is written.
    `show` — if True, call fig.show() which opens in default browser.

    Returns the plotly Figure so the caller can inspect / extend it.
    """
    reach_ips = set(hop_of.keys())
    ip_to_row = nodes.set_index("ip").to_dict("index")
    max_hop = max(hop_of.values()) if hop_of else 0

    o_row = ip_to_row[origin_ip]
    o_lat = float(o_row["latitude"])
    o_lon = float(o_row["longitude"])

    reach_df = nodes[nodes["ip"].isin(reach_ips)]
    min_lat = float(min(reach_df["latitude"].min(), o_lat))
    max_lat = float(max(reach_df["latitude"].max(), o_lat))
    min_lon = float(min(reach_df["longitude"].min(), o_lon))
    max_lon = float(max(reach_df["longitude"].max(), o_lon))

    fig = go.Figure()

    # --- parent -> child tree edges (one trace, gap-separated by None) ------
    edge_lon: list[float | None] = []
    edge_lat: list[float | None] = []
    for child, par in parent_of.items():
        c = ip_to_row.get(child)
        p = ip_to_row.get(par)
        if not c or not p:
            continue
        edge_lon.extend([float(p["longitude"]), float(c["longitude"]), None])
        edge_lat.extend([float(p["latitude"]), float(c["latitude"]), None])

    fig.add_trace(
        go.Scattergeo(
            lon=edge_lon,
            lat=edge_lat,
            mode="lines",
            line=dict(width=0.6, color="rgba(120,120,120,0.55)"),
            hoverinfo="skip",
            name="tree edges",
        )
    )

    # --- unreachable listeners (padded view, hidden by default) -------------
    if show_unreachable_in_view:
        pad = 6.0
        view = nodes[
            (nodes["longitude"].between(min_lon - pad, max_lon + pad))
            & (nodes["latitude"].between(min_lat - pad, max_lat + pad))
            & (~nodes["ip"].isin(reach_ips))
            & (nodes["ip"] != origin_ip)
        ]
        if len(view):
            fig.add_trace(
                go.Scattergeo(
                    lon=view["longitude"],
                    lat=view["latitude"],
                    mode="markers",
                    marker=dict(size=4, color="#bdbdbd", opacity=0.55,
                                line=dict(width=0)),
                    name=f"unreachable ({len(view)} in view)",
                    text=[
                        f"{r['ip']}<br>{r.get('city','')}, {r.get('country','')}"
                        f"<br><i>unreachable</i>"
                        for _, r in view.iterrows()
                    ],
                    hovertemplate="%{text}<extra></extra>",
                    visible="legendonly",
                )
            )

    # --- one trace per hop (legend-click toggles the layer) -----------------
    for h in range(1, max_hop + 1):
        ips = [ip for ip, v in hop_of.items() if v == h]
        if not ips:
            continue
        rows = [ip_to_row[i] for i in ips if i in ip_to_row]
        lons = [float(r["longitude"]) for r in rows]
        lats = [float(r["latitude"]) for r in rows]
        hover = []
        for ip, r in zip(ips, rows):
            par = parent_of.get(ip, "")
            km = (parent_km_of or {}).get(ip)
            km_str = f"{km:.1f} km" if km is not None else "-"
            hover.append(
                f"<b>{ip}</b><br>"
                f"{r.get('city','')}, {r.get('country','')}<br>"
                f"hop {h}<br>"
                f"parent: {par}<br>"
                f"distance to parent: {km_str}"
            )
        color = _hex_from_cmap(h / max(max_hop, 1))
        fig.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                mode="markers",
                marker=dict(
                    size=7,
                    color=color,
                    line=dict(width=0.5, color="black"),
                    opacity=0.9,
                ),
                name=f"hop {h} ({len(ips)})",
                text=hover,
                hovertemplate="%{text}<extra></extra>",
            )
        )

    # --- origin (tx entry) --------------------------------------------------
    fig.add_trace(
        go.Scattergeo(
            lon=[o_lon],
            lat=[o_lat],
            mode="markers+text",
            marker=dict(
                size=18, color="red", symbol="star",
                line=dict(width=1.5, color="black"),
            ),
            text=[origin_label or origin_ip],
            textposition="top center",
            textfont=dict(size=12, color="darkred"),
            name=f"tx entry {origin_ip}",
            hovertemplate=(
                f"<b>{origin_ip}</b> (tx entry)<br>"
                f"{origin_label}<br>"
                f"({o_lat:.4f}, {o_lon:.4f})<br>"
                f"reachable: {len(reach_ips)}<br>"
                f"max hops: {max_hop}<br>"
                f"link_km: {link_km:g}<extra></extra>"
            ),
        )
    )

    fig.update_geos(
        projection_type="natural earth",
        showcountries=True, countrycolor="#999", countrywidth=0.4,
        showcoastlines=True, coastlinecolor="#666", coastlinewidth=0.5,
        showland=True, landcolor="#f5f5f2",
        showocean=True, oceancolor="#eaf3fa",
        lonaxis=dict(range=[max(-180, min_lon - 6), min(180, max_lon + 6)]),
        lataxis=dict(range=[max(-85, min_lat - 6), min(85, max_lat + 6)]),
    )
    fig.update_layout(
        title=dict(
            text=(
                f"<b>TRON tx gossip traversal</b><br>"
                f"<span style='font-size:12px'>origin {origin_ip} "
                f"({origin_label}) · link_km={link_km:g} · "
                f"reachable={len(reach_ips)} · hops={max_hop}</span>"
            ),
            x=0.02, xanchor="left",
        ),
        legend=dict(
            title="layers (click to toggle)",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#888", borderwidth=0.5,
            x=0.01, y=0.01, xanchor="left", yanchor="bottom",
        ),
        margin=dict(l=10, r=10, t=70, b=10),
        height=780,
    )

    if path is not None:
        import pickle
        with open(path, "wb") as fh:
            pickle.dump(fig, fh)

    if show:
        try:
            fig.show()
        except Exception:
            # headless / no-browser environments — skip silently; caller gets fig
            pass

    return fig
