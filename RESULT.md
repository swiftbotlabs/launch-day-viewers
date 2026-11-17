# Result

Code commit: `371aaef037526b6d282c57accfc1a75de3f0e8dc` (main.py last changed in `b924498`, and is identical at
`371aaef`).

The cases are the 37 comparable launches. Each is cut at the end of hour 1 of its release day and scored on hours
2-24, 851 scored hours in all. Losses are the rules' mean pinball loss on the log scale, from the scorer in
`tools/validate.py`, which reproduces the rules' worked example exactly (0.112545).

| | model (leave-one-out) | model (nested LOO, tuning inside each fold) | house baseline (same cases) |
|---|---|---|---|
| loss, all 37 launches | **0.3554** | 0.3717 | 0.9296 |
| loss, live at hour 1 (h1 ≥ 10k, 644 h) | **0.2232** | 0.2357 | 0.3508 |
| loss, big launches (h1 ≥ 100k, 368 h) | **0.1945** | 0.2040 | 0.2611 |
| 90% coverage, all | 0.887 | 0.878 | 0.624 |
| 90% coverage, live at hour 1 | 0.910 | 0.898 | 0.766 |
| typical miss (median), all | 71.1% | 75.1% | 213.3% |

- **Run time per case:** 0.03-0.09 s wall time (`python3 -P -s main.py`, one case per run, about 20 MB of memory),
  well under the 8 s limit.
- **Determinism:** outputs are byte-identical across separate runs, and every practice output passes a strict
  format check.
- **Practice cases p00-p03:** not scored, because their answers are not in the kit (each practice case's comparables
  leave out the four practice launches).
