# cogeco-phase-sweep

**Does a constraint-governance simulation show regime boundaries in its parameter
space — and can you reproduce the answer?**

A governance simulation, swept over two policy parameters, classified into five
regimes. Reproducible from a seed, with a command that proves it.

```console
$ cogeco-sweep run --seed 42
==========================================================================
  CoGeCo - Regulatory Phase Sweep
==========================================================================
  seed            : 42
  grid            : 49 points (7x7)
  ticks per point : 500
  constraints     : 4

    PHASE DIAGRAM

    Revision Cooldown ->
           0.10   0.20   0.30   0.40   0.50   0.60   0.70
    ------
  400.00|  F    F    F    A    A    A    A
  300.00|  F    F    F    A    A    A    A
  200.00|  C    C    C    A    A    A    A
  100.00|  C    C    C    C    A    A    A
    10.0|  C    C    C    C    C    C    C
    Legend: F=FROZEN C=CHAOTIC S=STABLE A=ADAPTIVE X=COLLAPSED .=UNKNOWN

  --- MODEL-CONSISTENCY CHECKS ---
  These compare this run against what THIS MODEL already predicts.
  They are internal consistency checks, not external validation.
  Nothing here is compared against real data or an independent
  implementation, and no claim beyond this model is supported.

  [CONSISTENT_WITH_THIS_MODEL] Moderate constraint revision with low rollback
  produces stable adaptive regulatory regimes...
```

---

## Contents

- [Install](#install)
- [Run it](#run-it)
- [Reproducibility](#reproducibility)
- [What the labels mean](#what-the-labels-mean)
- [Commands](#commands)
- [Figures](#figures)
- [Historical artifacts](#historical-artifacts)
- [Tests](#tests)
- [Known limits](#known-limits)
- [License](#license)

---

## Install

```console
$ git clone https://github.com/EchoSystems-Foundation/cogeco-phase-sweep
$ cd cogeco-phase-sweep
$ python -m venv .venv
$ .venv/bin/pip install .
```

One runtime dependency: `numpy`, needed by the metric. Add `[plots]` for the
figures:

```console
$ .venv/bin/pip install ".[plots]"
```

Python 3.11 or newer. **The sweep itself is standard library only** — a test
enforces that.

## Run it

```console
$ cogeco-sweep run --seed 42      # sweep, write the result artifact
$ cogeco-sweep plot               # render figures from that artifact
$ cogeco-sweep reproduce --seed 42  # run twice, prove the artifacts match
```

The whole sweep takes well under a second. `reproduce` runs it more than once.

## Reproducibility

This is the part the package is really about.

**Before this package, the sweep was not reproducible.** The revision path called
the module-level `random.random()`, while the `seed` argument seeded a different
stream that governed only shock injection. Five runs of the same code at the
same seed produced five different results, and no seed could reproduce any
published number.

That is fixed, and the fix is checkable rather than asserted:

```console
$ cogeco-sweep reproduce --seed 42
  run 1: 33b077f6f5a283c45aac2315114cc94abc86ab97dd209a558f90a156cba887c2
  run 2: 33b077f6f5a283c45aac2315114cc94abc86ab97dd209a558f90a156cba887c2

  REPRODUCIBLE      : yes - 2 runs, 1 distinct artifact
```

The guarantee is narrow and precise:

| Property | Guarantee |
|---|---|
| same code + parameters + seed | **byte-identical** result artifact |
| different seeds | **may** differ — not required, not forbidden |
| global `random` stream | never used for a simulation decision |

The middle row is deliberately weak. Some parameterisations are attractors, and a
seed-insensitive point is a real finding rather than a defect. A test asserting
that every seed differs would encode a falsehood.

Wall-clock runtime is deliberately **excluded** from the artifact. It used to be
written as `elapsed_seconds`, which made every file unique and every diff
meaningless. It is still shown to you, labelled as operational metadata.

## What the labels mean

The five registers are kept distinct, because the fastest way to overstate a
result is to blur which kind of statement you are making.

| Register | What it is |
|---|---|
| **OBSERVATION** | a number the simulation produced |
| **DERIVED METRIC** | a number computed from observations by a stated formula |
| **MODEL-CONSISTENCY RESULT** | agreement with what **this model** already predicts |
| **INTERPRETATION** | a reading that goes beyond the observations |
| **HYPOTHESIS** | a claim this sweep does not test |

Every run prints which register each statement belongs to.

### Why not `SUPPORTED`?

The sweep previously printed `[SUPPORTED]` next to three hypotheses. That was
wrong in a specific way: those checks compare this simulation against **this
model's own predictions**. Reproducing a model's prediction cannot establish that
the model is correct about anything outside itself. The model could be
confidently, reproducibly, and comprehensively wrong.

Nothing here is compared against experimental data, an independent
implementation, or any real system. So the label is
`CONSISTENT_WITH_THIS_MODEL`, and a test fails if `SUPPORTED` reappears.

**Determinism is not validation.** A reproducible wrong answer is still wrong.

## Commands

| Command | Does |
|---|---|
| `run` | execute the sweep, write the deterministic artifact |
| `plot` | render PNGs **from that artifact** — never re-runs the simulation |
| `reproduce` | run repeatedly at one seed and compare artifacts byte for byte |

`run` takes `--seed`, `--out`, `--verbose`. `plot` takes `--artifact`,
`--outdir`. `reproduce` takes `--seed`, `--rounds`.

Exit codes: `0` success, `1` reproducibility check failed, `64` bad invocation.

## Figures

`plot` reads the result artifact and writes three PNGs:

```
figures/phase_diagram.png           regime map over the two swept parameters
figures/plasticity_heatmap.png      derived plasticity across the grid
figures/revision_rollback_scatter.png  every swept point, coloured by regime
```

Headless (`Agg` backend), so they generate on a machine with no display.

**A figure can never disagree with the numbers it claims to show**, because it is
drawn from the same artifact the run wrote, and never from a second simulation.

## Historical artifacts

The JSON files under `historical/` were generated **before** the reproducibility
repair, while the revision path drew from an uncontrolled stream.

Each is stamped `REPRODUCIBILITY_STATUS = NOT_ESTABLISHED`. They are retained for
provenance. **Their values are not reproducibility evidence and will not match a
fresh run.** That difference is the finding, not a regression.

## Tests

```console
$ python -m pytest -q
32 passed
```

The tests assert properties, not outputs. There is no test that pins a regime
count, a matrix element, or a diagram cell — those are outputs of a stochastic
model, and asserting them would fail on any legitimate correction while catching
nothing.

What is asserted:

- **seed reproducibility** — same seed, byte-identical artifact
- **seed sensitivity** — different seeds *may* differ; nothing stronger
- **RNG ownership** — parsed with `ast`, so a *call* to the global stream fails
  but a mention in a docstring does not
- **metric execution** — `to_metric()` routes through the shipped bridge,
  proven by intercepting the call
- **metric structure** — shape, symmetry, finiteness, positive-definiteness,
  `epsilon` scaling anisotropy linearly, coherence lowering the floor
  monotonically
- **result language** — the source may not contain an unqualified `SUPPORTED`
- **the sweep needs nothing outside the standard library**
- **no shipped file references a private source tree** (tokenised, so provenance
  prose is not a false positive)

## Known limits

Stated plainly, because a phase diagram invites over-reading.

1. **Not validated against data.** No observation, no real system.
2. **Not compared to another implementation.** One implementation, one model family.
3. **Not a claim about governance.** A claim about a toy simulation's parameter space.
4. **Grid-limited.** 7x7. A boundary is resolved to one grid step, and no finer.
5. **Seed-sensitive.** The regime map moves between seeds. Always report the seed.
6. **Timestep-sensitive.** All rates are per tick; changing the tick budget can move a
   point across a boundary with no change to the dynamics.
7. **The metric's meaning is inherited.** Whether the tensor corresponds to any
   measurable geometric quantity is not established here.

One discrepancy is recorded rather than silently corrected: the bridge's docstring
says low coherence makes the metric "anisotropic", but measured, the eigenvalue
*shape* does not change — coherence controls the overall scale while `epsilon`
controls the anisotropy. See [`docs/METRICS.md`](docs/METRICS.md).

## Documentation

- [`docs/METRICS.md`](docs/METRICS.md) — registers, definitions, metric structure,
  seed and timestep dependence, and what is not established
- [`docs/PROVENANCE.md`](docs/PROVENANCE.md) — source paths, hashes, every change
  made during extraction, and the bridge's provenance
- [`historical/`](historical/) — pre-repair outputs, stamped not-established

## License

**Apache-2.0.** See [`LICENSE`](LICENSE).

No license file was added to, or modified in, any internal source repository as
part of this work.
