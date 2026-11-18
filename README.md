# GTA VI launch-day Twitch viewers: analog-ensemble forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/swiftbotlabs/launch-day-viewers/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/swiftbotlabs/launch-day-viewers/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

This is an entry for make.fun's *Forecast GTA VI's launch-day Twitch viewers hour by hour*. `main.py` targets
Python 3.13 and uses the standard library only. It needs no network, gives the same output on every run, and takes
about 23 ms per case (interpreter start included). It was checked byte for byte on Python 3.12 and 3.14. It reads every `*.in` in
`$MAKEFUN_INPUT_DIR` (default `/input/`) and writes `<id>.out` to `$MAKEFUN_OUTPUT_DIR` (default `/output/`):
5/25/50/75/95% quantiles for each of hours 2-24.

## Method

It forecasts each hour's log ratio to hour 1's print from the release days of the past launches in `comparables`.
All of them are aligned to 00:00 UTC of their release date.

1. **Kernel weights** on size (ln hour 1), 6-hour momentum, channel growth, and **unlock type** parsed from the
   text: *rolling* (midnight local), *mixed* (rolling plus one PC/Steam unlock), *simultaneous* or *early access*.
   The same type counts ×5 and a known different type ×0.05. GTA VI is typed rolling, as the rules state. The size
   kernel is clamped at the largest analog, so a record hour 1 leans on the group of the biggest launches.
2. **Daylight-saving blend.** GTA VI's unlocks (Europe 23:00Z, UK 00:00Z, US east 05:00Z, west 08:00Z) fall an hour
   later in UTC than a summer-time launch's. The US-unlock jump lands in hour 5 for summer launches and hour 6 for
   winter ones. An analog from the other season contributes, for the centre, the mean of its own hour and its hour
   shifted onto the case's clock.
3. **Centre:** the weighted mean of the log ratios, plus a momentum carry,
   0.5·e^−(h−2)/3 · (the case's ln(h1/h0) minus the analogs'), with that gap capped at ±0.2.
4. **Spread:** √(var·(1+1/n_eff) + 0.15²), measured on the analogs' unshifted days, ×0.8 for the 25/75% quantiles
   and ×1.0 for the 5/95% ones. When fewer than 4 effective analogs remain (a record hour 1), the 5/95% quantiles
   are widened ×1.15.
5. **Speed:** only the hours the model reads (48 h before the cut to the day's end) are parsed, through a fast
   ISO-hour path.
6. **Fault isolation:** each file gets its own try/except. A bad or unusable case (fewer than 5 analogs) gets the
   house baseline around hour 1's print, and every result is shape-checked before it is written.

## Validation

The scorer reproduces the rules' worked example exactly (0.112545). **Leave-one-out (LOO)** runs over the 37
launches in the comparables: each is cut at the end of hour 1 of its release day and scored on hours 2-24 against
the house baseline. **Nested LOO** re-tunes every numeric parameter inside each fold. The design switches (the
daylight-saving blend and the momentum cap) are held fixed. The practice answers are not in the kit, so the practice
cases cannot be scored.

| subset (hours) | LOO | nested LOO | baseline | 90% coverage (LOO / nested / baseline) |
|---|---|---|---|---|
| all 37 launches (851) | **0.3533** | 0.3675 | 0.9296 | 0.898 / 0.878 / 0.624 |
| live at hour 1, h1 ≥ 10k (644) | **0.2238** | 0.2330 | 0.3508 | 0.911 / 0.901 / 0.766 |
| big, h1 ≥ 100k (368) | **0.1964** | 0.2043 | 0.2611 | 0.927 / 0.913 / 0.837 |
| rolling or mixed unlock (207) | **0.2397** | 0.2672 | 0.3977 | 0.879 / 0.879 / 0.758 |

**Tried and not adopted**, because LOO or nested LOO got worse:
- softer unlock weights;
- tempering to a minimum n_eff;
- pool-variance inflation;
- a lower size clamp;
- a full or timing-only daylight-saving shift;
- a 0.25 spread floor when n_eff < 4;
- an explicit US-unlock step at hour 6 (`dst_mode` "step");
- a dip guard (an early-hours median plus a wider 5% quantile).

RESULT.md has the numbers.

**Caveats:**
- There are only 37 launches, and 9 of them are rolling or mixed. The final's comparables add the 4 practice
  launches.
- At a record hour 1 the forecast rests on about 2-3 effective analogs. Its medians and bands still scale with
  hour 1 at 3-6 million; nothing caps them.
- Prints in the final are minute means, not SullyGnome's hourly averages.

## Run

    python3 tools/validate.py <kit>/input/p00.in   # scorer check + LOO; several case files pool their launches
    python3 tools/validate.py h00.in               # final case: LOO with and without the 4 practice launches
    python3 tools/nested.py   <kit>/input/p00.in '{"dst_align": true, "dst_mode": "blend", "var_own": true, "mom_cap": 0.2, "thin_kout": 1.15}'
    python3 tools/smoke.py    <kit>/input          # format, synthetic final cases, 9 malformed inputs
    python3 tools/stress.py   <kit>/input          # record hour 1, odd histories
    python3 tools/stress.py   <kit>/input sizes    # hour 1 at 3/4/5/6 million: medians and bands
    python3 tools/stepwise.py <kit>/input          # minute-level region-by-region unlock up to the 01:00Z cut

Data: SullyGnome.com hourly Twitch category averages, from the contest kit. Licence: MIT, © Swift Bot Labs.
