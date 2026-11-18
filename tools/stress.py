"""Stress test: a record hour 1 (2 to 5 million viewers) under several pre-release histories.

usage: python3 tools/stress.py <kit input dir>
Builds GTA VI-shaped cases (the rules' id, notes, rolling unlock) from a practice launch's own history, rescaled or
replaced, runs them through main.run_case, checks every output and prints the median ratios, 90% bands, the
effective number of analogs and the heaviest ones.
"""
import copy
import json
import math
import os
import sys
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import main  # noqa: E402

sys.path.insert(0, HERE)
from smoke import synth_final  # noqa: E402


def with_history(base, h1, pre):
    """GTA VI case whose hourly history for the 48 h before is pre(k) viewers at offset k (k = -48..-1)."""
    c = synth_final(base, 1.0, minute_history=False)
    ds = main.parse_time(c["day_start"])
    c["history_hourly"] = [{"from": (ds + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "viewers": round(pre(k)), "channels": max(1, round(pre(k) / 150)), "reads": 60}
                           for k in range(-48, 0)]
    c["history"] = []
    c["known"][0]["viewers"] = h1
    c["known"][0]["channels"] = round(h1 / 150)
    return c


def analog_weights(case):
    t = main.target_series(case)
    analogs, kinds, days = main.load_analogs(case)
    day = main.parse_time(case["day_start"]).date()
    if main.PARAMS.get("dst_align") and main.PARAMS.get("dst_mode") == "full":  # other modes keep the weights
        moved = [{o + main.dst_shift(day, d): v for o, v in a.items()} for a, d in zip(analogs, days)]
        analogs = moved
    names = []
    for cc in case["comparables"]:
        if not main.is_launch_analog(cc, case["game"]["name"]):
            continue
        s = main.series_from_rows(cc["hourly"], main.parse_time(cc["day_start"]), "from")
        if 0 in s and sum(1 for h in range(1, 24) if h in s) >= 12:
            names.append(cc["name"])
    ft = main.features(t)
    ft["kind"] = main.case_kind(case)
    feats = [main.features(a) for a in analogs]
    ft["size"] = min(ft["size"], max(f["size"] for f in feats))
    ws = []
    for f, k, n in zip(feats, kinds, names):
        f["kind"] = k
        ws.append((main.weight(ft, f, main.PARAMS), n))
    tot = sum(w for w, _ in ws)
    neff = tot * tot / sum(w * w for w, _ in ws)
    top = sorted(ws, reverse=True)[:4]
    return neff, ", ".join("%s %.0f%%" % (n[:14], 100 * w / tot) for w, n in top)


def run():
    kit = sys.argv[1]
    with open(os.path.join(kit, "p02.in"), encoding="utf-8") as f:
        base = json.load(f)
    ds = main.parse_time(base["day_start"])
    shape = {}
    for r in base["history_hourly"]:
        shape[int((main.parse_time(r["from"]) - ds).total_seconds() // 3600)] = r["viewers"]
    h1_base = base["known"][0]["viewers"]
    scenarios = []
    for h1 in (2_000_000, 3_500_000, 5_000_000):
        sc = h1 / h1_base
        scenarios.append(("h1 %.1fM, real ramp shape x%.1f" % (h1 / 1e6, sc),
                          with_history(base, h1, lambda k, sc=sc: shape.get(k, shape[-1]) * sc)))
    scenarios.append(("h1 5M, flat 100k before (sudden jump)", with_history(base, 5_000_000, lambda k: 100_000)))
    scenarios.append(("h1 5M, hour 0 at 6M (fading into h1)",
                      with_history(base, 5_000_000, lambda k: 6_000_000 if k == -1 else 2_000_000 + 40_000 * k)))
    scenarios.append(("h1 5M, no history at all", synth_final(base, 5_000_000 / h1_base, drop_history=True)))
    for label, case in scenarios:
        res = main.run_case(case)
        assert main.valid_result(res), label
        h1 = case["known"][0]["viewers"]
        rows = {r["hour"]: r["q"] for r in res["hours"]}
        widths = [math.log(rows[h][4] / rows[h][0]) for h in range(2, 25)]
        neff, top = analog_weights(case)
        print("%-40s med h2 %.2f h6 %.2f h12 %.2f h20 %.2f h24 %.2f | 90%% h20 %.2f-%.2f | log-width %.2f-%.2f"
              " | max q95 %.2fM | n_eff %.1f: %s" % (
                  label, rows[2][2] / h1, rows[6][2] / h1, rows[12][2] / h1, rows[20][2] / h1, rows[24][2] / h1,
                  rows[20][0] / h1, rows[20][4] / h1, min(widths), max(widths),
                  max(rows[h][4] for h in rows) / 1e6, neff, top))


if __name__ == "__main__" and not (len(sys.argv) > 2 and sys.argv[2] == "sizes"):
    run()


def size_table(kit, sizes=(3_000_000, 4_000_000, 5_000_000, 6_000_000)):
    """Record hour 1 at 3-6 million (above every analog): absolute medians and 5-95% bands at hours 2/6/12/24, and a
    check that no size clamp caps the median (each quantile / hour 1 must be the same at every size)."""
    with open(os.path.join(kit, "p02.in"), encoding="utf-8") as f:
        base = json.load(f)
    ds = main.parse_time(base["day_start"])
    shape = {int((main.parse_time(r["from"]) - ds).total_seconds() // 3600): r["viewers"]
             for r in base["history_hourly"]}
    h1_base = base["known"][0]["viewers"]
    ratios = []
    for h1 in sizes:
        sc = h1 / h1_base
        case = with_history(base, h1, lambda k, sc=sc: shape.get(k, shape[-1]) * sc)
        res = main.run_case(case)
        assert main.valid_result(res)
        rows = {r["hour"]: r["q"] for r in res["hours"]}
        ratios.append([round(rows[h][i] / h1, 4) for h in (2, 6, 12, 24) for i in (0, 2, 4)])
        print("h1 %.0fM: " % (h1 / 1e6) + " | ".join(
            "h%d median %.2fM (5-95%% %.2f-%.2fM)" % (h, rows[h][2] / 1e6, rows[h][0] / 1e6, rows[h][4] / 1e6)
            for h in (2, 6, 12, 24)))
    same = all(r == ratios[0] for r in ratios)
    print("quantile / hour-1 ratios identical at every size (median scales with hour 1, not capped): %s" % same)
    return same


if __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[2] == "sizes":
    size_table(sys.argv[1])
