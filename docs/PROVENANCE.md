# Source provenance

Recorded 2026-09-30. Read this before trusting a number this package prints.

## What is here, and where it came from

Four modules, from two internal repositories.

| File here | Internal source | SHA-256 of source | Lines |
|---|---|---|---|
| `cogeco/sweep.py` | `VNES-Lab/experiments/010_cogeco_phase_sweep/cogeco_sweep.py` | `5e9f629db13bddb3…` | 1,195 → 1,268 |
| `cogeco/psv.py` | `VNES-Lab/lib/psv_core.py` | `aaebc2864f40b627…` | 335 → 162 |
| `cogeco/bridges.py` | `substrate_echo/dynamics/bridges.py` | `5dc385c8b04b935c…` | 272 → 272 |
| `cogeco/plot.py` | `VNES-Lab/experiments/010_cogeco_phase_sweep/visualize.py` | `f9b60461b9cfdc67…` | 140 → 165 |
| `cogeco/cli.py` | written for this package | — | new |

Plus `cogeco/__init__.py`, the tests, and this documentation.

### Full source hashes

```
5e9f629db13bddb3…  VNES-Lab/experiments/010_cogeco_phase_sweep/cogeco_sweep.py
f9b60461b9cfdc67…  VNES-Lab/experiments/010_cogeco_phase_sweep/visualize.py
aaebc2864f40b627…  VNES-Lab/lib/psv_core.py
5dc385c8b04b935c78f445ca14bcf0fe6f24dbf2162a072b73e0fe2d8f931114
                   substrate_echo/dynamics/bridges.py
```

## `bridges.py` — provenance established before use

This file was the reason the metric path could not be trusted as a public
dependency: it existed in the working tree of `substrate_echo` and had **never
been committed**. No commit history, no authorship record.

Per operator instruction, provenance was established before it was used here:

1. SHA-256 recorded — `5dc385c8b04b935c78f445ca14bcf0fe6f24dbf2162a072b73e0fe2d8f931114`
2. Its 24 existing tests confirmed passing, before and after, unchanged
3. Committed to `substrate_echo` as **`b5e607e5b9dafe4d68d4916f21418e44a4bf3b85`**
4. The repository's existing **MIT** licence covers it and was not modified
5. The commit message records that this is the **first** commit containing the
   file, with no earlier history invented
6. **No behaviour was altered.** The committed content is byte-identical to what
   was on disk, and to the copy shipped here.

Operator attestation: the file was produced by `UrukuTelal` or under their
direction as part of this architecture.

The commit message also notes that several *other* files in that working tree
are modified or untracked, and were deliberately left uncommitted.

## Changes made to `sweep.py`

Four changes. The first two are the reproducibility repair; the third is the
scientific-language correction; the fourth is the artifact schema.

### 1. RNG ownership — the substantive defect

`ConstraintRevisionManager._apply_revision` called the module-level
`random.random()`. The sweep's `seed` seeded a *different* `Random` that
governed only shock injection.

Consequence: **five runs of the same code at the same seed produced five
different results.** No seed could reproduce any published number. Any result
JSON produced before this repair — including the ones in `historical/` — is not
reproducible evidence.

Changes:

- `ConstraintRevisionManager.__init__` accepts `rng: Optional[random.Random]`
  and owns it. With no RNG supplied it is unseeded and therefore
  non-reproducible — the honest default, rather than something that silently
  pretends to be deterministic.
- `_apply_revision` draws from `self._rng`.
- `SeedVariedSweep` hands its existing per-seed stream to the manager.
- `DirectionalSweep` had **no RNG at all**, so every hysteresis run drew from
  the global stream and no hysteresis result was reproducible. It now takes a
  seed and derives a fresh stream per step from it.

No simulation logic was refactored. No thresholds, no dynamics, no regime
classification.

### 2. Wall-clock removed from the deterministic artifact

`save_report_json` wrote `elapsed_seconds`, which made every artifact unique and
every diff meaningless. Removed. Runtime is still shown to the operator in the
human-readable report, labelled *"operational metadata, not part of the
result"*.

The artifact gained `seed`, `config_summary`, `reproducibility_status`, and
`schema_version: 2`.

### 3. Scientific language

`TheoryHypothesis.supported: bool` became `register: str`, with three values:

| Value | Meaning |
|---|---|
| `CONSISTENT_WITH_THIS_MODEL` | this run agrees with what this model already predicts |
| `INCONSISTENT_WITH_THIS_MODEL` | it does not |
| `NOT_TESTED_BY_THIS_SWEEP` | the sweep does not test this |

The CLI previously printed `SUPPORTED` / `UNSUPPORTED`. A boolean forces the
caller to pick between "matches" and "is validated", and the previous CLI
picked the wrong one. `docs/METRICS.md` explains why reproducing a model's own
prediction cannot validate it.

The section is now headed `MODEL-CONSISTENCY CHECKS` and states in the output
that nothing here is compared against real data or an independent
implementation.

### 4. Plot rendering

`plot.main` took no arguments and assumed a filename in the working directory.
It now takes an artifact path and an output directory, so a figure can always be
traced to the artifact that produced it.

**It still never re-runs the simulation.** A plot that disagreed with the numbers
it claimed to show would be worse than no plot.

## Changes made to `psv.py`

Extracted from `psv_core.py`, which is 335 lines of a broader research library;
only `PillarState` is used here. That class was carried across unchanged except:

1. `to_metric` imports `.bridges` (local) instead of
   `substrate_echo.dynamics.bridges` (installed package).
2. **`clamp()` now validates the state size.** Upstream it iterated
   `range(NUM_PILLARS)` over whatever `theta` held, so
   `PillarState(theta=[0.5]*3, phi=[0.0]*3).clamp()` raised `IndexError` from
   inside the loop — a confusing crash far from the mistake. It now raises
   `ValueError` naming the expected size. Verified pre-existing: upstream
   `psv_core` raises the same `IndexError`.

The soft-clamping behaviour was **not** changed. It damps toward the boundary
region on every call and is therefore deliberately not idempotent; the test
asserts the domain invariant holds after repeated application instead.

## Licensing

**Apache-2.0** for this package, by operator decision.

No license file was added to, or modified in, `VNES-Lab`, `substrate_echo`, or
any other internal repository as part of this work. `substrate_echo`'s existing
MIT licence covers `bridges.py` as committed at `b5e607e`; VNES-Lab carries no
licence file, and the code here is used under the operator's grant.

## Third-party material

None carried across. The sweep imports only the standard library. The metric
bridge imports `numpy`. Plots import `matplotlib`. All ordinary and public.

## What is deliberately absent

| Not shipped | Why |
|---|---|
| the rest of `psv_core.py` (`Entity`, `FLLGraph`, `HopfPID`, `MetricLogger`) | not required by the sweep |
| the other VNES-Lab experiments | separate surfaces |
| `substrate_echo`'s other 12 modules | not required; the sweep needs two symbols from one file |
| the Model Characteristics Registry, capability graphs, ledgers | unrelated estate state |

## Verification

```console
$ cogeco-sweep reproduce --seed 42
$ python -m pytest -q
```

`reproduce` is the check that matters: it runs the sweep more than once at the
same seed and compares the artifacts byte for byte. A claim of reproducibility
that is not tested is a hope.
