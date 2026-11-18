"""Step-wise unlock test: a final-shaped GTA VI case whose minute reads step up region by region (New Zealand
11:00Z the day before, eastern Australia 13:00Z, Japan 15:00Z, Europe 23:00Z, UK 00:00Z) up to the 01:00Z cut.
Checks that the momentum this builds into hour 1 does not make the first hours overshoot.

usage: python3 tools/stepwise.py <kit input dir> ['{"param": value}']
"""
import copy
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import main  # noqa: E402

DAY = datetime(2026, 11, 19, tzinfo=timezone.utc)
EVENTS = (("nz", DAY - timedelta(hours=13)), ("au", DAY - timedelta(hours=11)), ("jp", DAY - timedelta(hours=9)),
          ("eu", DAY - timedelta(hours=1)), ("uk", DAY))
SCENARIOS = {  # audience each unlock adds once ramped up (viewers), on top of a ~60k pre-release level
    "early-heavy (NZ draws the world)": {"nz": 1_200_000, "au": 300_000, "jp": 200_000, "eu": 500_000, "uk": 300_000},
    "late-heavy (Europe + UK)": {"nz": 200_000, "au": 100_000, "jp": 100_000, "eu": 800_000, "uk": 1_300_000},
    "all at the UK unlock": {"nz": 10_000, "au": 5_000, "jp": 5_000, "eu": 20_000, "uk": 2_400_000},
}


def viewers_at(t, steps):
    hour = t.hour + t.minute / 60.0
    v = 60_000 * (1.0 + 0.4 * math.cos((hour - 20.0) / 24.0 * 2 * math.pi))  # pre-release, evening peak ~20Z
    for region, at in EVENTS:
        mins = (t - at).total_seconds() / 60.0
        if mins >= 0:
            v += steps[region] * (1.0 - math.exp(-mins / 20.0))  # each unlock ramps up over ~20-40 minutes
    return int(round(v))


def build_case(base, steps):
    c = copy.deepcopy(base)
    c["id"] = "h00"
    c["game"] = {"name": "Grand Theft Auto VI", "twitch_id": main.GTA6_TWITCH_ID}
    c["day_start"] = "2026-11-19T00:00:00Z"
    c["checkpoint"] = "2026-11-19T01:00:00Z"
    c["notes"] = "Grand Theft Auto VI, PS5 and Xbox Series X|S, midnight local time country by country."
    hist, hourly = [], []
    t = DAY - timedelta(hours=48)
    while t < DAY + timedelta(hours=1):
        hist.append({"at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "viewers": viewers_at(t, steps),
                     "channels": max(1, viewers_at(t, steps) // 120)})
        t += timedelta(minutes=1)
    for i in range(0, len(hist), 60):
        block = hist[i:i + 60]
        hourly.append({"from": block[0]["at"], "viewers": int(sum(r["viewers"] for r in block) / 60 + 0.5),
                       "channels": int(sum(r["channels"] for r in block) / 60 + 0.5), "reads": 60})
    h1 = hourly[-1]
    c["history"], c["history_hourly"] = hist, hourly
    c["known"] = [{"hour": 1, "from": "2026-11-19T00:00:00Z", "until": "2026-11-19T01:00:00Z",
                   "viewers": h1["viewers"], "channels": h1["channels"], "reads": 60}]
    return c


def run():
    kit = sys.argv[1]
    if len(sys.argv) > 2:
        main.PARAMS.update(json.loads(sys.argv[2]))
    with open(os.path.join(kit, "p02.in"), encoding="utf-8") as f:
        base = json.load(f)
    for label, steps in SCENARIOS.items():
        case = build_case(base, steps)
        res = main.run_case(case)
        assert main.valid_result(res), label
        t = main.target_series(case)
        f = main.features(t)
        h1 = t[0][0]
        rows = {r["hour"]: r["q"] for r in res["hours"]}
        print("%-34s h0 %.2fM h1 %.2fM | mom %+.2f r6 %+.2f ch %+.2f | median h2-h8: %s | h12 %.2f h20 %.2f"
              " | 90%% h2 %.2f-%.2f" % (
                  label, t[-1][0] / 1e6, h1 / 1e6, f["mom"], f["r6"], f["ch"] if f["ch"] is not None else 0,
                  " ".join("%.2f" % (rows[h][2] / h1) for h in range(2, 9)), rows[12][2] / h1, rows[20][2] / h1,
                  rows[2][0] / h1, rows[2][4] / h1))


if __name__ == "__main__":
    run()
