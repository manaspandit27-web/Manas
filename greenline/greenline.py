#!/usr/bin/env python3
"""Next Green Line C trains at Washington Square (to Government Center) and
St. Mary's Street (to Cleveland Circle). Standard library only.

    MBTA_API_KEY=... ./greenline.py          # print once
    MBTA_API_KEY=... ./greenline.py --watch  # refresh every 30s
    ./greenline.py --line                    # one line, for a status bar
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api-v3.mbta.com"
ROUTE = "Green-C"
WATCHES = [
    # label, parent station, destination to match, fallback direction_id
    ("Wash Sq → Gov Ctr", "place-wascm", "Government Center", 1),
    ("St Mary's → Clev Cir", "place-smary", "Cleveland Circle", 0),
]


def get(path, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"accept": "application/vnd.api+json"})
    key = os.environ.get("MBTA_API_KEY", "").strip()
    if key:
        req.add_header("x-api-key", key)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        hint = {403: " (check MBTA_API_KEY)", 429: " (rate limited)"}.get(e.code, "")
        raise SystemExit(f"MBTA API {e.code}{hint}")


def rel(resource, name):
    data = (resource.get("relationships") or {}).get(name, {}).get("data")
    return data["id"] if data else None


def load_layout():
    try:
        destinations = get(f"/routes/{ROUTE}")["data"]["attributes"]["direction_destinations"]
    except Exception:
        destinations = []
    directions = []
    for _, _, towards, fallback in WATCHES:
        match = [i for i, d in enumerate(destinations) if towards.lower() in d.lower()]
        directions.append(match[0] if match else fallback)
    order, names = {}, {}
    for d in set(directions):
        stops = get("/stops", {"filter[route]": ROUTE, "filter[direction_id]": d})["data"]
        order[d] = [s["id"] for s in stops]
        names.update({s["id"]: s["attributes"]["name"] for s in stops})
    return directions, order, names


def positions():
    doc = get("/vehicles", {"filter[route]": ROUTE, "include": "stop"})
    parents = {s["id"]: rel(s, "parent_station") or s["id"] for s in doc.get("included", []) if s["type"] == "stop"}
    out = {}
    for v in doc["data"]:
        stop = rel(v, "stop")
        if stop:
            out[v["id"]] = (parents.get(stop, stop), v["attributes"].get("current_status") or "")
    return out


def boards(layout):
    directions, order, names = layout
    where_now = positions()
    now = datetime.now(timezone.utc)
    result = []
    for (label, stop, _, _), d in zip(WATCHES, directions):
        doc = get("/predictions", {"filter[stop]": stop, "filter[route]": ROUTE, "filter[direction_id]": d})
        line = order.get(d, [])
        target = line.index(stop) if stop in line else -1
        arrivals = []
        for p in doc["data"]:
            a = p["attributes"]
            t = a.get("arrival_time") or a.get("departure_time")
            if not t:
                continue
            minutes = round((datetime.fromisoformat(t) - now).total_seconds() / 60)
            if minutes < 0:
                continue
            arrival = {"minutes": minutes, "status": a.get("status")}
            pos = where_now.get(rel(p, "vehicle"))
            if pos and pos[0] in line and target >= 0 and line.index(pos[0]) <= target:
                arrival["stops"] = target - line.index(pos[0])
                name = names.get(pos[0], pos[0])
                arrival["where"] = f"at {name}" if pos[1] == "STOPPED_AT" else f"→ {name}"
            arrivals.append(arrival)
        result.append((label, sorted(arrivals, key=lambda x: x["minutes"])))
    return result


def one_line(bs):
    parts = []
    for label, arrivals in bs:
        if not arrivals:
            parts.append(f"{label}: none")
            continue
        first = arrivals[0]
        text = f"{label} {'now' if first['minutes'] == 0 else str(first['minutes']) + 'm'}"
        if "stops" in first:
            s = first["stops"]
            text += " (arriving)" if s == 0 else f" ({s} stop{'' if s == 1 else 's'})"
        if len(arrivals) > 1:
            text += f", {arrivals[1]['minutes']}m"
        parts.append(text)
    return "🚋 " + " · ".join(parts)


def detail(bs):
    out = []
    for label, arrivals in bs:
        out.append(f"{label} (Green Line C)")
        if not arrivals:
            out.append("  no trains predicted")
        for a in arrivals[:3]:
            bits = ["now" if a["minutes"] == 0 else f"{a['minutes']} min"]
            if "stops" in a:
                bits.append(f"{a['stops']} stop{'' if a['stops'] == 1 else 's'} away")
            if a.get("where"):
                bits.append(a["where"])
            if a.get("status"):
                bits.append(a["status"])
            out.append("  " + " · ".join(bits))
        out.append("")
    return "\n".join(out).rstrip()


def main():
    args = sys.argv[1:]
    layout = load_layout()
    if "--watch" in args:
        while True:
            print("\033[2J\033[H" + detail(boards(layout)) + f"\n\nupdated {time.strftime('%-I:%M:%S %p')}", flush=True)
            time.sleep(30)
    bs = boards(layout)
    print(one_line(bs) if "--line" in args else detail(bs))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
