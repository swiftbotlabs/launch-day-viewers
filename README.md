# GTA VI launch-day Twitch viewers: analog-ensemble forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/swiftbotlabs/launch-day-viewers/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/swiftbotlabs/launch-day-viewers/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

This is an entry for the make.fun contest *Forecast GTA VI's launch-day Twitch viewers hour by hour*. `main.py` is
written for Python 3.13 and uses the standard library only. It needs no network, gives the same output on every run,
and takes about 0.05 s per case. It was run on Python 3.12 and 3.14 (one on each side of 3.13) with byte-identical
outputs. It reads every `*.in` in `$MAKEFUN_INPUT_DIR` (default `/input/`) and writes `<id>.out` to
`$MAKEFUN_OUTPUT_DIR` (default `/output/`). Each output has five quantiles (5/25/50/75/95%) for each of hours 2-24.

## What the model does

It forecasts each hour's **log ratio to hour 1's print**, using the release days of the past launches in
`comparables` as analogs. Every comparable is aligned to 00:00 UTC of its release date, so its hours line up with
GTA VI's in the daily Twitch cycle and in when the regional unlocks fall.

1. **Analogs.** Every comparable launch that has an hour-1 point and at least 12 points on its release day. GTA VI's
   own pre-release category is left out because it is not a launch. A malformed comparable or row is skipped.
2. **Weights.** Each analog gets a Gaussian kernel weight based on how much it resembles the case at the end of hour 1:
   - size, ln(hour-1 viewers). The bigger the hour 1, the flatter the rest of the day, because much of the audience
     is already watching;
   - momentum over the previous 6 hours;
   - channel growth (live channels at hour 1 against the earlier peak), which shows whether the game is already
     unlocked and being streamed;
   - **unlock type**, parsed from the `unlock` and `notes` text: *rolling* (console midnight local),
     *mixed* (rolling consoles plus one global PC/Steam unlock), *simultaneous* (one global unlock time) or
     *early access*. An analog with the same type counts ×5, and one with a known different type counts ×0.05.
     This was the strongest signal in validation. A launch whose game was not yet unlocked at hour 1 (Silksong,
     Battlefield 6) climbs 100× that day. One unlocked in Europe by 00:00 UTC dips overnight, bumps when the
     US unlocks, and peaks in the US afternoon. GTA VI is console-only and rolls from New Zealand (the rules), so
     it is typed *rolling*.
   - If hour 1 is bigger than every analog (likely for GTA VI), the size kernel is clamped to the largest analog,
     so the group of the biggest launches speaks for it instead of the single nearest one.
3. **Daylight-saving alignment.** GTA VI releases on 19 November, after summer time has ended in Europe and the US:
   Europe unlocks at 23:00Z, the UK at 00:00Z, the US east coast at 05:00Z and the west coast at 08:00Z. A
   summer-time launch's midnights (and its viewers' evenings) come an hour earlier in UTC. The data show it: the
   US-unlock jump lands in hour 5 for 7 of 17 summer launches and in hour 6 for 8 of 11 winter ones. So an analog
   released under a different US daylight-saving state than the case contributes, for the centre, the mean of its
   own hour and its hour shifted onto the case's clock ("blend"). Its hour-1 anchor and features stay its own, and
   the spread is measured on its unshifted day. A full shift and a timing-only shift validated worse.
4. **Centre.** The weighted mean of the analogs' log ratios for each hour, plus a decaying **momentum carry**
   (0.5·e^−(h−2)/3 times how much faster the case moved into hour 1 than its analogs did).
5. **Spread.** √(weighted variance·(1 + 1/n_eff) + 0.15²) per hour. It is scaled by 0.8 for the 25/75% quantiles
   and 1.0 for the 5/95% ones, because the ratios have fat tails.
6. **Fault isolation.** Each input file is handled inside its own try/except. If a case is unreadable, is not JSON,
   has the wrong shape, or yields fewer than 5 usable analogs, it still gets a valid forecast: the house baseline
   formula around hour 1's print, taken from `known`, else the last history point, else the raw text, else 1. Every
   result is checked against the rules' output shape before it is written.

## How it was validated

- **Scorer** (`tools/validate.py`): the rules' pinball loss 2·max(τd, (τ−1)d) on d = ln y − ln q. It reproduces
  the rules' worked example exactly: all ten item losses, 0.112545, a typical miss of 19.52%, coverage 1, and
  0.360659 for the invalid case.
- **Leave-one-out** over the 37 launches in the comparables. Each launch is cut at the end of hour 1 of its release
  day, hours 2-24 are forecast from the other 36, and the result is scored beside the house baseline (flat at hour 1,
  spread 0.15·√(h−1)).
- **Nested leave-one-out** (`tools/nested.py`): the tuning (`tools/tune.py`, every numeric parameter including the
  unlock-type weights) is rerun on the other 36 launches inside every fold. The on/off design switches for the
  daylight-saving blend were chosen on all 37 launches and are held fixed.
- **Practice cases:** their answers are not in the kit, since every practice case's comparables leave out the four
  practice launches, so they could not be scored. Their outputs were checked for format and determinism.
- **Smoke tests** (`tools/smoke.py`): a strict format check on the practice outputs, on synthetic final-shaped cases
  (minute-level history, a record hour 1, no history, a zero print), and on malformed inputs. These include an empty
  file, non-JSON, truncated JSON, a JSON array, a minimal object, junk rows, a non-numeric or NaN hour 1, and bad
  UTF-8. Each gets a valid forecast, and a good case listed after them forecasts exactly as on its own.
- **Stress test** (`tools/stress.py`): a record hour 1 of 2, 3.5 and 5 million viewers. The ratios are identical
  across those sizes and the quantiles scale in proportion (largest q95 about 15.5M, far below the 1e9 cap).
- **Python 3.12 and 3.14:** the practice outputs, the LOO, smoke and stress output, and the nested LOO output are
  byte-identical under both.

| subset (hours scored) | LOO model | nested LOO model | baseline | 90% coverage (LOO / nested / baseline) |
|---|---|---|---|---|
| all 37 launches (851) | **0.3525** | 0.3689 | 0.9296 | 0.890 / 0.872 / 0.624 |
| live at hour 1, h1 ≥ 10k (644) | **0.2227** | 0.2332 | 0.3508 | 0.911 / 0.896 / 0.766 |
| big, h1 ≥ 100k (368) | **0.1948** | 0.2027 | 0.2611 | 0.927 / 0.905 / 0.837 |
| rolling or mixed unlock (207) | **0.2390** | 0.2681 | 0.3977 | 0.879 / 0.860 / 0.758 |

On the live subset, the share of prints below each quantile (nested) is 0.04 / 0.27 / 0.49 / 0.74 / 0.94, against
the nominal 0.05 / 0.25 / 0.50 / 0.75 / 0.95.

**Tried and not adopted** (each one made leave-one-out or nested LOO worse):
- softer unlock-type weights (×3/×0.1 and ×2/×0.2): nested all 0.3672 and 0.3717 against 0.3622 with ×5/×0.05
  held the same way;
- tempering the weights to a minimum effective number of analogs (2 to 10);
- inflating the spread by the whole pool's variance when n_eff is small;
- a lower clamp on size.

Caveats:
- There are only 37 launches, and just 9 of them are rolling or mixed. The final adds the four practice launches
  (all rolling) to the analog pool.
- At a record hour 1 the forecast still rests on few effective analogs (n_eff ≈ 2-3, led by TLOU2), because
  broader weightings validated worse.
- A sudden jump to a record hour 1 from a quiet day before (no counterpart among past launches) gives an
  overconfident band. GTA VI's real history should instead show the roll-out ramp from New Zealand's unlock onwards.
- A LOO score is not a guarantee for the final, whose prints are minute means rather than SullyGnome's hourly
  averages.

Reproduce (one process at a time):

    python3 tools/validate.py <kit>/input/p00.in     # scorer check + LOO
    python3 tools/nested.py   <kit>/input/p00.in '{"dst_align": true, "dst_mode": "blend", "var_own": true}'
    python3 tools/smoke.py    <kit>/input            # format, synthetic final cases, malformed inputs
    python3 tools/stress.py   <kit>/input            # record hour 1 (2-5 million)

Data: SullyGnome.com hourly Twitch category averages, as given in the contest kit.

## License

MIT, © Swift Bot Labs.
