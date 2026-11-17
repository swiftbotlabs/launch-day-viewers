# Result (round 2)

Code commit: `4ad296aaddc745a2c7f1a451095b37daaece7187` (main.py last changed in `a26e25d`, identical at `4ad296a`
and at the branch head; the commit after it only updates this file).

The cases are the 37 comparable launches. Each is cut at the end of hour 1 of its release day and scored on hours
2-24, 851 scored hours in all. Losses are the rules' mean pinball loss on the log scale, from the scorer in
`tools/validate.py`, which reproduces the rules' worked example exactly (0.112545).

| | model (leave-one-out) | model (nested LOO) | house baseline (same cases) | round 1 model (LOO / nested) |
|---|---|---|---|---|
| loss, all 37 launches | **0.3525** | 0.3689 | 0.9296 | 0.3554 / 0.3717 |
| loss, live at hour 1 (h1 ≥ 10k, 644 h) | **0.2227** | 0.2332 | 0.3508 | 0.2232 / 0.2357 |
| loss, big launches (h1 ≥ 100k, 368 h) | **0.1948** | 0.2027 | 0.2611 | 0.1945 / 0.2040 |
| loss, rolling or mixed unlock (207 h) | **0.2390** | 0.2681 | 0.3977 | 0.2380 / 0.2702 |
| 90% coverage, all | 0.890 | 0.872 | 0.624 | 0.887 / 0.878 |
| 90% coverage, live at hour 1 | 0.911 | 0.896 | 0.766 | 0.910 / 0.898 |
| typical miss (median), all | 70.7% | 74.8% | 213.3% | 71.1% / 75.1% |

Nested LOO re-tunes every numeric parameter, including the unlock-type weights, on the other 36 launches in each
fold. The daylight-saving switches (`dst_align` blend, `var_own`) are design choices made on all 37 launches and are
held fixed. With them switched off, the same nested run reproduces round 1's 0.3717 exactly.

## Changes this round
1. **README badges:** the three required make.fun badges sit directly under the title, exactly as given.
2. **Fault isolation:** every `*.in` is handled in its own try/except. An unreadable, non-JSON or misshapen case, or
   one with fewer than 5 usable analogs, gets the baseline formula around hour 1's print. Malformed comparables and
   rows are skipped one by one, and every result is shape-checked before it is written. The smoke test covers 9
   malformed or minimal inputs: all give valid forecasts, and a good case after them is unchanged.
3. **Python 3.12.15 and 3.14.4:** the grader's 3.13 is not on this machine, so main.py was run under 3.12 and 3.14,
   one on each side of it. The four practice outputs are byte-identical between the two (sha256 p00 e6849152…,
   p01 798eeb34…, p02 794acb7e…, p03 eb33eba6…). So is the full printed output of the LOO validation, smoke and
   stress tests, and of the nested LOO.
4. **Reviewer's tips:**
   - a) **Softer unlock-type weights: not adopted.** In plain LOO, all 30 softer pairs were worse on all launches,
     on live and on rolling/mixed. In nested LOO with the weights held fixed, all/live/rolling loss was 0.3622 /
     0.2251 / 0.2403 at ×5/×0.05, against 0.3672 / 0.2263 / 0.2461 at ×3/×0.1 and 0.3717 / 0.2298 / 0.2521 at
     ×2/×0.2. Only the big subset improved, by 0.0035. Adaptive tempering to a minimum n_eff and pool-variance
     inflation were also worse at every setting.
   - b) **Record hour 1 (2, 3.5 and 5 million):** every output is valid. The ratios are identical across those sizes
     and the quantiles scale in proportion. At hour 20 the median is about 1.6× hour 1 with a 90% band of 0.81-3.11×,
     and the largest q95 is about 15.5M. Caveat: n_eff is about 2-3 there, and a 50× sudden jump from a quiet day is
     overconfident (README).
   - c) **Unlock roll-out at the 01:00 UTC cut:** GTA VI (winter time) has Europe at 23:00Z, the UK at 00:00Z, the US
     east coast at 05:00Z and the west coast at 08:00Z. Summer-time analogs have every midnight one hour earlier in
     UTC, and the data confirm it: the US-unlock jump lands in hour 5 for summer launches and hour 6 for winter ones.
     **Adopted:** a daylight-saving blend for the centre only. It passed the criterion set before the nested run
     (nested no worse on all and live, and no more than 0.001 worse on big and rolling); in the end it was better on
     all four subsets.

- **Run time per case:** 0.03-0.06 s wall time on either interpreter (`python3 -P -s main.py`, one case per run,
  21-25 MB), well under the 8 s limit.
- **Practice cases p00-p03:** not scored, because their answers are not in the kit.
