"""Smoke test: strict output-format check (the rules' "Your forecast") on the practice outputs and on synthetic
final-shaped cases (GTA VI's id, minute-level history, streams/categories present, edge cases).

usage: python3 tools/smoke.py <kit input dir>
"""
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "..", "main.py")
sys.path.insert(0, os.path.join(HERE, ".."))
import main  # noqa: E402


def check_out(path):
    raw = open(path, "rb").read()
    assert len(raw) <= 65536 and not os.path.islink(path)
    d = json.loads(raw.decode("utf-8"))
    assert list(d.keys()) == ["hours"] and len(d["hours"]) == 23
    assert sorted(r["hour"] for r in d["hours"]) == list(range(2, 25))
    for r in d["hours"]:
        assert set(r.keys()) == {"hour", "q"} and len(r["q"]) == 5
        prev = 0
        for x in r["q"]:
            assert isinstance(x, (int, float)) and math.isfinite(x) and 0 < x <= 1e9 and x >= prev
            prev = x
    return d


def synth_final(base, h1_scale, minute_history=True, drop_history=False, zero=False):
    c = copy.deepcopy(base)
    c["id"] = "h00"
    c["game"] = {"name": "Grand Theft Auto VI", "twitch_id": main.GTA6_TWITCH_ID}
    c["notes"] = "Grand Theft Auto VI, PS5 and Xbox Series X|S (no PC), unlocks at midnight local time."
    ds = main.parse_time(c["day_start"])
    hist = []
    hh = []
    for r in c["history_hourly"]:
        t = main.parse_time(r["from"])
        if t < ds - timedelta(hours=48):
            continue
        v = r["viewers"] * h1_scale
        hh.append({"from": r["from"], "viewers": round(v), "channels": r["channels"], "reads": 60})
        if minute_history:
            for m in range(60):
                hist.append({"at": (t + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "viewers": int(v * (1 + 0.01 * math.sin(m))), "channels": r["channels"]})
    c["history"], c["history_hourly"] = (([], []) if drop_history else (hist, hh))
    k = c["known"][0]
    k["viewers"] = 0 if zero else round(k["viewers"] * h1_scale)
    k["reads"] = 60
    c["streams"] = [{"login": "x", "viewers": 1000, "language": "en", "started_at": c["day_start"]}]
    c["categories_hourly"] = [{"from": c["day_start"], "top": [{"name": "Grand Theft Auto VI", "viewers": 1,
                                                               "channels": 1}]}]
    return c


def run_dir(cases):
    tin, tout = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        for c in cases:
            with open(os.path.join(tin, c["id"] + ".in"), "w", encoding="utf-8") as f:
                json.dump(c, f)
        env = dict(os.environ, MAKEFUN_INPUT_DIR=tin, MAKEFUN_OUTPUT_DIR=tout, PYTHONHASHSEED="0")
        subprocess.run([sys.executable, "-P", "-s", MAIN], env=env, check=True)
        return {c["id"]: check_out(os.path.join(tout, c["id"] + ".out")) for c in cases}
    finally:
        shutil.rmtree(tin)
        shutil.rmtree(tout)


def malformed_cases(base):
    """(file id, raw bytes, expected hour-1 the fallback should use or None) for broken or minimal inputs."""
    good = json.dumps(base)
    h1 = base["known"][0]["viewers"]
    minimal = {"id": "m", "known": [{"hour": 1, "viewers": 50000}]}
    junk = copy.deepcopy(base)
    junk["comparables"] = [{"name": "x", "day_start": "not a time", "hourly": [{"from": 3, "viewers": "many"}]}]
    junk["history_hourly"] = junk["history_hourly"] + [{"from": None, "viewers": "?"}]
    junk["comparables"] = base["comparables"] + junk["comparables"]  # good analogs plus one broken one
    bad_known = copy.deepcopy(base)
    bad_known["known"] = [{"hour": 1, "viewers": "abc"}]
    nan_known = copy.deepcopy(base)
    nan_known["known"][0]["viewers"] = float("nan")  # json.dumps writes NaN, which Python's json reads back
    return [
        ("a_empty", b"", 1.0),
        ("b_not_json", b"this is not json {", 1.0),
        ("c_truncated", good[: len(good) // 3].encode(), None),
        ("d_array", b"[]", 1.0),
        ("e_minimal", json.dumps(minimal).encode(), None),
        ("f_junk_rows", json.dumps(junk).encode(), None),
        ("g_bad_known", json.dumps(bad_known).encode(), None),
        ("h_bad_utf8", b'{"known": [{"hour": 1, "viewers": 7000}], \xff\xfe}', 7000.0),
        ("i_nan", json.dumps(nan_known).encode(), None),
        ("z_good", good.encode(), None),
    ]


def run_raw(items):
    tin, tout = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        for cid, raw, _ in items:
            with open(os.path.join(tin, cid + ".in"), "wb") as f:
                f.write(raw)
        env = dict(os.environ, MAKEFUN_INPUT_DIR=tin, MAKEFUN_OUTPUT_DIR=tout, PYTHONHASHSEED="0")
        subprocess.run([sys.executable, "-P", "-s", MAIN], env=env, check=True)
        return {cid: check_out(os.path.join(tout, cid + ".out")) for cid, _, _ in items}
    finally:
        shutil.rmtree(tin)
        shutil.rmtree(tout)


def run():
    kit = sys.argv[1]
    practice = []
    for n in sorted(os.listdir(kit)):
        if n.endswith(".in"):
            with open(os.path.join(kit, n), encoding="utf-8") as f:
                practice.append(json.load(f))
    outs = run_dir(practice)
    print("practice outputs valid:", sorted(outs))
    base = practice[2]  # a rolling-midnight console launch as the template
    for label, kw in (("GTA-sized h1 x8 (2.2M), minute history", dict(h1_scale=8.0)),
                      ("h1 x3, hourly history only", dict(h1_scale=3.0, minute_history=False)),
                      ("no history at all", dict(h1_scale=5.0, drop_history=True)),
                      ("hour-1 print 0", dict(h1_scale=1.0, zero=True))):
        c = synth_final(base, **kw)
        d = run_dir([c])["h00"]
        h1 = max(c["known"][0]["viewers"], 1)
        row = {r["hour"]: r["q"] for r in d["hours"]}
        print("%-40s ok  median ratio h2 %.2f h6 %.2f h12 %.2f h20 %.2f h24 %.2f | 90%% band h20 %.2f-%.2f" % (
            label, row[2][2] / h1, row[6][2] / h1, row[12][2] / h1, row[20][2] / h1, row[24][2] / h1,
            row[20][0] / h1, row[20][4] / h1))
    items = malformed_cases(base)
    outs = run_raw(items)
    for cid, raw, want_h1 in items:
        med2 = {r["hour"]: r["q"] for r in outs[cid]["hours"]}[2][2]
        if want_h1 is not None:  # baseline fallback: the hour-2 median is the hour-1 print itself
            assert abs(med2 - want_h1) < 0.01, (cid, med2, want_h1)
        print("malformed %-12s -> valid forecast (hour-2 median %.2f)" % (cid, med2))
    good = run_dir([base])[base["id"]]
    assert outs["z_good"] == good, "a good case after bad ones must forecast exactly as on its own"
    print("good case after the malformed ones: identical to its own run")


if __name__ == "__main__":
    run()
