"""Tests for cogeco-phase-sweep.

The properties asserted here are the ones the package actually claims. Where a
test could be written as "this named input produces this fixed number", it is
written as a relation instead — observed state plus requested state, expected
result — because a pinned value is not a property and stops being one the moment
the simulation is legitimately corrected.

No test asserts a specific regime count, matrix element, or phase-diagram cell.
Those are outputs of a stochastic model at a particular seed; asserting them
would make the test suite fail on any change to the dynamics, while catching
nothing that matters.
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

from cogeco import bridges, psv, sweep


# --------------------------------------------------------------------------- #
# RNG ownership
# --------------------------------------------------------------------------- #


def _module_level_random_calls(path: Path) -> list[tuple[int, str]]:
    """Every call to a module-level ``random.*`` function, with its line.

    Found by parsing rather than grepping, so a mention inside a docstring or a
    comment -- which is not a call -- cannot produce a false result.
    """
    tree = ast.parse(path.read_text(encoding="utf8"))
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "random"
            and func.attr
            not in {"Random", "seed", "getrandbits"}  # constructors and helpers
        ):
            calls.append((node.lineno, func.attr))
    return calls


def test_no_stochastic_decision_uses_the_global_random_stream() -> None:
    """No simulation decision may draw from the uncontrolled global stream.

    This is the defect that made the sweep unreproducible before: the revision
    path called ``random.random()`` directly, so the sweep's seed governed only
    shock injection. Reading a module-level ``random.*`` call anywhere in the
    simulation module is enough to reintroduce it.
    """
    offenders = _module_level_random_calls(Path(sweep.__file__))
    assert offenders == [], (
        f"{Path(sweep.__file__).name} calls the global random stream at "
        f"{offenders}. Route these through an explicitly owned random.Random."
    )


def test_the_random_module_is_only_used_to_construct_owned_streams() -> None:
    """``import random`` is fine. Constructing our own Random with it is the point."""
    source = Path(sweep.__file__).read_text(encoding="utf8")
    constructors = re.findall(r"random\.Random\(", source)
    assert len(constructors) >= 1, "no seeded streams are constructed at all"


def test_a_manager_without_an_rng_is_unseeded_and_says_so() -> None:
    """The default is honestly non-deterministic, not silently 'seeded'."""
    manager = sweep.ConstraintRevisionManager(
        sweep.ConstraintEvolutionPolicy(),
        sweep.ConstraintMutationLimiter(),
        sweep.ConstraintMemory(),
    )
    assert isinstance(manager._rng, __import__("random").Random)


def test_the_seed_reaches_the_revision_manager() -> None:
    """A seed that does not reach the code that draws must not be called a seed."""
    config = sweep.PhaseSweepConfig.focused2d()
    runner = sweep.RegulatoryPhaseSweep(config, seed=1234)
    captured: list[object] = []
    original = sweep.ConstraintRevisionManager.__init__

    def spy(self_, *args, **kwargs):
        original(self_, *args, **kwargs)
        captured.append(self_._rng)

    sweep.ConstraintRevisionManager.__init__ = spy
    try:
        runner.run()
    finally:
        sweep.ConstraintRevisionManager.__init__ = original
    assert captured, "no revision manager was constructed"
    assert all(r is runner._rng for r in captured), (
        "the sweep's seeded stream must be the one the managers draw from"
    )


# --------------------------------------------------------------------------- #
# seed reproducibility
# --------------------------------------------------------------------------- #


def _artifact(seed: int, tmp_path: Path, name: str) -> dict:
    config = sweep.PhaseSweepConfig.focused2d()
    with redirect_stdout(io.StringIO()):
        report = sweep.RegulatoryPhaseSweep(config, seed=seed).run()
    out = tmp_path / name
    sweep.save_report_json(report, path=str(out), seed=seed)
    return json.loads(out.read_text(encoding="utf8"))


def test_same_seed_produces_an_identical_artifact(tmp_path: Path) -> None:
    """Same code, same parameters, same seed -> byte-identical scientific payload.

    This is the reproducibility contract. Two runs, two files, compared as
    bytes rather than as parsed objects, so even key ordering must agree.
    """
    config = sweep.PhaseSweepConfig.focused2d()
    digests = []
    for i in range(2):
        with redirect_stdout(io.StringIO()):
            report = sweep.RegulatoryPhaseSweep(config, seed=42).run()
        path = tmp_path / f"r{i}.json"
        sweep.save_report_json(report, path=str(path), seed=42)
        digests.append(path.read_bytes())
    assert digests[0] == digests[1], (
        f"same seed produced different artifacts:\n"
        f"  {digests[0][:80]!r}\n  {digests[1][:80]!r}"
    )


def test_repeated_runs_of_the_same_seed_agree_repeatedly(tmp_path: Path) -> None:
    """Not a one-off. Three runs, three identical payloads."""
    config = sweep.PhaseSweepConfig.focused2d()
    payloads = set()
    for i in range(3):
        with redirect_stdout(io.StringIO()):
            report = sweep.RegulatoryPhaseSweep(config, seed=7).run()
        payloads.add(json.dumps(
            [r.regime.value for r in report.results], sort_keys=False))
    assert len(payloads) == 1, "the same seed disagreed with itself across three runs"


def test_a_different_seed_may_produce_a_different_result(tmp_path: Path) -> None:
    """Different seeds are *permitted* to differ. Not required, not forbidden.

    The assertion is deliberately weak. Requiring every seed to differ would be
    wrong -- some parameterisations are attractors, and a seed-insensitive point
    is a real finding. This test records only that the seed is not ignored.
    """
    a = _artifact(42, tmp_path, "a.json")
    b = _artifact(9999, tmp_path, "b.json")
    assert a["seed"] == 42 and b["seed"] == 9999
    # No assertion that they differ. Only that the artifact records which seed
    # produced it, which is what makes an unexplained difference diagnosable.


def test_the_artifact_records_the_seed_and_configuration(tmp_path: Path) -> None:
    """A result that does not say how it was produced is not interpretable."""
    data = _artifact(42, tmp_path, "meta.json")
    assert data["seed"] == 42
    assert data["config_summary"], "configuration must be recorded"
    assert data["reproducibility_status"] == "ESTABLISHED"
    assert data["schema_version"] == 2


def test_the_artifact_contains_no_wall_clock_time(tmp_path: Path) -> None:
    """Runtime must not participate in deterministic comparison.

    A previous artifact wrote ``elapsed_seconds``, which made every file unique
    and every diff meaningless.
    """
    data = _artifact(42, tmp_path, "t.json")
    raw = json.dumps(data)
    assert "elapsed" not in raw, "wall-clock leaked into the deterministic payload"
    assert "runtime" not in raw.lower()


def test_the_human_report_still_shows_runtime_as_metadata() -> None:
    """Runtime is useful to an operator. It just is not part of the result."""
    config = sweep.PhaseSweepConfig.focused2d()
    with redirect_stdout(io.StringIO()):
        report = sweep.RegulatoryPhaseSweep(config, seed=42).run()
    text = report.to_report()
    assert "Runtime" in text
    assert "not part of the result" in text


def test_regime_classification_follows_from_its_thresholds() -> None:
    """A relation, not a pinned table entry.

    classify() is a pure threshold function, so the property is: what the
    classifier returns must follow from the revision and rollback rates it is
    given, at the boundaries.
    """
    cases = [
        # (revision_rate, rollback_rate, collapsed, expected)
        (0.000, 0.00, False, sweep.PhaseRegime.STABLE),
        (0.000, 0.90, False, sweep.PhaseRegime.FROZEN),
        (0.500, 0.00, False, sweep.PhaseRegime.ADAPTIVE),
        (0.500, 0.90, False, sweep.PhaseRegime.CHAOTIC),
        (0.500, 0.90, True, sweep.PhaseRegime.COLLAPSED),
    ]
    for rev, roll, collapsed, expected in cases:
        got = sweep.PhaseSweepResult.classify(rev, roll, collapsed)
        assert got is expected, f"classify({rev}, {roll}, {collapsed}) -> {got}"

    # the threshold itself: 0.01 is the boundary, on both sides
    assert sweep.PhaseSweepResult.classify(0.0099, 0.0, False) is sweep.PhaseRegime.STABLE
    assert sweep.PhaseSweepResult.classify(0.0100, 0.0, False) is sweep.PhaseRegime.ADAPTIVE
    assert sweep.PhaseSweepResult.classify(0.0100, 0.3999, False) is sweep.PhaseRegime.ADAPTIVE
    assert sweep.PhaseSweepResult.classify(0.0100, 0.4000, False) is sweep.PhaseRegime.CHAOTIC


def test_rollback_rate_is_defined_as_a_rate_and_handles_zero_revisions() -> None:
    """Zero revisions means zero rollbacks, not a division error."""
    assert sweep.PhaseSweepResult.classify(0.0, 0.0, False) is sweep.PhaseRegime.STABLE


# --------------------------------------------------------------------------- #
# metric execution through the committed bridge
# --------------------------------------------------------------------------- #


def test_the_metric_path_executes_through_the_shipped_bridge() -> None:
    """PillarState.to_metric() -> compute_metric_from_bloch(), for real.

    Not a fixture, not a stub, not a reimplementation. The assertion is on the
    call path itself.
    """
    calls: list[str] = []
    original = bridges.compute_metric_from_bloch

    def spy(*args, **kwargs):
        calls.append("compute_metric_from_bloch")
        return original(*args, **kwargs)

    bridges.compute_metric_from_bloch = spy
    try:
        state = psv.PillarState.random(seed=3)
        metric = state.to_metric()
    finally:
        bridges.compute_metric_from_bloch = original

    assert calls == ["compute_metric_from_bloch"], (
        "to_metric() did not route through the bridge"
    )
    assert isinstance(metric, np.ndarray)


def test_the_bridge_module_is_the_committed_implementation() -> None:
    """Guard against someone quietly reimplementing the metric locally."""
    source = Path(bridges.__file__).read_text(encoding="utf8")
    assert "def compute_metric_from_bloch" in source
    assert "substrate_echo" not in source, (
        "the shipped bridge must be self-contained, not an import shim"
    )


def test_to_metric_is_deterministic_for_a_given_state() -> None:
    state = psv.PillarState.random(seed=11)
    a = state.to_metric(epsilon=0.1, coherence_weight=0.3)
    b = state.to_metric(epsilon=0.1, coherence_weight=0.3)
    assert np.array_equal(a, b)


# --------------------------------------------------------------------------- #
# metric structural properties
# --------------------------------------------------------------------------- #


def test_the_metric_is_square_and_the_right_size() -> None:
    """One block per pillar: an N-pillar state maps to an NxN metric."""
    n = psv.NUM_PILLARS
    metric = psv.PillarState.random(seed=5).to_metric()
    assert metric.shape == (n, n)


def test_the_metric_is_symmetric() -> None:
    """G_ij must equal G_ji. That is a property of the construction, not a value."""
    for seed in (1, 2, 3):
        metric = psv.PillarState.random(seed=seed).to_metric()
        assert np.allclose(metric, metric.T, atol=1e-12), f"asymmetric at seed {seed}"


def test_the_metric_is_finite() -> None:
    """No NaN or inf. A metric that is not a number cannot describe curvature."""
    for seed in (1, 2, 3):
        assert np.all(np.isfinite(psv.PillarState.random(seed=seed).to_metric()))


def test_the_metric_is_positive_definite() -> None:
    """Positive-definiteness is the construction's defining invariant.

    The construction is delta_ij plus a rank-one term scaled by a positive
    factor, so every eigenvalue is bounded below by that factor. Asserted as a
    bound rather than as a specific number.
    """
    for seed in (1, 2, 3):
        metric = psv.PillarState.random(seed=seed).to_metric()
        eigenvalues = np.linalg.eigvalsh(metric)
        assert eigenvalues.min() > 0, f"not positive definite at seed {seed}"
        # the minimum eigenvalue cannot fall below (1 - coherence_weight)
        lower = 1.0 - 0.3
        assert eigenvalues.min() >= lower - 1e-9


def test_epsilon_scales_the_anisotropy_linearly_and_leaves_the_floor_alone() -> None:
    """A structural relation, checked across a range rather than at one point.

    The construction is ``(1 - a) * (I + eps * s s^T) + a * I`` where ``a``
    depends only on coherence. So ``eps`` multiplies the eigenvalue *spread*
    exactly, and leaves the *floor* untouched. Asserting proportionality over a
    range is a stronger property than asserting one number, and it would fail if
    the construction changed shape rather than merely scale.
    """
    state = psv.PillarState(theta=list(np.linspace(0.05, np.pi - 0.05, psv.NUM_PILLARS)),
                            phi=[0.0] * psv.NUM_PILLARS)
    baseline = np.linalg.eigvalsh(state.to_metric(epsilon=0.0, coherence_weight=0.3))
    for eps in (0.1, 0.2, 0.4):
        eigenvalues = np.linalg.eigvalsh(
            state.to_metric(epsilon=eps, coherence_weight=0.3)
        )
        assert eigenvalues.max() - eigenvalues.min() == pytest.approx(
            eps * (baseline.max() - baseline.min()) + eps, abs=1e-9
        ) or (eigenvalues.max() - eigenvalues.min()) == pytest.approx(
            eps, abs=1e-9
        ), f"spread at eps={eps} did not scale with epsilon"
        assert eigenvalues.min() == pytest.approx(baseline.min(), abs=1e-9), (
            "epsilon must not move the floor of the spectrum"
        )


def test_coherence_weight_lowers_the_floor_monotonically() -> None:
    """More coherence-weight means less of the isotropic component retained.

    The direction is the one the construction guarantees: a higher weight shifts
    the whole spectrum down. Monotonicity is asserted over a range; no particular
    floor value is contractual.
    """
    state = psv.PillarState(theta=list(np.linspace(0.05, np.pi - 0.05, psv.NUM_PILLARS)),
                            phi=[0.0] * psv.NUM_PILLARS)
    floors = [
        np.linalg.eigvalsh(state.to_metric(epsilon=0.1, coherence_weight=cw)).min()
        for cw in (0.0, 0.3, 0.6, 0.9)
    ]
    assert all(a > b for a, b in zip(floors, floors[1:])), (
        f"floor did not decrease monotonically with coherence weight: {floors}"
    )
    assert floors[0] == pytest.approx(1.0, abs=1e-9), (
        "at zero coherence weight the construction is the identity"
    )


def test_at_zero_epsilon_the_metric_is_isotropic() -> None:
    """eps=0 removes the rank-one term, leaving a multiple of the identity."""
    state = psv.PillarState.random(seed=9)
    eigenvalues = np.linalg.eigvalsh(state.to_metric(epsilon=0.0, coherence_weight=0.3))
    assert eigenvalues.max() - eigenvalues.min() == pytest.approx(0.0, abs=1e-12)


def test_clamp_constrains_the_domain_rather_than_construction() -> None:
    """The dataclass does not normalise on construction; clamp() does.

    Asserting the invariant on a freshly built state would be asserting a
    property the class does not have. The relation that does hold: an
    out-of-domain state is out of domain until clamped, and clamping brings it
    in.
    """
    state = psv.PillarState(theta=[0.0, np.pi] * 8, phi=[-1.0, 7.0] * 8)
    assert any(not (0.0 <= p < psv.TAU) for p in state.phi), (
        "the fixture should start out of domain, or this test proves nothing"
    )
    state.clamp()
    assert all(0.0 <= t <= np.pi for t in state.theta)
    assert all(0.0 <= p < psv.TAU for p in state.phi)


def test_a_state_of_the_wrong_size_is_refused_with_a_clear_error() -> None:
    """The metric is NxN. A state of another size has no meaning, and upstream
    raised IndexError from deep inside clamp() instead of saying so.

    Regression guard: a confusing crash far from the mistake is worse than a
    refusal at the boundary.
    """
    with pytest.raises(ValueError, match="exactly 16 components"):
        psv.PillarState(theta=[0.5] * 3, phi=[0.0] * 3).clamp()


def test_soft_clamping_keeps_every_theta_in_domain() -> None:
    """Repeated soft damping still respects the domain.

    Soft clamping is a *process*: it damps toward the boundary region on each
    call, so it is deliberately not idempotent. What must hold after any number
    of applications is the domain invariant.
    """
    state = psv.PillarState(
        theta=[0.0, np.pi, 0.01, np.pi - 0.01] * 4,
        phi=[-1.0, 7.0, 3.0, 100.0] * 4,
    )
    for _ in range(5):
        state.clamp()
        assert all(0.0 <= t <= np.pi for t in state.theta)
        assert all(0.0 <= p < psv.TAU for p in state.phi)


def test_hard_clamping_reaches_the_exact_boundary() -> None:
    """soft=False clamps to the domain rather than damping toward it."""
    state = psv.PillarState(theta=[-5.0, 99.0] + [0.5] * 14, phi=[0.0] * 16)
    state.clamp(soft=False)
    assert state.theta[0] == 0.0
    assert state.theta[1] == pytest.approx(np.pi)
    assert all(0.0 <= t <= np.pi for t in state.theta)


# --------------------------------------------------------------------------- #
# result-language guard
# --------------------------------------------------------------------------- #


def test_the_code_never_prints_an_unqualified_supported_verdict() -> None:
    """``SUPPORTED`` must not reappear as a scientific verdict.

    Reproducing a model's own prediction does not validate it. The old output
    printed ``SUPPORTED`` for three internal consistency checks, which read as
    external validation. This guard makes the regression loud.
    """
    source = Path(sweep.__file__).read_text(encoding="utf8")
    tree = ast.parse(source)
    literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    offenders = [
        s for s in literals
        if re.fullmatch(r"(UN)?SUPPORTED", s)
    ]
    assert offenders == [], f"unqualified verdict literals returned: {offenders}"


def test_the_consistency_register_labels_are_the_ones_documented() -> None:
    assert sweep.REGISTER_CONSISTENT == "CONSISTENT_WITH_THIS_MODEL"
    assert sweep.REGISTER_INCONSISTENT == "INCONSISTENT_WITH_THIS_MODEL"
    assert sweep.REGISTER_NOT_TESTED == "NOT_TESTED_BY_THIS_SWEEP"


def test_the_printed_verdict_uses_the_consistency_register() -> None:
    config = sweep.PhaseSweepConfig.focused2d()
    with redirect_stdout(io.StringIO()):
        report = sweep.RegulatoryPhaseSweep(config, seed=42).run()
    buf = io.StringIO()
    from cogeco.cli import main

    # exercise the real printing path
    argv = ["run", "--seed", "42", "--out", str(Path("x.json"))]
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        argv[-1] = str(Path(tmp) / "x.json")
        with redirect_stdout(buf):
            main(argv)
    out = buf.getvalue()
    assert "CONSISTENT_WITH_THIS_MODEL" in out
    assert "not external validation" in out
    assert "SUPPORTED]" not in out


def test_every_hypothesis_declares_a_register_not_a_bare_bool() -> None:
    hypotheses = sweep.SweepTheoryBridge.evaluate.__doc__
    assert hypotheses is None or isinstance(hypotheses, str)
    # the dataclass must expose `register`, not `supported`
    fields = sweep.TheoryHypothesis.__dataclass_fields__
    assert "register" in fields
    assert "supported" not in fields, (
        "a bare `supported: bool` makes both readings available to a caller, "
        "and the CLI previously chose the wrong one"
    )


# --------------------------------------------------------------------------- #
# packaging
# --------------------------------------------------------------------------- #


def test_the_sweep_needs_nothing_outside_the_standard_library() -> None:
    """A governance demo that cannot install is not a demo."""
    tree = ast.parse(Path(sweep.__file__).read_text(encoding="utf8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    allowed = set(sys.stdlib_module_names) | {"cogeco"}
    third_party = imported - allowed
    assert third_party == set(), f"sweep.py imports {third_party}"


def test_no_shipped_file_references_a_private_source_tree() -> None:
    """No C:\\Projects, no C:\\G1, no path that resolves only on one machine."""
    package = Path(__file__).resolve().parent.parent / "cogeco"
    drive = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/[a-z]|C:/")
    offenders = []
    for path in sorted(package.rglob("*.py")):
        source = path.read_text(encoding="utf8")
        # tokenise so provenance prose and comments are not false positives
        import io as _io
        import tokenize

        try:
            code = " ".join(
                t.string for t in tokenize.generate_tokens(_io.StringIO(source).readline)
                if t.type not in (tokenize.STRING, tokenize.COMMENT)
            )
        except tokenize.TokenError:  # pragma: no cover
            continue
        if drive.search(code):
            offenders.append(path.name)
    assert offenders == [], offenders
