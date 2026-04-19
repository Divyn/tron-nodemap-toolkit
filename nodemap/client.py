"""HTTP client for TronScan nodemap API."""
from __future__ import annotations

import json
import urllib.request
from typing import Any

URL = "https://apilist.tronscan.org/api/nodemap"


def fetch_nodemap_rows(*, timeout: int = 30) -> list[dict[str, Any]]:
    """
    GET TronScan nodemap JSON and return one dict per node:
    ip, city, country, latitude, longitude.

    Raises urllib.error.URLError on network failure. Returns [] only if the API
    returns an empty list (unexpected format raises ValueError).
    """
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())

    if isinstance(data, dict) and "data" in data:
        nodes = data["data"]
    elif isinstance(data, list):
        nodes = data
    else:
        raise ValueError(
            "Unexpected nodemap response format. Keys: "
            f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
        )

    rows: list[dict[str, Any]] = []
    for node in nodes:
        ip = node.get("ip", node.get("host", node.get("address", "unknown")))
        rows.append(
            {
                "ip": ip,
                "city": node.get("city", ""),
                "country": node.get("country", ""),
                "latitude": node.get("lat", node.get("latitude", "")),
                "longitude": node.get("lng", node.get("longitude", "")),
            }
        )
    return rows
