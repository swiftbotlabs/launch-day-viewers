# Result (round 5)

The final commit is the one that adds this file (its sha is printed in the session). `main.py` last changed in
`35a44e9`, where the dip-guard options were added switched off, so the outputs match `312184b`.

**Final numbers.**

| | LOO, 37 launches | nested LOO | house baseline |
|---|---|---|---|
| all | **0.3533** | 0.3675 | 0.9296 |
| live at hour 1 | 0.2238 | 0.2330 | 0.3508 |
| rolling/mixed unlock | 0.2397 | 0.2672 | 0.3977 |
| 90% coverage, all | 0.898 | 0.878 | 0.624 |

- **Run time:** 23.7 ms median per case (15 interleaved runs per case, interpreter start included), against
  23.6 ms for round 4's `main.py`.
- **Interpreters:** outputs are byte-identical on Python 3.12.15 and 3.14.4.
- **Final case:** run `python3 tools/validate.py h00.in` once the house cuts it (2026-11-19T01:00Z). It prints LOO
  with and without the 4 practice launches.

## The three review points

1. **Hour 1 at 3, 4, 5 and 6 million: the median is not capped** (`3c1f23f`; `tools/stress.py <kit> sizes`).
   - The size clamp acts only on the analog weights: a record hour 1 is weighted like the largest launches. Every
     quantile is hour 1 × exp(log ratio), so it scales with hour 1.
   - The quantile / hour-1 ratios are identical at all four sizes. No fix was needed, so the numbers are the same
     before and after:

   | hour 1 | h2 median (5-95%) | h6 | h12 | h24 |
   |---|---|---|---|---|
   | 3M | 2.58M (1.58-4.22) | 2.32M (1.21-4.43) | 2.10M (0.82-5.35) | 4.12M (2.20-7.70) |
   | 4M | 3.44M (2.10-5.63) | 3.09M (1.62-5.91) | 2.80M (1.10-7.13) | 5.49M (2.94-10.27) |
   | 5M | 4.30M (2.63-7.03) | 3.87M (2.02-7.39) | 3.50M (1.37-8.91) | 6.86M (3.67-12.83) |
   | 6M | 5.16M (3.16-8.44) | 4.64M (2.43-8.87) | 4.20M (1.65-10.70) | 8.24M (4.40-15.40) |

2. **Dip guard: tested, not kept** (`35a44e9`; it stays in the code, switched off).
   - It has two parts: a weighted-median centre for hours 2-4 or 2-6, and the 5% quantile widened ×1.15 to ×1.5
     for hours 2-6.
   - **Pooled LOO:** every setting was worse than off. The mildest (median for hours 2-4, ×1.15) moved all
     0.3533 → 0.3550 and live 0.2238 → 0.2259. The 5% quantile alone at ×1.15 gave 0.3536.
   - **Nested LOO** (median for hours 2-4, ×1.15): all 0.3675 → 0.3816, live 0.2330 → 0.2361, big 0.2043 → 0.2099,
     rolling 0.2672 → 0.2715.
   - The lower tail is already slightly wide (3.4% of prints below the 5% quantile). The momentum cap and the
     spread taken from the analogs' unshifted days already guard against a misleading early hour.

3. **Provenance.**
   - **Verified in git:** the first commit is `8dfd43b`, at 2026-11-17 08:46:44 UTC. Every commit in this
     repository has the one author, Swiftbot, and was written by the one recorded Claude Code session that built
     the entry.
   - **Stated by the entrant** (not checkable from inside the session): the GitHub repository
     swiftbotlabs/launch-day-viewers was created on 17 Nov 2026, and this session's transcript is uploaded with
     the entry, as the contest requires.
