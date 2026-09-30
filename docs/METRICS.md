# Metrics, registers, and what this sweep does not show

Written for a reader who wants to know which claims are load-bearing.

## The five registers

Every claim this package makes belongs to exactly one of these. Mixing them is
how a reproducibility result becomes a scientific claim.

| Register | What it is | Example in the output |
|---|---|---|
| **OBSERVATION** | Something the simulation produced. A number it computed. | `revision_rate=0.3760`, `FROZEN=6 CHAOTIC=13 STABLE=8 ADAPTIVE=22` |
| **DERIVED METRIC** | A number computed *from* observations by a stated formula. | `system_health`, `plasticity_score` |
| **MODEL-CONSISTENCY RESULT** | Agreement between this run and what this model already predicts. | `[CONSISTENT_WITH_THIS_MODEL]` |
| **INTERPRETATION** | A reading of the observations that goes beyond them. | "a phase diagram in parameter space" |
| **HYPOTHESIS** | A claim this sweep does not test. | "regime labels track real behavioural differences" |

The register labels in the CLI output are printed in this order at the end of
every run, so a reader never has to guess which kind of statement they are
looking at.

### Why `CONSISTENT_WITH_THIS_MODEL` and not `SUPPORTED`

The sweep previously printed `SUPPORTED` for three hypotheses. That was wrong,
and wrong in a specific way.

Those three checks compare this simulation's output against **this model's own
predictions**. Reproducing a model's prediction cannot establish that the model
is correct about anything outside itself — the model could be confidently,
reproducibly, and comprehensively wrong.

Nothing in this sweep is compared against:

- experimental or observational data
- an independent implementation of the same dynamics
- a fit to any real system
- any prior published result

So the strongest honest label is the one now used. `SUPPORTED`/`UNSUPPORTED` is
rejected outright by `test_the_code_never_prints_an_unqualified_supported_verdict`,
which parses the source and fails on the literals rather than trusting a string
in the report.

The `supported: bool` field became `register: str`. A boolean forces the caller
to choose between two readings, and the previous CLI chose the wrong one. A
label that is only one of the three honest options cannot be read that way.

## Definitions

### Pillar State Vector

A state is 16 pillar angles `theta` in `[0, pi]`, plus a periodic phase `phi`.
`NUM_PILLARS = 16`, `TAU = 2*pi`.

`theta` is bounded by `clamp()`. `phi` is periodic modulo `TAU`. A state built
with the wrong number of components is refused: the metric derived from it is
16x16, and has no meaning at another size.

### The metric

`PillarState.to_metric(epsilon=0.1, coherence_weight=0.3)` returns a 16x16
symmetric positive-definite matrix computed by `bridges.compute_metric_from_bloch`.

The construction is

```
G = (1 - a) * (I + eps * s s^T) + a * I
```

where `a = coherence_weight * (1 - coherence)` and `s` is the normalised pillar
value vector. Consequences, each asserted as a test rather than a value:

| Property | Assertion |
|---|---|
| shape | `(16, 16)` |
| symmetric | `G == G.T` |
| finite | no NaN, no inf |
| positive definite | `min(eigvalsh(G)) > 0` |
| floor bounded below | `min(eigvalsh(G)) >= 1 - coherence_weight` |
| `eps` scales anisotropy | eigenvalue *spread* scales with `eps`; the *floor* does not move |
| `eps = 0` | metric is isotropic |
| `coherence_weight` | the floor decreases monotonically as it rises |

### A discrepancy worth stating

The bridge's own docstring says:

> High coherence → metric isotropic (identity-like, pillars aligned).
> Low coherence → metric anisotropic (distorted by dominant pillar).

Measured, the **shape** does not change. The eigenvalue spread is 0.1 for both a
fully aligned state and a maximally spread state, at `eps=0.1`. What varies with
coherence is the **overall scale** — the floor drops from 1.0 at
`coherence_weight=0` to 0.13 at `0.9`.

So the construction's anisotropy is controlled by `eps`, and coherence controls
the magnitude. The docstring conflates the two. This is recorded rather than
silently corrected, because the bridge is carried across unchanged and its
behaviour is not this package's to redefine; only its documentation here is
clarified.

## Regime classification

A pure threshold function, no randomness:

```
collapsed                      -> COLLAPSED
high_revision  = revision_rate >= 0.01
high_rollback  = rollback_rate >= 0.40
neither                       -> STABLE
revision only                 -> ADAPTIVE
rollback only                 -> FROZEN
both                          -> CHAOTIC
```

`rollback_rate = total_rollbacks / total_revisions`, and is 0.0 when there were
no revisions — never a division error, and never silently treated as infinite.

## Seed dependence

**Every stochastic decision draws from an explicitly owned `random.Random`.**
Before the repair in this package, the revision path called the module-level
`random.random()`, so `seed` governed only shock injection. Two runs at the same
seed produced different numbers, and no published number could be reproduced.
That defect is what this repository exists partly to document.

Guaranteed:

| Property | Guarantee |
|---|---|
| same code + parameters + seed | byte-identical result artifact |
| different seeds | **may** differ — not required, not forbidden |
| global random stream | never used for a simulation decision |

The middle row is deliberately weak. Some parameterisations are attractors; a
seed-insensitive point is a real finding, not a defect. Asserting that every
seed differs would encode a falsehood.

## Timestep dependence

`config.total_ticks` is the per-point tick budget, default 500. All reported
rates are per tick. Regime labels are thresholds on those rates, so:

- changing `total_ticks` can move a point across a regime boundary without any
  change to the underlying dynamics
- the sweep has not been characterised against tick budget; the 7x7 grid result
  is specific to the shipped configuration

The configuration string is recorded in every artifact so a result is
interpretable without reference to the command that produced it.

## Resolution and thresholds

Two independent thresholds define the regimes: `revision_rate >= 0.01` and
`rollback_rate >= 0.40`. Both are asserted at their boundaries in
`test_regime_classification_follows_from_its_thresholds`.

Grid resolution is 7x7 over the two swept axes. **A boundary between adjacent
grid cells is a fact about this grid.** With 7 points per axis, a boundary is
located to within one step and no finer. A finer grid could move a boundary
without contradicting anything here.

## What is NOT established

Stated plainly, because a phase diagram invites over-reading:

1. **Not validated against data.** No observation, no real system.
2. **Not compared to another implementation.** One implementation, one parameterisation.
3. **Not a claim about governance.** It is a claim about a toy simulation's parameter space.
4. **Grid-limited.** 7x7. Boundaries are resolved to one grid step.
5. **Seed-sensitive.** The regime map moves between seeds. Report the seed.
6. **Not sensitive-analysis complete.** Only one sweep of one model family.
7. **The metric's meaning is inherited.** `to_metric` is carried across from
   Substrate Echo. Whether the resulting tensor corresponds to any measurable
   geometric quantity is not established here.

## Historical artifacts

The JSON files under `historical/` were generated **before** the reproducibility
repair, while the revision path drew from an uncontrolled global stream.

They are retained for provenance. **Their numeric values are not reproducibility
evidence**, and `reproducibility_status` in each is `NOT_ESTABLISHED`.

Do not compare them to a fresh run and expect agreement. They will differ. That
difference is the finding, not a regression.
