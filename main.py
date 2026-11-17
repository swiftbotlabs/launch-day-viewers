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

GTA6_TWITCH_ID = "1867279146"
MIN_ANALOGS = 5  # with fewer usable comparables the flat baseline is the safer forecast
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
    "mom_beta": 0.5,  # momentum carry into the first hours
    "mom_tau": 3.0,   # its decay, in hours
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
        try:  # a malformed row is skipped, never fatal
            v = _positive(r.get("viewers"))
            if v is None:
                continue
            k = hour_offset(parse_time(r[time_key]), day_start)
        except Exception:
            continue
        a = acc.setdefault(k, [0.0, 0, 0.0, 0])
        a[0] += v
        a[1] += 1
        c = _positive(r.get("channels"))
        if c is not None:
            a[2] += c
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
    mom = clip(math.log(h1 / max(s[-1][0], 1.0)), -1.0, 1.0) if -1 in s else None
    return {"size": math.log(h1), "mx": mx, "r6": r6, "ch": ch, "mom": mom}


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
        t = re.sub(r"\b(no|not on|without)\s+(a\s+)?pc\b|\bpc\s+(later|\d{4})", " ", t)
        if re.search(r"\b(pc|steam)\b[^.;()]{0,20}(unlock|simultaneous|global|single)", t):
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
    feats = [features(a) for a in analogs]
    for i, fa in enumerate(feats):
        fa["kind"] = analog_kinds[i] if analog_kinds else None
    if feats and p.get("clamp_size", True):
        # never extrapolate the kernel upward: a case bigger than every analog (GTA VI, likely) is weighted as the
        # largest one, so the group of the largest launches speaks for it rather than the single nearest one.
        # (A lower clamp was tried too: leave-one-out showed it only hurt the smallest launch, so there is none.)
        ft["size"] = min(ft["size"], max(f["size"] for f in feats))
    prepared = [(weight(ft, fa, p), analog_targets(a), fa["mom"]) for fa, a in zip(feats, analogs)]
    # momentum carry: how much faster (or slower) the case moved into hour 1 than its analogs did
    mpts = [(w, m) for w, _, m in prepared if m is not None and w > 0]
    dmom = 0.0
    if ft["mom"] is not None and mpts and sum(w for w, _ in mpts) > 1e-300:
        dmom = ft["mom"] - sum(w * m for w, m in mpts) / sum(w for w, _ in mpts)
    out = {}
    for h in range(2, 25):
        pts = [(w, y[h]) for w, y, _ in prepared if h in y and w > 0]
        sw = sum(w for w, _ in pts)
        if sw <= 1e-300:
            mu, var, neff = 0.0, 0.0, 1.0
        else:
            mean = sum(w * y for w, y in pts) / sw
            var = sum(w * (y - mean) ** 2 for w, y in pts) / sw
            neff = sw * sw / sum(w * w for w, _ in pts)
            mu = weighted_median(pts) if p["center"] == "median" else mean
            mu = p["shrink"] * mu  # pull toward flat (ratio 1) when analogs are few or noisy
        mu += p["mom_beta"] * math.exp(-(h - 2) / p["mom_tau"]) * dmom
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
        try:  # a malformed comparable is skipped, never fatal
            if not is_launch_analog(c, game_name):
                continue
            s = series_from_rows(c.get("hourly") or [], parse_time(c["day_start"]), "from")
        except Exception:
            continue
        if 0 not in s or sum(1 for h in range(1, 24) if h in s) < 12:
            continue
        res.append(s)
        kinds.append(unlock_kind(c.get("unlock")))
    return res, kinds


def case_kind(case):
    """The case's own unlock type: from its notes, else from its own pre-release category's note."""
    if str((case.get("game") or {}).get("twitch_id")) == GTA6_TWITCH_ID:
        return "rolling"  # the rules: PS5/Xbox only, midnight local country by country, no early access
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
    k1 = case["known"][0] if isinstance(case.get("known"), list) and case["known"] else {}
    c1 = _positive(k1.get("channels")) if isinstance(k1, dict) else None
    s[0] = (hour1_print(case), c1)
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


def _positive(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v >= 0 else None


def hour1_print(case, raw=""):
    """Hour 1's print from whatever the case holds (known row, else last history point, else the raw text), else 1."""
    if isinstance(case, dict):
        known = case.get("known")
        if isinstance(known, list):
            for r in known:
                if isinstance(r, dict) and r.get("hour", 1) == 1 and _positive(r.get("viewers")) is not None:
                    return max(_positive(r["viewers"]), 1.0)
        for key in ("history_hourly", "history"):
            rows = case.get(key)
            if isinstance(rows, list):
                for r in reversed(rows):
                    if isinstance(r, dict) and _positive(r.get("viewers")) is not None:
                        return max(_positive(r["viewers"]), 1.0)
    m = re.search(r'"known"\s*:\s*\[\s*\{[^}]*?"viewers"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw or "")
    if m and _positive(m.group(1)) is not None:
        return max(float(m.group(1)), 1.0)
    return 1.0


def baseline_result(h1):
    q = baseline_quantiles(h1)
    return {"hours": [{"hour": h, "q": clean_row(q[h])} for h in range(2, 25)]}


def valid_result(res):
    """The rules' shape: 23 rows, hours 2..24 once each, five finite quantiles in (0, 1e9], non-decreasing."""
    try:
        rows = res["hours"]
        if list(res.keys()) != ["hours"] or len(rows) != 23:
            return False
        if sorted(r["hour"] for r in rows) != list(range(2, 25)):
            return False
        for r in rows:
            q = r["q"]
            if set(r.keys()) != {"hour", "q"} or len(q) != 5:
                return False
            prev = 0.0
            for x in q:
                if not (isinstance(x, (int, float)) and math.isfinite(x) and 0 < x <= 1e9 and x >= prev):
                    return False
                prev = x
        return len(json.dumps(res, separators=(",", ":"))) <= 65536
    except Exception:
        return False


def run_case(case):
    try:
        analogs, kinds = load_analogs(case)
        if len(analogs) < MIN_ANALOGS:
            raise ValueError("too few usable analogs")
        q = forecast_quantiles(target_series(case), analogs, PARAMS, case_kind(case), kinds)
        res = {"hours": [{"hour": h, "q": clean_row(q[h])} for h in range(2, 25)]}
    except Exception:  # never leave a case invalid: fall back to the flat forecast
        res = None
    if res is None or not valid_result(res):
        res = baseline_result(hour1_print(case))
    return res


def forecast_file(path):
    """Forecast for one input file; whatever goes wrong (unreadable, not JSON, odd shape), a valid forecast."""
    raw = ""
    try:
        with open(path, "rb") as f:
            raw = f.read().decode("utf-8", errors="replace")
        case = json.loads(raw)
        res = run_case(case)
    except Exception:
        res = None
    if res is None or not valid_result(res):
        res = baseline_result(hour1_print(None, raw))
    return res


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for n in names:
        try:
            res = forecast_file(os.path.join(in_dir, n))
        except Exception:
            res = baseline_result(1.0)
        try:
            with open(os.path.join(out_dir, n[:-3] + ".out"), "w", encoding="utf-8") as f:
                json.dump(res, f, separators=(",", ":"))
        except Exception:  # one case's write failing must not stop the others
            continue
    return 0


if __name__ == "__main__":
    sys.exit(main())
