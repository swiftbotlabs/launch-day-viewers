"""Validation for main.py: the rules' pinball loss, its worked example, and leave-one-out over the comparables.

usage: python3 tools/validate.py <case.in with comparables> ['{"param": value, ...}']
Each comparable launch is cut at the end of hour 1 of its release day, forecast from all the other launches, and
scored on hours 2..24, beside the house baseline (flat at hour 1, spread 0.15*sqrt(h-1)).
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import main  # noqa: E402

LEVELS = main.LEVELS


def pinball(y, q, tau):
    d = math.log(max(y, 1.0)) - math.log(q)
    return 2.0 * max(tau * d, (tau - 1.0) * d)


def score(rows):
    """rows: list of (y, [5 quantiles]). Returns loss, typical miss %, 90% coverage."""
    items, absmed, cov = [], [], 0
    for y, q in rows:
        for tau, qq in zip(LEVELS, q):
            items.append(pinball(y, qq, tau))
        absmed.append(abs(math.log(max(y, 1.0)) - math.log(q[2])))
        cov += 1 if q[0] <= y <= q[4] else 0
    n = len(rows)
    return (sum(items) / len(items), 100.0 * (math.exp(sum(absmed) / n) - 1.0), cov / n)


def check_worked_example():
    q = [600000, 800000, 900000, 1100000, 1500000]
    each = [round(pinball(1000000, x, t), 6) for x, t in zip(q, LEVELS)]
    each += [round(pinball(700000, x, t), 6) for x, t in zip(q, LEVELS)]
    want = [0.051083, 0.111572, 0.105361, 0.047655, 0.040547, 0.015415, 0.200297, 0.251314, 0.225993, 0.076214]
    assert each == want, each
    loss, miss, cov = score([(1000000, q), (700000, q)])
    assert round(loss, 6) == 0.112545 and round(miss, 2) == 19.52 and cov == 1.0, (loss, miss, cov)
    inv = [1200000] * 5
    loss2, _, _ = score([(1000000, inv), (700000, inv)])
    assert round(loss2, 6) == 0.360659, loss2
    return True


def launches(case):
    game_name = case["game"]["name"]
    res = []
    for c in case["comparables"]:
        if not main.is_launch_analog(c, game_name):
            continue
        s = main.series_from_rows(c["hourly"], main.parse_time(c["day_start"]), "from")
        if 0 not in s or sum(1 for h in range(1, 24) if h in s) < 12:
            continue
        res.append((c["name"], s))
    return res


def loo(all_launches, params):
    per = []
    for i, (name, s) in enumerate(all_launches):
        target = {k: v for k, v in s.items() if k <= 0}
        analogs = [a for j, (_, a) in enumerate(all_launches) if j != i]
        q = main.forecast_quantiles(target, analogs, params)
        b = main.baseline_quantiles(s[0][0])
        rows_m, rows_b = [], []
        for h in range(2, 25):
            if (h - 1) in s:
                y = s[h - 1][0]
                rows_m.append((y, main.clean_row(q[h])))
                rows_b.append((y, main.clean_row(b[h])))
        per.append((name, s[0][0], rows_m, rows_b))
    return per


def summarize(per, pick=lambda name, h1: True):
    rm, rb = [], []
    for name, h1, a, b in per:
        if pick(name, h1):
            rm += a
            rb += b
    return score(rm), score(rb), len(rm)


def main_cli():
    check_worked_example()
    print("worked example: OK (0.112545, 19.52%, coverage 1; invalid 0.360659)")
    with open(sys.argv[1], encoding="utf-8") as f:
        case = json.load(f)
    params = dict(main.PARAMS)
    if len(sys.argv) > 2:
        params.update(json.loads(sys.argv[2]))
    L = launches(case)
    per = loo(L, params)
    verbose = os.environ.get("VERBOSE")
    if verbose:
        for name, h1, a, b in per:
            m, bb = score(a), score(b)
            print("  %-34s h1=%8d  model %.3f cov %.2f | base %.3f" % (name[:34], h1, m[0], m[2], bb[0]))
    for label, pick in (("all launches", lambda n, h: True), ("live at h1 (h1>=10k)", lambda n, h: h >= 10000),
                        ("big (h1>=100k)", lambda n, h: h >= 100000)):
        m, b, n = summarize(per, pick)
        print("%-22s n_hours=%4d  model loss %.4f miss %5.1f%% cov %.3f | baseline loss %.4f miss %5.1f%% cov %.3f"
              % (label, n, m[0], m[1], m[2], b[0], b[1], b[2]))


if __name__ == "__main__":
    main_cli()
