# Result (round 4)

The final commit is the one that adds this file (its sha is printed in the session). `main.py` last changed in
`312184b`.

**Final numbers.** LOO over 37 launches: **0.3533** against the house baseline's 0.9296. Nested LOO: 0.3675. 90%
coverage: 0.898 (nested 0.878, baseline 0.624). Live at hour 1: 0.2238 (nested 0.2330) against 0.3508.
Rolling/mixed unlock: 0.2397 (nested 0.2672) against 0.3977. Outputs are byte-identical on Python 3.12.15 and
3.14.4 (3.13 is not on this machine).

## The five review points

1. **LOO on the real final case h00: not possible yet.**
   - h00 is cut by the house at 2026-11-19T01:00Z. It did not exist on this machine when this ran (2026-11-18,
     about 07:00Z), and nowhere in the kit.
   - **Without the practice launches**, which is all that can be scored now: the numbers above (37 launches, 9
     rolling/mixed).
   - **With them:** `python3 tools/validate.py h00.in` pools the 42 comparables, adds the 4 practice launches as
     LOO cases, and prints both sets (with and without).
   - No numbers were made up for it.

2. **Wider 5/95% quantiles when few analogs remain: kept** (`2b7e6e8`).
   - When an hour's n_eff < 4, the outer quantiles are widened ×1.15. The 25/50/75% quantiles are unchanged.
   - Pooled LOO: overall 0.3538 → **0.3533**. The 4 thin launches go from 0.2608 → 0.2562, with coverage
     0.815 → 0.924. Live (+0.0001), big (+0.0001) and the other 33 launches are unchanged.
   - Nested LOO: 0.3764 → **0.3675**, and better on all four subsets (live 0.2348 → 0.2330, big 0.2047 → 0.2043,
     rolling 0.2676 → 0.2672). A defaults bug in `nested.py` had kept this widening from firing; it is fixed.
   - ×1.3 and up were worse than ×1.15.
   - Record hour 1 of 2-5M (n_eff 2.3): the hour-20 90% band goes from 0.81-3.08× to **0.74-3.41×**, and the
     sudden 50× jump from 0.65-1.17× to 0.63-1.22×. The medians are unchanged.

3. **Explicit US-east unlock step at hour 6: tested, not kept** (`cc3ab00`; it stays selectable as `dst_mode`
   "step").
   - Analog hours are mapped by event: before the case's US hour (6 in winter time, 5 in summer) the analog's
     pre-US hours are used, and from it on, its post-US hours.
   - In `tools/stepwise.py` the step shows clearly: hour 5 is 0.52-0.55× and hour 6 0.75-0.79×, against the blend's
     gradual 0.57-0.64 → 0.73-0.78.
   - Pooled LOO improved (0.3533 → 0.3519).
   - **But nested LOO did not:** all 0.3675 → 0.3672, live 0.2330 → 0.2339, rolling/mixed 0.2672 → 0.2702. That
     fails the rule set beforehand: nested better on all and live, and no subset worse by more than 0.002.

4. **Speed** (`312184b`): timestamps of the fixed ISO form go through a fast path (a cached day ordinal plus the
   hour), and only the offsets the model reads are parsed (−49 to +24 h; rows outside are skipped by a string
   comparison).
   - Interleaved timing, 15 runs per case, wall time including the interpreter start: **before 29.8 ms, after
     23.1 ms median per case** (minimums 26.9-27.5 → 21.5-21.7 ms).
   - In process, analog parsing went from 7.5 to 2.4 ms. What is left is mostly JSON decoding (about 7 ms) and the
     interpreter start (about 8-10 ms).
   - Outputs are byte-identical before and after, for the practice cases, the smoke test (malformed inputs
     included), the step-wise test and the stress test.

5. **No prize amounts:** README.md and RESULT.md mention none. The only reward reference is the required `reward`
   badge, an image link.
