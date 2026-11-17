"""Coordinate-descent tuning of main.PARAMS on the leave-one-out loss (one process, coarse grids).

usage: python3 tools/tune.py <case.in> [objective: live|all|big|mix]
The objective defaults to "mix": 0.4 x live-at-h1 loss + 0.2 x big-launch loss + 0.2 x rolling/mixed-unlock loss
+ 0.2 x all-launch loss, so the regime Grand Theft Auto VI is in leads while the odd launches keep the model honest.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

GRID = {
    "bw_size": [0.5, 0.75, 1.0, 1.5, 2.5, 5.0],
    "bw_mx": [0.25, 0.35, 0.5, 0.75, 1.0, 2.0, 99.0],
    "bw_r6": [0.3, 0.45, 0.6, 0.9, 1.5, 99.0],
    "bw_ch": [0.5, 1.0, 1.5, 2.5, 99.0],
    "kind_match": [1.0, 2.0, 3.0, 5.0, 8.0],
    "kind_mismatch": [0.05, 0.1, 0.2, 0.3, 0.5, 1.0],
    "center": ["mean", "median"],
    "shrink": [0.6, 0.8, 0.9, 1.0],
    "mom_beta": [0.0, 0.2, 0.35, 0.5, 0.7],
    "mom_tau": [1.5, 3.0, 5.0, 8.0],
    "floor": [0.0, 0.05, 0.1, 0.15, 0.2],
    "floor_slope": [0.0, 0.005, 0.01, 0.02],
    "k_in": [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25],
    "k_out": [0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4],
}


KIND = {}


def objective(per, which):
    live = validate.summarize(per, lambda n, h: h >= 10000)[0][0]
    big = validate.summarize(per, lambda n, h: h >= 100000)[0][0]
    alll = validate.summarize(per)[0][0]
    roll = validate.summarize(per, lambda n, h: KIND.get(n) in ("rolling", "mixed"))[0][0]
    mix = 0.4 * live + 0.2 * big + 0.2 * alll + 0.2 * roll
    return {"live": live, "big": big, "all": alll, "roll": roll, "mix": mix}[which]


def tune(L, which="mix", start=None, sweeps=3, log=print):
    KIND.update({x[0]: x[2] for x in L})
    params = dict(start or validate.main.PARAMS)
    best = objective(validate.loo(L, params), which)
    log("start %.5f" % best)
    for sweep in range(sweeps):
        improved = False
        for key, values in GRID.items():
            for v in values:
                if v == params[key]:
                    continue
                trial = dict(params, **{key: v})
                o = objective(validate.loo(L, trial), which)
                if o < best - 1e-5:
                    best, params, improved = o, trial, True
            log("sweep %d %-12s -> %-7s %.5f" % (sweep, key, params[key], best))
        if not improved:
            break
    return params, best


def run():
    with open(sys.argv[1], encoding="utf-8") as f:
        case = json.load(f)
    which = sys.argv[2] if len(sys.argv) > 2 else "mix"
    params, _ = tune(validate.launches(case), which)
    print(json.dumps(params, sort_keys=True))


if __name__ == "__main__":
    run()
