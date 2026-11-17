"""Launch-day Twitch viewer forecast (make.fun gta6-twitch-ccu-forecast-01).

Kernel-weighted analog ensemble over past big launches. For hours 2..24 of the release day it forecasts the
log ratio of the hour's viewers to hour 1's print, using the comparables' own release days as analogs, weighted by
how much their situation at the end of hour 1 resembles this case's. Standard library only, deterministic.
"""
import json
import math
import os
import re
import sys
from datetime import datetime

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z = (-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722)

PARAMS = {
    "bw_size": 1.0,   # kernel bandwidth on ln(hour-1 viewers)
    "bw_mx": 99.0,     # on ln(h1 / max of the previous 24 h)
    "bw_r6": 1.5,     # on ln(h1 / mean of the previous 6 h)
    "bw_ch": 1.0,     # on ln(h1 channels / max channels from 48 h to 7 h before)
    "k_in": 0.8,      # spread multiplier for the 25/75 quantiles
    "k_out": 1.0,     # spread multiplier for the 5/95 quantiles
    "center": "mean", # weighted mean or weighted median of the analogs' log ratios
    "shrink": 1.0,    # multiplies the centre (1 = no shrink toward flat)
    "kind_match": 5.0,  # weight factor for analogs whose unlock type matches the case's
    "kind_mismatch": 0.05,  # weight factor when both types are known and differ (unknown type: factor 1)
    "floor": 0.15,    # minimum log spread at hour 2
    "floor_slope": 0.0,  # extra floor per hour ahead
}


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hour_offset(t, day_start):
    return int((t - day_start).total_seconds() // 3600)


def clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def series_from_rows(rows, day_start, time_key):
    """offset hour -> (viewers, channels or None); several rows in one hour are averaged."""
    acc = {}
    for r in rows:
        v = r.get("viewers")
        if v is None:
            continue
        k = hour_offset(parse_time(r[time_key]), day_start)
        a = acc.setdefault(k, [0.0, 0, 0.0, 0])
        a[0] += float(v)
        a[1] += 1
        c = r.get("channels")
        if c is not None:
            a[2] += float(c)
            a[3] += 1
    return {k: (a[0] / a[1], (a[2] / a[3]) if a[3] else None) for k, a in acc.items()}


def features(s):
    """Features of a series at the end of hour 1 (offset 0); uses offsets <= 0 only."""
    h1 = max(s[0][0], 1.0)
    prev24 = [s[k][0] for k in range(-24, 0) if k in s]
    prev6 = [s[k][0] for k in range(-6, 0) if k in s]
    mx = clip(math.log(h1 / max(max(prev24), 1.0)), -3.0, 1.5) if prev24 else 0.0
    r6 = clip(math.log(h1 / max(sum(prev6) / len(prev6), 1.0)), -3.0, 3.0) if prev6 else 0.0
    ch = None
    c1 = s[0][1]
    old = [s[k][1] for k in range(-48, -6) if k in s and s[k][1] is not None]
    if c1 is not None and old:
        ch = clip(math.log(max(c1, 1.0) / max(max(old), 1.0)), -2.0, 5.0)
    return {"size": math.log(h1), "mx": mx, "r6": r6, "ch": ch}


def analog_targets(s):
    """ln(viewers at hour h / hour-1 viewers) for h = 2..24 where the analog has a point."""
    h1 = max(s[0][0], 1.0)
    return {h: math.log(max(s[h - 1][0], 1.0) / h1) for h in range(2, 25) if (h - 1) in s}


def unlock_kind(text):
    """Coarse unlock type from a free-text unlock note: 'early', 'simul', 'rolling' or None (unknown)."""
    t = (text or "").lower()
    if "early access" in t and "no early access" not in t:
        return "early"
    if "simultaneous" in t or "single global" in t or "single simultaneous" in t:
        if "midnight local" not in t:
            return "simul"
    if "midnight local" in t or "rolling" in t:
        # consoles rolling but PC/Steam on its own single unlock: a different shape (a global surge at one hour)
        if re.search(r"\b(pc|steam)\b[^.;]{0,20}(unlock|simultaneous|global|single)", t):
            return "mixed"
        return "rolling"
    return None


def weight(fa, fb, p):
    d2 = ((fa["size"] - fb["size"]) / p["bw_size"]) ** 2
    d2 += ((fa["mx"] - fb["mx"]) / p["bw_mx"]) ** 2
    d2 += ((fa["r6"] - fb["r6"]) / p["bw_r6"]) ** 2
    if fa["ch"] is not None and fb["ch"] is not None:
        d2 += ((fa["ch"] - fb["ch"]) / p["bw_ch"]) ** 2
    w = math.exp(-0.5 * d2)
    ka, kb = fa.get("kind"), fb.get("kind")
    if ka is not None and kb is not None:
        w *= p["kind_match"] if ka == kb else p["kind_mismatch"]
    return w


def weighted_median(pts):
    pts = sorted(pts, key=lambda t: t[1])
    half = sum(w for w, _ in pts) / 2.0
    acc = 0.0
    for w, y in pts:
        acc += w
        if acc >= half:
            return y
    return pts[-1][1]


def forecast_quantiles(target, analogs, p=PARAMS, target_kind=None, analog_kinds=None):
    """target: series with offsets <= 0; analogs: list of full series. Returns {h: [5 quantiles]}."""
    ft = features(target)
    ft["kind"] = target_kind
    h1 = max(target[0][0], 1.0)
    prepared = []
    for i, a in enumerate(analogs):
        fa = features(a)
        fa["kind"] = analog_kinds[i] if analog_kinds else None
        prepared.append((weight(ft, fa, p), analog_targets(a)))
    out = {}
    for h in range(2, 25):
        pts = [(w, y[h]) for w, y in prepared if h in y and w > 0]
        sw = sum(w for w, _ in pts)
        if sw <= 1e-300:
            mu, var, neff = 0.0, 0.0, 1.0
        else:
            mean = sum(w * y for w, y in pts) / sw
            var = sum(w * (y - mean) ** 2 for w, y in pts) / sw
            neff = sw * sw / sum(w * w for w, _ in pts)
            mu = weighted_median(pts) if p["center"] == "median" else mean
            mu = p["shrink"] * mu  # pull toward flat (ratio 1) when analogs are few or noisy
        floor = p["floor"] + p["floor_slope"] * (h - 2)
        s = math.sqrt(var * (1.0 + 1.0 / neff) + floor * floor)
        ks = (p["k_out"], p["k_in"], 0.0, p["k_in"], p["k_out"])
        out[h] = [h1 * math.exp(mu + s * z * k) for z, k in zip(Z, ks)]
    return out


def is_launch_analog(c, game_name):
    if c.get("name") == game_name or "before release" in (c.get("name") or ""):
        return False
    return True


def load_analogs(case):
    """Returns (series list, unlock kinds list) of the comparables usable as release-day analogs."""
    game_name = (case.get("game") or {}).get("name")
    res, kinds = [], []
    for c in case.get("comparables") or []:
        if not is_launch_analog(c, game_name):
            continue
        s = series_from_rows(c.get("hourly") or [], parse_time(c["day_start"]), "from")
        if 0 not in s or sum(1 for h in range(1, 24) if h in s) < 12:
            continue
        res.append(s)
        kinds.append(unlock_kind(c.get("unlock")))
    return res, kinds


def case_kind(case):
    """The case's own unlock type: from its notes, else from its own pre-release category's note."""
    k = unlock_kind(case.get("notes"))
    if k is None:
        game_name = (case.get("game") or {}).get("name")
        for c in case.get("comparables") or []:
            if not is_launch_analog(c, game_name):
                text = (c.get("unlock") or "").lower()
                if "rolling" in text or "midnight local" in text:
                    k = "rolling"
    return k


def target_series(case):
    ds = parse_time(case["day_start"])
    rows = case.get("history_hourly")
    if rows:
        s = series_from_rows(rows, ds, "from")
    else:
        s = series_from_rows(case.get("history") or [], ds, "at")
    s = {k: v for k, v in s.items() if k < 0}
    k1 = case["known"][0]
    s[0] = (max(float(k1["viewers"]), 1.0), k1.get("channels"))
    return s


def clean_row(q):
    out = []
    prev = 0.0
    for x in q:
        if not math.isfinite(x):
            x = prev if prev > 0 else 1.0
        x = round(clip(x, 0.01, 1e9), 2)
        if x < prev:
            x = prev
        out.append(x)
        prev = x
    return out


def baseline_quantiles(h1):
    h1 = max(h1, 1.0)
    return {h: [h1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z] for h in range(2, 25)}


def run_case(case):
    try:
        analogs, kinds = load_analogs(case)
        q = forecast_quantiles(target_series(case), analogs, PARAMS, case_kind(case), kinds)
    except Exception:  # never leave a case invalid: fall back to the flat forecast
        q = baseline_quantiles(float(case["known"][0]["viewers"]))
    return {"hours": [{"hour": h, "q": clean_row(q[h])} for h in range(2, 25)]}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for n in names:
        with open(os.path.join(in_dir, n), encoding="utf-8") as f:
            case = json.load(f)
        res = run_case(case)
        with open(os.path.join(out_dir, n[:-3] + ".out"), "w", encoding="utf-8") as f:
            json.dump(res, f, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
