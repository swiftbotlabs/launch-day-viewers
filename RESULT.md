# Result (round 3)

The final commit is the one that adds this file (its sha is printed in the session). `main.py` last changed in
`7ad5480`.

**Final numbers.** LOO over 37 launches: **0.3538** against the house baseline's 0.9296. Nested LOO: 0.3764. 90%
coverage: 0.886 (nested 0.864, baseline 0.624). Live at hour 1: 0.2237 (nested 0.2348) against 0.3508.
Rolling/mixed unlock: 0.2393 (nested 0.2676) against 0.3977. Run time is 0.02-0.07 s per case, on Python 3.12.15 and
3.14.4. Outputs, LOO and step-wise test output are byte-identical between the two (3.13 is not on this machine).

## The four review points

1. **SPDX:** LICENSE now starts with `SPDX-License-Identifier: MIT` and an empty line; the rest is unchanged
   (`f7c9ff4`).

2. **Spread floor 0.25 when n_eff < 4: tested, not adopted** (`4c3509c`; the code is kept, switched off with
   `thin_floor` 0).
   - It fires on 4 of the 37 held-out launches (Cyberpunk, Elden Ring, Silksong, Marvel Rivals).
   - On those, coverage rose from 0.848 to 0.891, but loss got *worse*, 0.2553 → 0.2570. Elden Ring and Cyberpunk
     are huge, flat days where the narrow band was right.
   - Overall LOO went from 0.3525 to 0.3526, live from 0.2227 to 0.2231 and big from 0.1948 to 0.1956. The other
     33 launches were unchanged.
   - In the record-hour-1 stress test the medians are unchanged. The bands widen: the record ramp at hour 20 goes
     from 0.81-3.08× to 0.75-3.33×, and the sudden 50× jump from 0.65-1.17× to 0.56-1.36×.
   - It hurts the overall loss and does not help the thin cases' loss, so it fails the rule. Its only gain is in a
     made-up scenario that LOO cannot score.

3. **Practice launches as extra LOO cases: not possible with the kit.**
   - Their release-day hours 2-24 are not in it: each practice case's history stops at 00:00Z, no practice case's
     comparables include another practice launch, and the answers are server-side (`reference/answer.json`).
   - They appear only in the final case's 42 comparables, which is where the reviewer's 13 = 9 + 4 rolling/mixed
     comes from.
   - **Without them** (all that can be scored now): 37 launches, 9 rolling/mixed, with the numbers above.
   - **With them:** `validate.py` now pools launches from several case files and, when practice launches are
     present, prints both sets, with and without (`e768121`). `python3 tools/validate.py h00.in` will do it once
     the final case exists. The plumbing was checked on a relabelled test file, whose numbers are not reported.
   - I did not fetch the curves from SullyGnome: its notice asks not to scrape it, and that would need your
     approval.

4. **Step-wise minute-level unlock: overshoot found and fixed** (`7ad5480`).
   - `tools/stepwise.py` builds GTA VI cases from minute reads that step up as each region unlocks (New Zealand
     11:00Z the day before, eastern Australia 13:00Z, Japan 15:00Z, Europe 23:00Z, UK 00:00Z) up to the 01:00Z
     cut, with hour 1 at 1.7-2.5M.
   - With the roll-out late-heavy or concentrated at the UK unlock, ln(h1/h0) reaches +0.74 and +1.0, against a
     10th-90th percentile range of −0.36 to +0.17 among past live launches.
   - The uncapped momentum carry then put hour 2's median at 1.01×, 1.35× and 1.54× hour 1, and hour 3 at up to
     1.14×. Every rolling analog dips there instead.
   - **Fix:** cap the momentum gap at ±0.2, the largest cap that meets the criterion set beforehand (hour 2 ≤ 1.1×
     and hours 3-4 ≤ 1.0× in every scenario). Hour 2 is now 0.98×, 0.99× and 1.07×, and hour 3 at most 0.88×.
   - **Cost:** LOO overall 0.3525 → 0.3538, live 0.2227 → 0.2237, rolling/mixed 0.2390 → 0.2393.
   - Nested overall went from 0.3689 to 0.3764, but about 0.0065 of that is one launch: Kingdom Come II, a
     414-viewer category not yet unlocked at hour 1. Nested live moved +0.0016, big +0.0020 and rolling/mixed −0.0005.
