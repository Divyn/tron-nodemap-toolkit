"""Proximity-aware gossip simulation and trace outputs."""

from gossip.geo import haversine_matrix_km
from gossip.interactive import plot_interactive_map
from gossip.outputs import write_rounds_txt, write_trace_csv
from gossip.plots import plot_hop_expansion, plot_regional_map, plot_tree
from gossip.simulate import simulate_gossip

__all__ = [
    "haversine_matrix_km",
    "simulate_gossip",
    "write_trace_csv",
    "write_rounds_txt",
    "plot_tree",
    "plot_hop_expansion",
    "plot_regional_map",
    "plot_interactive_map",
]
