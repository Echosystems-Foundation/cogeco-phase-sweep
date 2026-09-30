"""``cogeco-sweep`` — the command line for the regulatory phase sweep.

Three commands, in the order a reader should meet them:

``run``
    Execute the sweep and write the deterministic result artifact.

``plot``
    Render PNGs *from that artifact*. Never re-runs the simulation, so a plot
    can never disagree with the numbers it claims to show.

``reproduce``
    Run twice and prove the artifacts are byte-identical. This is the command
    that makes a reproducibility claim checkable rather than asserted.

Every report carries its seed and configuration. A result without them is not
interpretable, and a result without a seed is not reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import sweep as _sweep

DEFAULT_ARTIFACT = "cogeco_sweep_results.json"

EXIT_OK = 0
EXIT_REPRODUCTION_FAILED = 1
EXIT_USAGE = 64


class _Parser(argparse.ArgumentParser):
    """argparse hardcodes exit 2, which collides with nothing here but is still
    surprising. Keep the documented bad-invocation code."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file="sys.stderr")
        raise SystemExit(EXIT_USAGE)


def _artifact_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_artifact(
    report: Any, path: Path, seed: int, status: str = "ESTABLISHED"
) -> Path:
    _sweep.save_report_json(
        report, path=str(path), seed=seed, reproducibility_status=status
    )
    return path


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #


def cmd_run(args: argparse.Namespace) -> int:
    config = _sweep.PhaseSweepConfig.focused2d()
    print("=" * 68)
    print('  CoGeCo - Regulatory Phase Sweep')
    print("=" * 68)
    print(f"  seed            : {args.seed}")
    print(f"  grid            : {config.total_combinations()} points "
          f"({len(config.rollout_threshold)}x{len(config.revision_cooldown)})")
    print(f"  swept axes      : rollback threshold x revision cooldown")
    print(f"  ticks per point : {config.total_ticks}")
    print(f"  constraints     : {config.constraint_count}")
    print()

    runner = _sweep.RegulatoryPhaseSweep(config, seed=args.seed)
    report = runner.run()

    print()
    print(report.to_report(detailed=args.verbose))

    print()
    print("  --- MODEL-CONSISTENCY CHECKS ---")
    print("  These compare this run against what THIS MODEL already predicts.")
    print("  They are internal consistency checks, not external validation.")
    print("  Nothing here is compared against real data or an independent")
    print("  implementation, and no claim beyond this model is supported.")
    print()
    for hypothesis in _sweep.SweepTheoryBridge.evaluate(report):
        print(f"  [{hypothesis.register}] {hypothesis.description}")
        for item in hypothesis.evidence:
            print(f"    - {item}")
        print(f"    model-consistency score: {hypothesis.confidence:.2f}")
    print()

    _sweep.run_basin_analysis(report)

    out = Path(args.out)
    _write_artifact(report, out, seed=args.seed)
    print()
    print(f"  OBSERVATION  regime counts, phase diagram, basin statistics")
    print(f"  DERIVED      revision_rate, rollback_rate, plasticity_score, system_health")
    print(f"               (computed from the tick loop; definitions in docs/METRICS.md)")
    print(f"  REGISTER     model-consistency labels above; these compare this run")
    print(f"               against this model's own predictions and nothing else")
    print(f"  INTERPRETATION  a phase diagram in parameter space, not a claim about")
    print(f"               real governance systems")
    print(f"  HYPOTHESIS   that regime labels correspond to observable behavioural")
    print(f"               differences. Untested here: see docs/METRICS.md.")
    print()
    print(f"  artifact     : {out}")
    print(f"  sha256       : {_artifact_digest(out)}")
    print(f"  seed         : {args.seed}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# plot
# --------------------------------------------------------------------------- #


def cmd_plot(args: argparse.Namespace) -> int:
    """Render from the artifact. Never re-runs the simulation."""
    src = Path(args.artifact)
    if not src.exists():
        print(
            f"error: no result artifact at {src}\n"
            f"       run 'cogeco-sweep run --seed 42' first",
            file=sys.stderr,
        )
        return EXIT_USAGE
    data = json.loads(src.read_text(encoding="utf-8"))
    if data.get("reproducibility_status") != "ESTABLISHED":
        print(
            f"warning: artifact reproducibility_status is "
            f"{data.get('reproducibility_status')!r}, not ESTABLISHED",
            file=sys.stderr,
        )
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    from . import plot as _plot

    _plot.main(src.as_posix(), str(outdir))
    print()
    print(f"  derived from  : {src}")
    print(f"  artifact seed : {data.get('seed')}")
    print(f"  output dir    : {outdir}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# reproduce
# --------------------------------------------------------------------------- #


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Run the sweep twice at the same seed and compare the artifacts byte for byte.

    This is the check that matters. A claim of reproducibility that is not
    tested is a hope.
    """
    config = _sweep.PhaseSweepConfig.focused2d()

    print("=" * 68)
    print("  REPRODUCIBILITY CHECK")
    print("=" * 68)
    print(f"  seed              : {args.seed}")
    print(f"  grid              : {config.total_combinations()} points")
    print(f"  comparisons       : {args.rounds}")
    print()

    import contextlib
    import io

    digests: list[str] = []
    for i in range(args.rounds):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report = _sweep.RegulatoryPhaseSweep(config, seed=args.seed).run()
        tmp = Path(args.workdir) / f"round{i}.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        _write_artifact(report, tmp, seed=args.seed)
        digest = _artifact_digest(tmp)
        digests.append(digest)
        print(f"  run {i+1}: {digest}")

    identical = len(set(digests)) == 1
    print()
    if identical:
        print(f"  REPRODUCIBLE      : yes - {args.rounds} runs, 1 distinct artifact")
        print(f"  sha256            : {digests[0]}")
        print()
        print("  OBSERVATION       identical artifacts across runs at the same seed")
        print("  INTERPRETATION    the sweep is deterministic given (code,")
        print("                    parameters, seed). That is NOT the same as a")
        print("                    validated model; docs/METRICS.md sets out what")
        print("                    determinism does and docs/METRICS.md sets out what determinism does and does not establish.")
        print()
        return EXIT_OK

    print('  REPRODUCIBLE      : NO - ')
    print()
    print("  A sweep at one seed produced different artifacts. The stochastic")
    print("  path is not fully owned by the seeded stream.")
    return EXIT_REPRODUCTION_FAILED


# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="cogeco-sweep",
        description=(
            "CoGeCo regulatory phase sweep: does a constraint-governance "
            "simulation show regime boundaries in its parameter space?"
        ),
        epilog=(
            "Register labels in the output are model-consistency checks against "
            "this model's own predictions. They are not external validation."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    run = sub.add_parser("run", help="execute the sweep and write the result artifact")
    run.add_argument("--seed", type=int, default=42,
                     help="seed for every stochastic decision (default: 42)")
    run.add_argument("--out", default=DEFAULT_ARTIFACT, help="result artifact path")
    run.add_argument("--verbose", action="store_true", help="list every swept point")
    run.set_defaults(func=cmd_run)

    plot = sub.add_parser("plot", help="render PNGs from the result artifact")
    plot.add_argument("--artifact", default=DEFAULT_ARTIFACT,
                      help="result artifact to read (never re-runs the simulation)")
    plot.add_argument("--outdir", default="figures", help="output directory")
    plot.set_defaults(func=cmd_plot)

    rep = sub.add_parser("reproduce",
                         help="run twice and prove the artifacts are identical")
    rep.add_argument("--seed", type=int, default=42, help="seed to reproduce at")
    rep.add_argument("--rounds", type=int, default=2, help="how many runs to compare")
    rep.add_argument("--workdir", default=".", help="where to write the compared artifacts")
    rep.set_defaults(func=cmd_reproduce)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
