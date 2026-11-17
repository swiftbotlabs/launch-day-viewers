"""Nested leave-one-out: an honest estimate of the whole procedure, tuning included.

usage: python3 tools/nested.py <case.in>
For each launch: tune the parameters (tools/tune.py's search, started from the house-neutral v1 defaults) on the
other launches only, then forecast the held-out launch with those parameters and the other launches as analogs.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tune  # noqa: E402
import validate  # noqa: E402

V1 = {"bw_size": 1.0, "bw_mx": 0.5, "bw_r6": 0.6, "bw_ch": 1.5, "k_in": 1.0, "k_out": 1.0, "center": "mean",
      "shrink": 1.0, "kind_match": 1.0, "kind_mismatch": 1.0, "floor": 0.10, "floor_slope": 0.01}


def run():
    with open(sys.argv[1], encoding="utf-8") as f:
        case = json.load(f)
    L = validate.launches(case)
    kinds = {n: k for n, _, k in L}
    per = []
    for i, (name, s, kind) in enumerate(L):
        rest = [x for j, x in enumerate(L) if j != i]
        params, _ = tune.tune(rest, "mix", V1, sweeps=2, log=lambda *a: None)
        target = {k: v for k, v in s.items() if k <= 0}
        q = validate.main.forecast_quantiles(target, [x[1] for x in rest], params, kind, [x[2] for x in rest])
        b = validate.main.baseline_quantiles(s[0][0])
        rm, rb = [], []
        for h in range(2, 25):
            if (h - 1) in s:
                rm.append((s[h - 1][0], validate.main.clean_row(q[h])))
                rb.append((s[h - 1][0], validate.main.clean_row(b[h])))
        per.append((name, s[0][0], rm, rb))
        print("%-34s km=%-4s mis=%-4s k_in=%-4s k_out=%-4s  model %.3f base %.3f" % (
            name[:34], params["kind_match"], params["kind_mismatch"], params["k_in"], params["k_out"],
            validate.score(rm)[0], validate.score(rb)[0]), flush=True)
    for label, pick in (("all launches", lambda n, h: True), ("live at h1 (h1>=10k)", lambda n, h: h >= 10000),
                        ("big (h1>=100k)", lambda n, h: h >= 100000),
                        ("rolling/mixed unlock", lambda n, h: kinds[n] in ("rolling", "mixed"))):
        m, b, n = validate.summarize(per, pick)
        print("NESTED %-22s n_hours=%4d  model loss %.4f miss %5.1f%% cov %.3f | baseline loss %.4f cov %.3f | "
              "below-q %s" % (label, n, m[0], m[1], m[2], b[0], b[2], validate.level_calibration(per, pick)))


if __name__ == "__main__":
    run()
