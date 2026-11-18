# Result (round 6)

The final commit is the one that adds this file (its sha is printed in the session). `main.py` last changed in
`af90949`.

**Final numbers.**

| | LOO, 37 launches | nested LOO | house baseline |
|---|---|---|---|
| all | **0.3535** | 0.3673 | 0.9296 |
| live at hour 1 | 0.2239 | 0.2329 | 0.3508 |
| big launches | 0.1964 | 0.2041 | 0.2611 |
| rolling/mixed unlock | 0.2398 | 0.2668 | 0.3977 |
| 90% coverage, all | 0.894 | 0.882 | 0.624 |

- **Run time:** 25.6 ms median per case, against 26.2 ms for the previous commit (15 interleaved runs per case,
  interpreter start included). The absolute numbers drift with machine load (the same code measured about 23 ms
  earlier); interleaved, this round costs nothing.
- **Interpreters:** outputs are byte-identical on Python 3.12.15 and 3.14.4.

## The four review points

(a) **Practice launches in the nested LOO: skipped.** Their release-day hours 2-24 are not available anywhere I
can reach:
- each practice case's history stops at 00:00Z on its release day;
- no practice case's comparables include a practice launch;
- the answers are server-side;
- the final case h00, whose 42 comparables do include them, is not cut until 2026-11-19T01:00Z and did not exist
  when this ran (2026-11-18, 11:00Z).

Once it exists, `python3 tools/validate.py h00.in` prints LOO with and without them. No model change was made for
this point.

(b) **Shrinking a record hour 1 toward the big launches' pooled curve: tested, not kept** (`db5b173`; off,
`record_shrink` 0).
- The centre was (1−λ)·kernel + λ·(the mean log ratio of the launches with hour 1 ≥ 100k), used only when hour 1
  is above every analog.
- In LOO this can only touch Elden Ring, the one launch bigger than all the others. At λ = 0.25 it improved
  (0.0842 → 0.0771; all 0.3533 → 0.3531), and λ ≥ 0.5 was worse.
- **Nested (λ = 0.25):** all 0.3675 → 0.3688, live 0.2330 → 0.2340, big 0.2043 → 0.2051, rolling 0.2672 → 0.2658.
  Overall is worse, so it is not kept.

(c) **Narrower bands for hours 2-6: kept at ×0.95** (`af90949`).
- **Nested:** big launches 0.2043 → **0.2041**, all 0.3675 → 0.3673, live 0.2330 → 0.2329, rolling
  0.2672 → 0.2668.
- **Plain LOO:** big unchanged (0.1964), all 0.3533 → 0.3535.
- The gain is tiny (0.0002, within noise). It is kept because the stated rule (nested big-launch loss improves)
  holds.
- ×0.9 and narrower were worse in LOO: big hours 2-6 went 0.1572 → 0.1576-0.1631, and coverage fell to
  0.75-0.89.
- At a 3-6M hour 1, the hour-2 band narrows slightly (3M: 1.58-4.22M → 1.62-4.12M) and the medians are
  unchanged.

(d) **Provenance in README.md:** a link anyone can check for the repository's creation date
(https://api.github.com/repos/swiftbotlabs/launch-day-viewers, field `created_at`), and a one-line pointer that
the session transcript is uploaded with the entry, as the contest requires.
