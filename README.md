# TRON nodemap gossip simulation toolkit

This repo pulls [TronScan nodemap](https://apilist.tronscan.org/api/nodemap) (listener IPs and geolocation) and runs a **toy** “gossip as breadth-first search on a geographic graph” simulation. The nodes are linked if their great-circle distance is at most a fixed threshold; propagation is synchronous BFS from a synthetic RPC entry point.

**Background and motivation:** [Simulating a TRON Transaction's Gossip Trace from Public Listener IPs](https://cryptogrammar.xyz/research/tron-nodes-listener-gossip-simulation/) (cryptogrammar.xyz) explains the model, the haversine graph, hop histograms, and how to interpret the map and trace outputs.

This is a thought experiment on public coordinates only. It does not read real peer tables, instrument nodes, or model production gossip (fanout, NAT, SR topology, etc.).

## Requirements

- Python 3.10+ recommended
- Dependencies: `pandas`, `numpy`, `matplotlib`, `plotly`

Install for example:

```bash
pip install pandas numpy matplotlib plotly
```

## Quick start

1. **Fetch nodemap rows** into `tron_nodes.csv` (generated next to the script; typically not committed):

   ```bash
   python fetch_tron_nodes.py
   ```

   Optional: `python fetch_tron_nodes.py --json-stdout` prints a JSON array to stdout instead of writing CSV.

2. **Run the gossip trace driver** (reads `tron_nodes.csv`, writes trace CSV, rounds text, and an optional Plotly pickle):

   ```bash
   python trace_gossip.py
   ```

   Edit the constants at the top of `trace_gossip.py` (`LINK_KM`, `TEST_ORIGIN`, `OUT_PREFIX`, browser/pickle flags) — there is no CLI for those options.

## Repository layout

| Path                    | Role                                                                           |
| ----------------------- | ------------------------------------------------------------------------------ |
| `fetch_tron_nodes.py`   | CLI entry: fetch nodemap and save `tron_nodes.csv` (or JSON stdout).           |
| `nodemap/client.py`     | HTTP GET to TronScan nodemap; normalizes `ip` / `lat` / `lng` style fields.    |
| `nodemap/cli.py`        | CSV export and console listing used by the fetch script.                       |
| `trace_gossip.py`       | End-to-end driver: append synthetic origin, simulate, write outputs, show map. |
| `gossip/geo.py`         | Pairwise haversine distances (`haversine_matrix_km`).                          |
| `gossip/simulate.py`    | `simulate_gossip` — threshold graph + synchronous BFS.                         |
| `gossip/outputs.py`     | `write_trace_csv`, `write_rounds_txt`.                                         |
| `gossip/interactive.py` | Plotly map of hops and parent edges.                                           |
| `gossip/plots.py`       | Static matplotlib helpers (`plot_tree`, regional maps, etc.).                  |

## Outputs

With default `OUT_PREFIX` in `trace_gossip.py`, a run produces:

- `*_trace.csv` — one row per reached listener with hop, geography, parent, distance, tie candidates.
- `*_rounds.txt` — hop-round summary and parameters.
- `*_map.pkl` — optional pickled Plotly figure (if enabled); the driver may also open the map in a browser.

## Further reading

- [Simulating a TRON Transaction's Gossip Trace from Public Listener IPs](https://cryptogrammar.xyz/research/tron-nodes-listener-gossip-simulation/) — full write-up of the dataset, RGG view, BFS as discrete-time gossip, and how to read the histogram and map.
