# ML Cut Selection Implementation Flow

## 1. Goal

The goal is to make `ML_MODE` prune the mapper cut pool more aggressively than baseline without causing obvious QoR regressions.

The important clarification is:

- `cuts_used` is **not** the number of candidate cuts kept by ML.
- `candidate_cuts` is the number of non-trivial cuts still attached to nodes after filtering.

That distinction matters because ML can remove a large fraction of candidates while the final mapped solution still uses the same number of cuts.

## 2. Runtime Flow

The active ML path is in:

- `src/map/mapper/mapperCore.c`
- `src/map/mapper/mapperCut.c`
- `src/map/mapper/ml_cut.c`
- `src/map/mapper/ml_cut.h`
- `src/map/mapper/ml_inference.h`

The runtime sequence in [mapperCore.c](/home/ayush/abc/src/map/mapper/mapperCore.c:50) is:

1. Read `ML_MODE` from the environment.
2. Compute cuts with `Map_MappingCuts()`.
3. Compute truth tables with `Map_MappingTruths()`.
4. If `g_mode > 0`, call `Map_CutFilter_ML()`.
5. Run matching with `Map_MappingMatches()`.

The ML hook is therefore placed before matching, which is the correct point if the intent is to reduce or rerank the candidate cut pool.

## 3. What Was Wrong With The Old Interpretation

The original evaluation focused too much on:

- `qor`
- `cuts_used`

That is incomplete because [Map_MappingCountUsedCuts()](/home/ayush/abc/src/map/mapper/mapperRefs.c:544) counts only the best cuts that survive all the way into the final mapped network.

It does **not** measure how many candidates the mapper had to carry before matching.

To measure the ML filter itself, the better metric is [Map_MappingCountAllCuts()](/home/ayush/abc/src/map/mapper/mapperCut.c:112), which counts all remaining non-trivial cuts after filtering. This is now reported as `candidate_cuts` in [PrintCutStats()](/home/ayush/abc/src/map/mapper/mapperCut.c:442).

## 4. Current ML Policy

The current policy is no longer "hard class gate then prune".

It is:

1. Score each cut with `ML_ScoreCut(...)`.
2. Blend model output with structural heuristics.
3. Prune early with an ML-specific prefilter cap.
4. Re-rank cuts per node by score.
5. Keep a mode-dependent top segment.
6. Keep only a small floor plus cuts whose score remains close to the best cut.

This makes the ML path stricter than baseline while still leaving a conservative escape hatch for nodes where several cuts score similarly.

## 5. Current Mode Knobs

The active knobs live in [ml_cut.c](/home/ayush/abc/src/map/mapper/ml_cut.c:148).

### Final top-N limit

- `mode <= 0`: `250`
- `mode == 1`: `20`
- `mode == 2`: `14`
- `mode >= 3`: `10`

### Prefilter limit before the final ML pass

- `mode <= 0`: `250`
- `mode == 1`: `96`
- `mode == 2`: `64`
- `mode >= 3`: `40`

### Minimum keep floor

- `mode <= 0`: `250`
- `mode == 1`: `8`
- `mode == 2`: `6`
- `mode >= 3`: `4`

### Score window from the best cut

- `mode <= 0`: `0.00`
- `mode == 1`: `0.35`
- `mode == 2`: `0.25`
- `mode >= 3`: `0.20`

The final keep behavior is implemented in [Map_CutFilter_ML()](/home/ayush/abc/src/map/mapper/mapperCut.c:348).

## 6. What The Output Means

The mapper now prints two separate lines:

```text
RESULT g_mode=<mode> qor=<area> cuts_used=<final_mapped_cuts>
CUT_STATS g_mode=<mode> candidate_cuts=<remaining_candidate_pool>
```

Interpret them as follows:

- `qor`: the final mapped cost currently reported by the mapper
- `cuts_used`: how many cuts ended up in the final chosen mapping
- `candidate_cuts`: how many non-trivial cuts were still available after filtering

Therefore:

- if `candidate_cuts` drops and `qor` stays flat, ML pruning is working safely
- if `candidate_cuts` drops and `cuts_used` stays flat, that is still a real filtering effect
- if `qor` gets worse while `candidate_cuts` drops, the ML policy is too aggressive for that benchmark

## 7. Validation Examples

### `bigkey.blif`

```text
ML_MODE=0 -> RESULT qor=6213.00 cuts_used=5789
             CUT_STATS candidate_cuts=55157
ML_MODE=1 -> RESULT qor=6213.00 cuts_used=5789
             CUT_STATS candidate_cuts=33621
ML_MODE=2 -> RESULT qor=6213.00 cuts_used=5789
             CUT_STATS candidate_cuts=27749
ML_MODE=3 -> RESULT qor=6213.00 cuts_used=5789
             CUT_STATS candidate_cuts=20960
```

Interpretation:

- the ML path is clearly active
- stricter modes are pruning more candidates
- for this benchmark, the final mapped solution is stable enough that `qor` and `cuts_used` do not move

That is a valid and desirable result.

### `riscv_core_lut6.blif`

```text
ML_MODE=0 -> RESULT qor=7969.00 cuts_used=7074
             CUT_STATS candidate_cuts=189926
ML_MODE=1 -> RESULT qor=7973.00 cuts_used=7074
             CUT_STATS candidate_cuts=23850
```

Interpretation:

- candidate cuts dropped by about `87%`
- final `cuts_used` stayed unchanged
- QoR regressed slightly (`+4`)

This shows the filter is strong enough to matter on larger circuits.

### `C6288.blif`

```text
ML_MODE=0 -> RESULT qor=9974.00 cuts_used=9460
             CUT_STATS candidate_cuts=129160
ML_MODE=1 -> RESULT qor=9982.00 cuts_used=9470
             CUT_STATS candidate_cuts=27899
```

Interpretation:

- candidate cuts dropped by about `78%`
- QoR regressed slightly (`+8`)
- the final mapped solution changed a little

This is the kind of benchmark that should drive threshold tuning.

## 8. Script Updates

Two repo scripts were updated to match the current behavior.

### `scripts/run_blif_tests.sh`

The runner now supports configurable mode sets through `MODES`.

Examples:

```bash
scripts/run_blif_tests.sh
MODES="0 1 2 3" scripts/run_blif_tests.sh
MODES="0 3" scripts/run_blif_tests.sh results/blif_modes_0_3.log
```

If no log filename is provided, it now derives one from the mode list.

### `scripts/map_results.py`

The parser now:

- reads both `RESULT` and `CUT_STATS`
- supports arbitrary mode lists instead of assuming only `0/1`
- reports per-mode deltas vs a configurable baseline
- prints a summary showing wins/losses and average candidate-cut reduction

Example:

```bash
python3 scripts/map_results.py results/blif_modes_0_1_2_3.log --baseline 0
python3 scripts/map_results.py results/blif_modes_0_1.log --baseline 0 --output results/mode_compare.csv
```

## 9. Current Conclusion

The runtime ML path is working correctly in the following sense:

- higher `ML_MODE` values reduce `candidate_cuts`
- baseline mode remains unchanged
- many benchmarks preserve the same final `qor`

What is **not** proven yet is that the current model consistently improves final mapping quality. Right now the evidence is:

- the filter is active
- the filter is strong
- QoR impact is benchmark-dependent

## 10. Remaining Limitations

The main limitation is still the training/export side:

1. the dataset quality needs cleanup
2. feature semantics must be verified end-to-end
3. the exported model may still be weak or mismatched

Without fixing that pipeline, runtime tuning alone can only go so far.

## 11. Recommended Next Steps

1. Run `scripts/run_blif_tests.sh` with `MODES="0 1 2 3"`.
2. Parse the log with `python3 scripts/map_results.py`.
3. Evaluate both:
   - QoR deltas vs baseline
   - candidate-cut reduction vs baseline
4. Tune:
   - `ML_CutMinKeepForMode()`
   - `ML_CutScoreWindowForMode()`
   - `ML_CutLimitForMode()`
5. Retrain and re-export the model only after the data pipeline is verified.

## 12. Short Summary

The important correction is not just that ML pruning exists.

It is that evaluation now distinguishes:

- the final mapped solution (`cuts_used`)
- the surviving candidate pool (`candidate_cuts`)

With that distinction, `ML_MODE` is visibly doing work even on benchmarks where QoR remains unchanged.
