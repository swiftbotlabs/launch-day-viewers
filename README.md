# GTA VI launch-day Twitch viewers: analog-ensemble forecast

[![make.fun competition](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun)

This is an entry for the make.fun contest *Forecast GTA VI's launch-day Twitch viewers hour by hour*. `main.py` uses
Python 3.13 and the standard library only. It needs no network, gives the same output on every run, and takes about
0.05 s per case. It reads every `*.in` in `$MAKEFUN_INPUT_DIR` (default `/input/`) and writes `<id>.out` to
`$MAKEFUN_OUTPUT_DIR` (default `/output/`). Each output has five quantiles (5/25/50/75/95%) for each of hours 2-24.

## What the model does

It forecasts each hour's **log ratio to hour 1's print**, using the release days of the past launches in
`comparables` as analogs. Every comparable is aligned to 00:00 UTC of its release date, so its hours line up with
GTA VI's both in the daily Twitch cycle and in the timing of the regional unlocks.

1. **Analogs.** Every comparable launch that has an hour-1 point and at least 12 points on its release day. GTA VI's
   own pre-release category is left out because it is not a launch.
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
3. **Centre.** The weighted mean of the analogs' log ratios for each hour, plus a decaying **momentum carry**
   (0.5·e^−(h−2)/3 times how much faster the case moved into hour 1 than its analogs did).
4. **Spread.** √(weighted variance·(1 + 1/n_eff) + 0.15²) per hour. It is scaled by 0.8 for the 25/75% quantiles
   and 1.0 for the 5/95% ones, because the ratios have fat tails.

## How it was validated

- **Scorer** (`tools/validate.py`): the rules' pinball loss 2·max(τd, (τ−1)d) on d = ln y − ln q. It reproduces
  the rules' worked example exactly: all ten item losses, 0.112545, a typical miss of 19.52%, coverage 1, and
  0.360659 for the invalid case.
- **Leave-one-out** over the 37 launches in the comparables. Each launch is cut at the end of hour 1 of its release
  day, hours 2-24 are forecast from the other 36, and the result is scored beside the house baseline (flat at hour 1,
  spread 0.15·√(h−1)).
- **Nested leave-one-out** (`tools/nested.py`): the whole tuning (`tools/tune.py`) is rerun on the other 36
  launches inside every fold. This is the honest estimate of the procedure, tuning included.
- **Practice cases:** their answers are not in the kit, since every practice case's comparables leave out the four
  practice launches, so they could not be scored. Their outputs were checked for format and determinism, and their
  forecast shapes were inspected.
- **Smoke tests** (`tools/smoke.py`): a strict format check on the practice outputs and on synthetic final-shaped
  cases (minute-level history, a record hour 1, no history, a zero print).

| subset (hours scored) | LOO model | nested LOO model | baseline | 90% coverage (LOO / nested / baseline) |
|---|---|---|---|---|
| all 37 launches (851) | **0.3554** | 0.3717 | 0.9296 | 0.887 / 0.878 / 0.624 |
| live at hour 1, h1 ≥ 10k (644) | **0.2232** | 0.2357 | 0.3508 | 0.910 / 0.898 / 0.766 |
| big, h1 ≥ 100k (368) | **0.1945** | 0.2040 | 0.2611 | 0.927 / 0.902 / 0.837 |
| rolling or mixed unlock (207) | **0.2380** | 0.2702 | 0.3977 | 0.889 / 0.870 / 0.758 |

On the live subset, the share of prints below each quantile (nested) is 0.04 / 0.28 / 0.49 / 0.73 / 0.94, against
the nominal 0.05 / 0.25 / 0.50 / 0.75 / 0.95.

Caveats: there are only 37 launches, and just 9 of them are rolling or mixed. The final also adds the four practice
launches (all rolling) to the analog pool. A practice or LOO score is not a guarantee for the final, whose prints are
minute means rather than SullyGnome's hourly averages.

Reproduce (Python 3.13, one process each):

    python3 tools/validate.py <kit>/input/p00.in     # scorer check + LOO
    python3 tools/nested.py   <kit>/input/p00.in     # nested LOO (~2 min)
    python3 tools/smoke.py    <kit>/input            # format + synthetic final cases

Data: SullyGnome.com hourly Twitch category averages, as given in the contest kit.

## License

MIT, © Swift Bot Labs.
