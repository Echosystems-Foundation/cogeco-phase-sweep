"""CoGeCo Regulatory Phase Sweep — pure Python implementation.

Port of the Java CoGeCo (Constraint-based Governance of Cognitive Ecologies)
phase diagram sweep. Explores the revision rate x rollback threshold parameter
space to identify FROZEN, STABLE, ADAPTIVE, CHAOTIC, and COLLAPSED regimes.

Usage:
    python cogeco_sweep.py
"""

import math
import random
import sys
import os
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─── Phase Regime Classification ───────────────────────────────────────

class PhaseRegime(Enum):
    FROZEN    = "FROZEN"      # Low revision, high rollback
    CHAOTIC   = "CHAOTIC"     # High revision, high rollback
    STABLE    = "STABLE"      # Low revision, low rollback
    ADAPTIVE  = "ADAPTIVE"    # High revision, low rollback
    COLLAPSED = "COLLAPSED"   # System collapsed
    UNKNOWN   = "UNKNOWN"     # Insufficient data

    def symbol(self) -> str:
        return {
            PhaseRegime.FROZEN:    "F",
            PhaseRegime.CHAOTIC:   "C",
            PhaseRegime.STABLE:    "S",
            PhaseRegime.ADAPTIVE:  "A",
            PhaseRegime.COLLAPSED: "X",
            PhaseRegime.UNKNOWN:   ".",
        }[self]


# ─── Phase Sweep Configuration ─────────────────────────────────────────

@dataclass
class SweepPoint:
    rollout_threshold: float = 0.15
    revision_cooldown: int = 100
    max_mutation_size: float = 0.2
    stability_resistance: float = 0.5
    constraint_budget: float = 20.0
    enforcement_cost: float = 0.05
    false_positive_penalty: float = 0.5
    shock_frequency: int = 100
    shock_magnitude: float = 0.3
    resource_volatility: float = 0.2

    def to_key(self) -> str:
        k = self.__dict__
        return f"RT={k['rollout_threshold']:.2f}|CD={k['revision_cooldown']}|MM={k['max_mutation_size']:.2f}|SR={k['stability_resistance']:.2f}|CB={k['constraint_budget']:.1f}|EC={k['enforcement_cost']:.2f}|FP={k['false_positive_penalty']:.2f}|SF={k['shock_frequency']}|SM={k['shock_magnitude']:.2f}|RV={k['resource_volatility']:.2f}"

    def to_short_key(self) -> str:
        return f"RT={self.rollout_threshold:.2f}_CD={self.revision_cooldown}"


class PhaseSweepConfig:
    def __init__(self):
        self.rollout_threshold: list[float] = [0.05, 0.15, 0.3, 0.5]
        self.revision_cooldown: list[int] = [10, 50, 100, 200, 500]
        self.max_mutation_size: list[float] = [0.05, 0.1, 0.2, 0.4]
        self.stability_resistance: list[float] = [0.3, 0.5, 0.8, 1.0]
        self.constraint_budget: list[float] = [5, 10, 20, 50]
        self.enforcement_cost: list[float] = [0.01, 0.05, 0.1, 0.2]
        self.false_positive_penalty: list[float] = [0.1, 0.5, 1.0, 2.0]
        self.shock_frequency: list[int] = [20, 50, 100, 200]
        self.shock_magnitude: list[float] = [0.1, 0.3, 0.5, 0.8]
        self.resource_volatility: list[float] = [0.0, 0.2, 0.5, 0.8]
        self.total_ticks: int = 500
        self.constraint_count: int = 4
        self.plasticity_window: int = 100

    @staticmethod
    def focused2d():
        c = PhaseSweepConfig()
        c.rollout_threshold = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]
        c.revision_cooldown = [10, 25, 50, 100, 200, 350, 500]
        c.max_mutation_size = [0.2]
        c.stability_resistance = [0.5]
        c.constraint_budget = [20]
        c.enforcement_cost = [0.05]
        c.false_positive_penalty = [0.5]
        c.shock_frequency = [100]
        c.shock_magnitude = [0.3]
        c.resource_volatility = [0.2]
        return c

    @staticmethod
    def ecology_sweep():
        c = PhaseSweepConfig()
        c.false_positive_penalty = [0.1, 0.3, 0.5, 1.0, 1.5, 2.0]
        c.enforcement_cost = [0.01, 0.03, 0.05, 0.1, 0.15, 0.2]
        c.rollout_threshold = [0.15]
        c.revision_cooldown = [100]
        c.max_mutation_size = [0.2]
        c.stability_resistance = [0.5]
        c.constraint_budget = [20]
        c.shock_frequency = [100]
        c.shock_magnitude = [0.3]
        c.resource_volatility = [0.2]
        return c

    @staticmethod
    def environment_sweep():
        c = PhaseSweepConfig()
        c.shock_magnitude = [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
        c.shock_frequency = [10, 25, 50, 100, 200, 400]
        c.rollout_threshold = [0.15]
        c.revision_cooldown = [100]
        c.max_mutation_size = [0.2]
        c.stability_resistance = [0.5]
        c.constraint_budget = [20]
        c.enforcement_cost = [0.05]
        c.false_positive_penalty = [0.5]
        c.resource_volatility = [0.2]
        return c

    def total_combinations(self) -> int:
        return (len(self.rollout_threshold) *
                len(self.revision_cooldown) *
                len(self.max_mutation_size) *
                len(self.stability_resistance) *
                len(self.constraint_budget) *
                len(self.enforcement_cost) *
                len(self.false_positive_penalty) *
                len(self.shock_frequency) *
                len(self.shock_magnitude) *
                len(self.resource_volatility))

    def get_combination(self, index: int) -> SweepPoint:
        i = index
        p = SweepPoint()
        p.rollout_threshold = self.rollout_threshold[i % len(self.rollout_threshold)]; i //= len(self.rollout_threshold)
        p.revision_cooldown = self.revision_cooldown[i % len(self.revision_cooldown)]; i //= len(self.revision_cooldown)
        p.max_mutation_size = self.max_mutation_size[i % len(self.max_mutation_size)]; i //= len(self.max_mutation_size)
        p.stability_resistance = self.stability_resistance[i % len(self.stability_resistance)]; i //= len(self.stability_resistance)
        p.constraint_budget = self.constraint_budget[i % len(self.constraint_budget)]; i //= len(self.constraint_budget)
        p.enforcement_cost = self.enforcement_cost[i % len(self.enforcement_cost)]; i //= len(self.enforcement_cost)
        p.false_positive_penalty = self.false_positive_penalty[i % len(self.false_positive_penalty)]; i //= len(self.false_positive_penalty)
        p.shock_frequency = self.shock_frequency[i % len(self.shock_frequency)]; i //= len(self.shock_frequency)
        p.shock_magnitude = self.shock_magnitude[i % len(self.shock_magnitude)]; i //= len(self.shock_magnitude)
        p.resource_volatility = self.resource_volatility[i % len(self.resource_volatility)]
        return p

    def summary(self) -> str:
        return (f"Sweep: {len(self.rollout_threshold)}x{len(self.revision_cooldown)}x"
                f"{len(self.max_mutation_size)}x{len(self.stability_resistance)}x"
                f"{len(self.constraint_budget)}x{len(self.enforcement_cost)}x"
                f"{len(self.false_positive_penalty)}x{len(self.shock_frequency)}x"
                f"{len(self.shock_magnitude)}x{len(self.resource_volatility)} = "
                f"{self.total_combinations()} combinations (ticks={self.total_ticks})")


# ─── Constraint Ecology (simplified Python port) ───────────────────────

@dataclass
class ConstraintPopulation:
    uid: str
    fitness: float = 1.0
    enforcement_strength: float = 0.5
    age: int = 0
    violations: int = 0
    false_positives: int = 0

    def tick(self, ecology: "SimpleConstraintEcology", dt: float = 1.0):
        self.age += 1
        budget = ecology._budget
        cost = ecology._enforcement_cost * self.enforcement_strength
        if budget > 0:
            ecological_pressure = 1.0 - budget / ecology._base_budget
            decay = 0.001 + ecological_pressure * 0.01
            self.enforcement_strength *= (1.0 - decay * dt)
        else:
            self.enforcement_strength *= 0.99
        self.enforcement_strength = max(0.0, min(1.0, self.enforcement_strength))
        self.fitness = self.enforcement_strength * (1.0 - 0.1 * self.violations / max(1, self.age))


class SimpleConstraintEcology:
    def __init__(self, config: Optional[PhaseSweepConfig] = None):
        self._populations: dict[str, ConstraintPopulation] = {}
        self._budget: float = 20.0
        self._base_budget: float = 20.0
        self._enforcement_cost: float = 0.05
        self._fp_penalty: float = 0.5
        self._config = config
        self._tick_count: int = 0

    def set_parameters(self, point: SweepPoint):
        self._budget = point.constraint_budget
        self._base_budget = point.constraint_budget
        self._enforcement_cost = point.enforcement_cost
        self._fp_penalty = point.false_positive_penalty

    def register_constraint(self, uid: str) -> ConstraintPopulation:
        pop = ConstraintPopulation(uid=uid)
        self._populations[uid] = pop
        return pop

    def get_population(self, uid: str) -> Optional[ConstraintPopulation]:
        return self._populations.get(uid)

    def all_populations(self) -> list[ConstraintPopulation]:
        return list(self._populations.values())

    def record_violation(self, uid: str, is_real: bool):
        pop = self._populations.get(uid)
        if pop is None:
            return
        if is_real:
            pop.violations += 1
            pop.fitness += 0.05
            pop.enforcement_strength = min(1.0, pop.enforcement_strength + 0.02)
        else:
            pop.false_positives += 1
            penalty = self._fp_penalty * pop.enforcement_strength
            pop.fitness -= penalty
            pop.enforcement_strength = max(0.0, pop.enforcement_strength - 0.03)

        self._budget -= self._enforcement_cost

    def tick(self, dt: float = 1.0):
        self._tick_count += 1
        for pop in self._populations.values():
            pop.tick(self, dt)
        if self._budget < 0:
            for pop in self._populations.values():
                pop.enforcement_strength *= 0.95
        self._budget += 0.01  # slow budget recovery

    def global_fitness_metric(self) -> float:
        if not self._populations:
            return 0.0
        return sum(p.fitness for p in self._populations.values()) / len(self._populations)


class ConstraintMemory:
    def __init__(self):
        self._knowledge: dict[str, dict] = {}

    def get_knowledge(self, uid: str) -> dict:
        if uid not in self._knowledge:
            self._knowledge[uid] = {
                "revision_count": 0,
                "rollback_count": 0,
                "last_revision_tick": -1,
                "last_rollback_tick": -1,
            }
        return self._knowledge[uid]


class ConstraintEvolutionPolicy:
    def __init__(self):
        self.rollback_threshold: float = 0.15
        self.cooldown_ticks: int = 100
        self.max_change_per_revision: float = 0.2
        self.stability_resistance_factor: float = 0.5


class ConstraintMutationLimiter:
    def __init__(self):
        self.rollback_threshold: float = 0.15
        self.min_ticks_between_revisions: int = 100


class ConstraintRevisionManager:
    def __init__(self, policy: ConstraintEvolutionPolicy,
                 limiter: ConstraintMutationLimiter,
                 memory: ConstraintMemory,
                 rng: Optional[random.Random] = None):
        # This class owns the revision stochasticity, so it owns the stream.
        #
        # It used to call the module-level ``random.random()`` directly. The
        # sweep's ``seed`` seeded a different Random that governed only shock
        # injection, so two runs of the same parameter point at the same seed
        # produced different numbers, and no seed could reproduce a published
        # result.
        #
        # With no RNG supplied this is unseeded and therefore non-reproducible.
        # That is the honest default for an interactive caller: nothing silently
        # pretends to be deterministic. Pass one to reproduce.
        self._rng = rng if rng is not None else random.Random()
        self._policy = policy
        self._limiter = limiter
        self._memory = memory
        self._ecology: Optional[SimpleConstraintEcology] = None
        self._total_revisions: int = 0
        self._total_rollbacks: int = 0
        self._last_revision_tick: dict[str, int] = {}
        self._tick: int = 0

    def set_ecology(self, ecology: SimpleConstraintEcology):
        self._ecology = ecology

    def begin_cycle(self, tick: int):
        self._tick = tick
        if self._ecology is None:
            return
        for pop in self._ecology.all_populations():
            knowledge = self._memory.get_knowledge(pop.uid)
            last_tick = self._last_revision_tick.get(pop.uid, -1)
            if tick - last_tick >= self._limiter.min_ticks_between_revisions:
                if self._should_revise(pop, knowledge):
                    self._apply_revision(pop, knowledge)

    def _should_revise(self, pop: ConstraintPopulation, knowledge: dict) -> bool:
        if pop.fitness < 0.3:
            return True
        if pop.enforcement_strength < 0.2:
            return True
        if pop.violations > pop.false_positives + 3:
            return True
        return False

    def _apply_revision(self, pop: ConstraintPopulation, knowledge: dict):
        old_strength = pop.enforcement_strength
        rng = self._rng.random()
        if pop.fitness < 0.2:
            change = self._policy.max_change_per_revision * (0.5 + rng * 0.5)
            if pop.enforcement_strength < 0.5:
                pop.enforcement_strength = min(1.0, pop.enforcement_strength + change)
            else:
                pop.enforcement_strength = max(0.0, pop.enforcement_strength - change * 0.5)
        else:
            change = self._policy.max_change_per_revision * rng * 0.3
            pop.enforcement_strength += (0.5 - pop.enforcement_strength) * 0.1
        pop.enforcement_strength = max(0.0, min(1.0, pop.enforcement_strength))
        self._total_revisions += 1
        knowledge["revision_count"] += 1
        knowledge["last_revision_tick"] = self._tick
        self._last_revision_tick[pop.uid] = self._tick
        if abs(pop.enforcement_strength - old_strength) > self._policy.rollback_threshold:
            self._rollback(pop, knowledge)

    def _rollback(self, pop: ConstraintPopulation, knowledge: dict):
        pop.enforcement_strength = max(0.0, min(1.0, pop.enforcement_strength * 0.8))
        self._total_rollbacks += 1
        knowledge["rollback_count"] += 1
        knowledge["last_rollback_tick"] = self._tick

    def get_total_revisions(self) -> int:
        return self._total_revisions

    def get_total_rollbacks(self) -> int:
        return self._total_rollbacks


class RegulatoryPlasticity:
    def __init__(self):
        self.plasticity_score: float = 0.0

    @staticmethod
    def compute(ecology: SimpleConstraintEcology,
                rm: ConstraintRevisionManager,
                memory: ConstraintMemory,
                constraint_count: int,
                total_ticks: int,
                start_tick: int,
                window: int) -> "RegulatoryPlasticity":
        rp = RegulatoryPlasticity()
        if total_ticks <= 0 or constraint_count <= 0:
            rp.plasticity_score = 0.0
            return rp
        rev_rate = rm.get_total_revisions() / total_ticks
        avg_strength = 0.0
        pops = ecology.all_populations()
        if pops:
            avg_strength = sum(p.enforcement_strength for p in pops) / len(pops)
        fitness = ecology.global_fitness_metric()
        rp.plasticity_score = rev_rate * 2.0 + (1.0 - avg_strength) * 0.3 + fitness * 0.2
        rp.plasticity_score = max(0.0, min(1.0, rp.plasticity_score))
        return rp


# ─── Phase Sweep Result ────────────────────────────────────────────────

@dataclass
class PhaseSweepResult:
    parameters: SweepPoint = field(default_factory=SweepPoint)
    total_revisions: int = 0
    total_rollbacks: int = 0
    revision_rate: float = 0.0
    rollback_rate: float = 0.0
    avg_fitness: float = 0.0
    avg_strength: float = 0.0
    frozen_ratio: float = 0.0
    dominant_ratio: float = 0.0
    plasticity_score: float = 0.0
    system_health: float = 0.0
    collapsed: bool = False
    adaptation_latency: int = -1
    regime: PhaseRegime = PhaseRegime.UNKNOWN

    @staticmethod
    def classify(revision_rate: float, rollback_rate: float, collapsed: bool) -> PhaseRegime:
        if collapsed:
            return PhaseRegime.COLLAPSED
        high_revision = revision_rate >= 0.01
        high_rollback = rollback_rate >= 0.4
        if not high_revision and not high_rollback:
            return PhaseRegime.STABLE
        if high_revision and not high_rollback:
            return PhaseRegime.ADAPTIVE
        if not high_revision and high_rollback:
            return PhaseRegime.FROZEN
        return PhaseRegime.CHAOTIC

    def to_report(self) -> str:
        return (f"  Regime: {self.regime.value:<10}  RevRate: {self.revision_rate:.4f}  "
                f"RollRate: {self.rollback_rate*100:.2f}%  Plasticity: {self.plasticity_score:.4f}\n"
                f"    Fitness: {self.avg_fitness:.4f}  Strength: {self.avg_strength:.4f}  "
                f"Frozen: {self.frozen_ratio*100:.0f}%  Dominant: {self.dominant_ratio*100:.0f}%\n"
                f"    Revisions: {self.total_revisions}  Rollbacks: {self.total_rollbacks}  "
                f"Health: {self.system_health:.4f}  Latency: {self.adaptation_latency}")

    @staticmethod
    def ascii_phase_diagram(results: list[list["PhaseSweepResult"]],
                            x_label: str = "Rollback Threshold",
                            y_label: str = "Revision Cooldown",
                            x_values: Optional[list[float]] = None,
                            y_values: Optional[list[float]] = None) -> str:
        sb = []
        sb.append("    PHASE DIAGRAM\n")
        sb.append(f"    {y_label} ->\n")
        if x_values:
            sb.append("    " + "".join(f"{v:>6.2f}" for v in x_values) + "\n")
        sb.append("    " + "------" * len(results) + "\n")
        for y in range(len(results[0]) - 1, -1, -1):
            label = f"{y_values[y]:>5.2f}|" if y_values else f"{y:>5d}|"
            sb.append(label)
            for x in range(len(results)):
                r = results[x][y]
                sb.append(f"  {r.regime.symbol()}  ")
            sb.append("\n")
        sb.append(f"    {x_label} ->\n")
        sb.append("    Legend: F=FROZEN C=CHAOTIC S=STABLE A=ADAPTIVE X=COLLAPSED .=UNKNOWN\n")
        return "".join(sb)

    @staticmethod
    def regime_summary(results: list["PhaseSweepResult"]) -> str:
        counts = {r: 0 for r in PhaseRegime}
        for r in results:
            counts[r.regime] = counts.get(r.regime, 0) + 1
        parts = [f"{k.value}={v}" for k, v in counts.items()]
        return "    " + "  ".join(parts)


# ─── Regulatory Phase Sweep ────────────────────────────────────────────

class SweepReport:
    def __init__(self):
        self.config: Optional[PhaseSweepConfig] = None
        self.results: list[PhaseSweepResult] = []
        self.total_combinations: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed: float = 0.0

    def to_report(self, detailed: bool = False) -> str:
        sb = []
        sb.append("=" * 60)
        sb.append("  REGULATORY PHASE SWEEP REPORT")
        sb.append("=" * 60)
        sb.append(f"  Config: {self.config.summary() if self.config else 'N/A'}")
        sb.append(f"  Runs completed: {len(self.results)}")
        sb.append(f"  Runtime (operational metadata, not part of the result): "
                 f"{self.elapsed:.3f}s")
        sb.append("")
        sb.append("  --- Phase Distribution ---")
        sb.append(PhaseSweepResult.regime_summary(self.results))

        if self.is_2d_sweep():
            sb.append("")
            sb.append(self.build_2d_phase_diagram())

        sb.append("")
        sb.append("  --- Extremes ---")
        most_adaptive = max((r for r in self.results if r.regime == PhaseRegime.ADAPTIVE),
                           key=lambda r: r.plasticity_score, default=None)
        most_frozen = max((r for r in self.results if r.regime == PhaseRegime.FROZEN),
                         key=lambda r: r.frozen_ratio, default=None)
        most_chaotic = max((r for r in self.results if r.regime == PhaseRegime.CHAOTIC),
                          key=lambda r: r.rollback_rate, default=None)

        for label, r in [("Most adaptive", most_adaptive), ("Most frozen", most_frozen),
                         ("Most chaotic", most_chaotic)]:
            if r:
                sb.append(f"  {label}: {r.parameters.to_short_key()}")
                if detailed:
                    sb.append(r.to_report())
        if detailed:
            sb.append(f"\n  --- All Results ---")
            for i, r in enumerate(self.results):
                sb.append(f"  [{i:3d}] {r.parameters.to_short_key():<20} "
                         f"Regime={r.regime.value:<10} RevRate={r.revision_rate:.4f} "
                         f"RollRate={r.rollback_rate*100:.2f}% Health={r.system_health:.3f}")
        sb.append("=" * 60)
        return "\n".join(sb)

    def is_2d_sweep(self) -> bool:
        if self.config is None:
            return False
        c = self.config
        return (len(c.rollout_threshold) > 1 and
                len(c.revision_cooldown) > 1 and
                all(len(x) == 1 for x in [c.max_mutation_size, c.stability_resistance,
                    c.constraint_budget, c.enforcement_cost, c.false_positive_penalty,
                    c.shock_frequency, c.shock_magnitude, c.resource_volatility]))

    def build_2d_phase_diagram(self) -> str:
        if self.config is None:
            return ""
        c = self.config
        x_size = len(c.rollout_threshold)
        y_size = len(c.revision_cooldown)
        grid = [[PhaseSweepResult(regime=PhaseRegime.UNKNOWN) for _ in range(y_size)]
                for _ in range(x_size)]

        def find_index(arr, val):
            for i, v in enumerate(arr):
                if abs(v - val) < 0.001:
                    return i
            return -1

        for r in self.results:
            x = find_index(c.rollout_threshold, r.parameters.rollout_threshold)
            y = find_index(c.revision_cooldown, float(r.parameters.revision_cooldown))
            if x >= 0 and y >= 0:
                grid[x][y] = r

        return PhaseSweepResult.ascii_phase_diagram(
            grid, "Rollback Threshold", "Revision Cooldown",
            c.rollout_threshold, [float(v) for v in c.revision_cooldown])


class RegulatoryPhaseSweep:
    def __init__(self, config: PhaseSweepConfig, seed: int = 42):
        self.config = config
        self._rng = random.Random(seed)

    def run(self) -> SweepReport:
        report = SweepReport()
        report.config = self.config
        report.start_time = time.time()
        total = self.config.total_combinations()
        report.total_combinations = total

        for i in range(total):
            point = self.config.get_combination(i)
            result = self._run_single(point)
            report.results.append(result)
            if (i + 1) % 10 == 0 or i == total - 1:
                pct = (i + 1) / total * 100
                print(f"  Sweep progress: {i+1}/{total} ({pct:.0f}%)")

        report.end_time = time.time()
        report.elapsed = report.end_time - report.start_time
        return report

    def _run_single(self, point: SweepPoint) -> PhaseSweepResult:
        result = PhaseSweepResult()
        result.parameters = point

        ecology = SimpleConstraintEcology(self.config)
        ecology.set_parameters(point)
        memory = ConstraintMemory()
        policy = ConstraintEvolutionPolicy()
        limiter = ConstraintMutationLimiter()

        policy.rollback_threshold = point.rollout_threshold
        policy.cooldown_ticks = point.revision_cooldown
        policy.max_change_per_revision = point.max_mutation_size
        policy.stability_resistance_factor = point.stability_resistance
        limiter.rollback_threshold = point.rollout_threshold
        limiter.min_ticks_between_revisions = point.revision_cooldown
        # Shares the sweep's seeded stream, so shock draws and revision draws
        # advance one stream in a fixed order.
        rm = ConstraintRevisionManager(policy, limiter, memory, rng=self._rng)

        ids = []
        for ci in range(self.config.constraint_count):
            cid = f"C{ci}"
            ids.append(cid)
            ecology.register_constraint(cid)
            memory.get_knowledge(cid)
        rm.set_ecology(ecology)

        collapsed = False
        first_shock_response = -1
        shock_occurred = False

        for tick in range(self.config.total_ticks):
            ecology.tick(1.0)
            rm.begin_cycle(tick)

            if point.shock_frequency > 0 and tick % point.shock_frequency == 0 and tick > 0:
                shock_occurred = True
                self._apply_shock(ids, ecology, point)

            if tick % 5 == 0:
                for cid in ids:
                    pop = ecology.get_population(cid)
                    if pop is not None and pop.enforcement_strength > 0.1:
                        is_real = pop.enforcement_strength > 0.5
                        ecology.record_violation(cid, is_real)
                        if shock_occurred and first_shock_response < 0 and is_real:
                            first_shock_response = tick

            total_fitness = ecology.global_fitness_metric()
            if total_fitness < -10 and tick > 50:
                collapsed = True
                break

        result.total_revisions = rm.get_total_revisions()
        result.total_rollbacks = rm.get_total_rollbacks()
        result.revision_rate = (result.total_revisions / self.config.total_ticks
                               if self.config.total_ticks > 0 else 0.0)
        result.rollback_rate = (result.total_rollbacks / result.total_revisions
                               if result.total_revisions > 0 else 0.0)
        result.collapsed = collapsed

        pops = ecology.all_populations()
        if pops:
            sum_fit = sum(p.fitness for p in pops)
            sum_str = sum(p.enforcement_strength for p in pops)
            frozen = sum(1 for p in pops if p.enforcement_strength < 0.01)
            dominant = sum(1 for p in pops if p.enforcement_strength > 0.9)
            result.avg_fitness = sum_fit / len(pops)
            result.avg_strength = sum_str / len(pops)
            result.frozen_ratio = frozen / len(pops)
            result.dominant_ratio = dominant / len(pops)

        plasticity = RegulatoryPlasticity.compute(
            ecology, rm, memory, self.config.constraint_count,
            self.config.total_ticks, 0, self.config.plasticity_window)
        result.plasticity_score = plasticity.plasticity_score
        result.system_health = (0.0 if collapsed else
                               max(0.0, min(1.0, 0.5 + result.avg_fitness * 0.2 +
                                   (1.0 - result.rollback_rate) * 0.2 +
                                   result.plasticity_score * 0.1)))
        result.adaptation_latency = (first_shock_response if first_shock_response > 0
                                    else (-1 if shock_occurred else 0))
        result.regime = PhaseSweepResult.classify(
            result.revision_rate, result.rollback_rate, result.collapsed)
        return result

    def _apply_shock(self, ids: list[str], ecology: SimpleConstraintEcology, point: SweepPoint):
        for cid in ids:
            pop = ecology.get_population(cid)
            if pop is not None and pop.enforcement_strength > 0.5:
                if self._rng.random() < point.shock_magnitude * 0.3:
                    ecology.record_violation(cid, False)


# ─── Seed Varied Sweep (Robustness Testing) ────────────────────────────

class SeedStabilityResult:
    def __init__(self):
        self.parameters: Optional[SweepPoint] = None
        self.seed_count: int = 0
        self.seed_results: list[PhaseSweepResult] = []
        self.seed_regimes: list[PhaseRegime] = []
        self.stability_score: float = 0.0
        self.dominant_regime: Optional[PhaseRegime] = None
        self.variation_count: int = 0
        self.is_near_boundary: bool = False
        self.is_reproducible: bool = False

    def to_report(self) -> str:
        sb = []
        sb.append("=== Seed Stability Analysis ===")
        sb.append(f"  Parameters: {self.parameters.to_short_key() if self.parameters else 'N/A'}")
        sb.append(f"  Seeds: {self.seed_count}  Stability: {self.stability_score:.2f}")
        sb.append(f"  Dominant: {self.dominant_regime.value if self.dominant_regime else '?'}  "
                  f"Variations: {self.variation_count}/{self.seed_count}")
        if self.is_near_boundary:
            sb.append("  *** NEAR PHASE BOUNDARY ***")
        elif self.is_reproducible:
            sb.append("  Reproducible attractor")
        sb.append("")
        sb.append("  Per-seed results:")
        for i, r in enumerate(self.seed_results):
            sb.append(f"    Seed {i+1:2d}: {r.regime.value:<10}  "
                     f"revRate={r.revision_rate:.4f}  rollRate={r.rollback_rate*100:.2f}%")
        sb.append("")
        sb.append("  Regime distribution:")
        for regime in PhaseRegime:
            count = sum(1 for r in self.seed_regimes if r == regime)
            if count > 0:
                sb.append(f"    {regime.value:<12} {count}/{self.seed_count} ({count/self.seed_count*100:.0f}%)")
        return "\n".join(sb)


class SeedVariedSweep:
    def __init__(self, point: SweepPoint, seed_count: int = 10, ticks_per_run: int = 500):
        self.point = point
        self.seed_count = seed_count
        self.ticks_per_run = ticks_per_run

    def run(self) -> SeedStabilityResult:
        result = SeedStabilityResult()
        result.parameters = self.point
        result.seed_count = self.seed_count

        for seed in range(self.seed_count):
            r = self._run_with_seed(seed)
            result.seed_results.append(r)
            result.seed_regimes.append(r.regime)

        result.stability_score = self._compute_stability(result.seed_regimes)
        result.dominant_regime = self._find_dominant_regime(result.seed_regimes)
        result.variation_count = sum(1 for r in result.seed_regimes if r != result.dominant_regime)
        result.is_near_boundary = result.stability_score < 0.8
        result.is_reproducible = result.stability_score >= 0.9
        return result

    def _run_with_seed(self, seed: int) -> PhaseSweepResult:
        rng = random.Random(seed)
        ecology = SimpleConstraintEcology()
        ecology.set_parameters(self.point)
        memory = ConstraintMemory()
        policy = ConstraintEvolutionPolicy()
        limiter = ConstraintMutationLimiter()

        policy.rollback_threshold = self.point.rollout_threshold
        policy.cooldown_ticks = self.point.revision_cooldown
        policy.max_change_per_revision = self.point.max_mutation_size
        policy.stability_resistance_factor = self.point.stability_resistance
        limiter.rollback_threshold = self.point.rollout_threshold
        limiter.min_ticks_between_revisions = self.point.revision_cooldown
        rm = ConstraintRevisionManager(policy, limiter, memory, rng=rng)
        ids = [f"C{i}" for i in range(4)]
        for cid in ids:
            ecology.register_constraint(cid)
            memory.get_knowledge(cid)
        rm.set_ecology(ecology)

        collapsed = False
        first_shock_response = -1
        shock_occurred = False

        for tick in range(self.ticks_per_run):
            ecology.tick(1.0)
            rm.begin_cycle(tick)

            if (self.point.shock_frequency > 0 and
                tick % self.point.shock_frequency == 0 and tick > 0):
                shock_occurred = True
                for cid in ids:
                    pop = ecology.get_population(cid)
                    if pop is not None and pop.enforcement_strength > 0.5:
                        if rng.random() < self.point.shock_magnitude * 0.3:
                            ecology.record_violation(cid, False)

            if tick % 5 == 0:
                for cid in ids:
                    pop = ecology.get_population(cid)
                    if pop is not None and pop.enforcement_strength > 0.1:
                        is_real = rng.random() < pop.enforcement_strength
                        ecology.record_violation(cid, is_real)
                        if shock_occurred and first_shock_response < 0 and is_real:
                            first_shock_response = tick

            if ecology.global_fitness_metric() < -10 and tick > 50:
                collapsed = True
                break

        result = self._make_result(ecology, rm, first_shock_response, shock_occurred, collapsed)
        return result

    def _make_result(self, ecology, rm, first_shock_response, shock_occurred, collapsed):
        result = PhaseSweepResult()
        result.parameters = self.point
        result.total_revisions = rm.get_total_revisions()
        result.total_rollbacks = rm.get_total_rollbacks()
        result.revision_rate = (result.total_revisions / self.ticks_per_run
                               if self.ticks_per_run > 0 else 0.0)
        result.rollback_rate = (result.total_rollbacks / result.total_revisions
                               if result.total_revisions > 0 else 0.0)
        result.collapsed = collapsed
        pops = ecology.all_populations()
        if pops:
            result.avg_fitness = sum(p.fitness for p in pops) / len(pops)
            result.avg_strength = sum(p.enforcement_strength for p in pops) / len(pops)
            result.frozen_ratio = sum(1 for p in pops if p.enforcement_strength < 0.01) / len(pops)
            result.dominant_ratio = sum(1 for p in pops if p.enforcement_strength > 0.9) / len(pops)
        result.adaptation_latency = (first_shock_response if first_shock_response > 0
                                    else (-1 if shock_occurred else 0))
        result.regime = PhaseSweepResult.classify(
            result.revision_rate, result.rollback_rate, result.collapsed)
        return result

    @staticmethod
    def _compute_stability(regimes: list[PhaseRegime]) -> float:
        if not regimes:
            return 0.0
        max_count = max(sum(1 for o in regimes if o == r) for r in set(regimes))
        return max_count / len(regimes)

    @staticmethod
    def _find_dominant_regime(regimes: list[PhaseRegime]) -> Optional[PhaseRegime]:
        if not regimes:
            return None
        return max(set(regimes), key=lambda r: sum(1 for o in regimes if o == r))


# ─── Directional Sweep (Hysteresis Testing) ────────────────────────────

class HysteresisResult:
    def __init__(self):
        self.param_name: str = ""
        self.param_min: float = 0.0
        self.param_max: float = 0.0
        self.steps: int = 0
        self.forward_values: list[float] = []
        self.backward_values: list[float] = []
        self.forward_results: list[PhaseSweepResult] = []
        self.backward_results: list[PhaseSweepResult] = []
        self.forward_transition: float = -1.0
        self.backward_transition: float = -1.0
        self.hysteresis_width: float = 0.0
        self.has_hysteresis: bool = False
        self.direction_matters: bool = False

    def to_report(self) -> str:
        sb = []
        sb.append(f"=== Hysteresis Analysis: {self.param_name} ===")
        sb.append(f"  Range: [{self.param_min:.3f} - {self.param_max:.3f}]  Steps: {self.steps}")
        sb.append("")
        sb.append("  Forward (Low -> High):")
        for i, r in enumerate(self.forward_results):
            sb.append(f"    {self.forward_values[i]:.3f} -> {r.regime.value:<10}  revRate={r.revision_rate:.4f}")
        sb.append("")
        sb.append("  Backward (High -> Low):")
        for i, r in enumerate(self.backward_results):
            sb.append(f"    {self.backward_values[-(i+1)]:.3f} -> {r.regime.value:<10}  revRate={r.revision_rate:.4f}")
        sb.append("")
        sb.append("  --- Comparison ---")
        sb.append(f"  Forward transition:  {'none' if self.forward_transition < 0 else f'{self.forward_transition:.3f}'}")
        sb.append(f"  Backward transition: {'none' if self.backward_transition < 0 else f'{self.backward_transition:.3f}'}")
        sb.append(f"  Hysteresis width:    {self.hysteresis_width:.3f}")
        sb.append(f"  Has hysteresis:      {self.has_hysteresis}")
        sb.append(f"  Direction matters:   {self.direction_matters}")
        if self.has_hysteresis:
            sb.append("")
            sb.append("  *** HYSTERESIS DETECTED ***")
            sb.append("  The system has developmental memory.")
        return "\n".join(sb)


class DirectionalSweep:
    SWEPT_PARAMS = {
        "rollbackThreshold", "revisionCooldown", "maxMutationSize",
        "stabilityResistance", "constraintBudget", "enforcementCost",
        "falsePositivePenalty", "shockFrequency", "shockMagnitude",
    }

    def __init__(self, param_name: str, param_min: float, param_max: float,
                 steps: int, ticks_per_run: int = 500, seed: int = 42):
        self.param_name = param_name
        self.param_min = param_min
        self.param_max = param_max
        self.steps = steps
        self.ticks_per_run = ticks_per_run
        self.carry_state = False
        # Previously this class had no RNG whatsoever, so every hysteresis run
        # drew from the global stream and the hysteresis result could not be
        # reproduced. One seed now covers the whole directional sweep.
        self._rng = random.Random(seed)
        self.seed = seed

    def run(self) -> HysteresisResult:
        result = HysteresisResult()
        result.param_name = self.param_name
        result.param_min = self.param_min
        result.param_max = self.param_max
        result.steps = self.steps
        values = [self.param_min + i * (self.param_max - self.param_min) / (self.steps - 1)
                  for i in range(self.steps)]
        result.forward_values = values[:]
        result.backward_values = values[:]

        result.forward_results = self._sweep_forward(values)
        result.backward_results = self._sweep_backward(values)

        result.forward_transition = self._find_transition(result.forward_results, values)
        result.backward_transition = self._find_transition(result.backward_results, list(reversed(values)))
        result.hysteresis_width = abs(result.forward_transition - result.backward_transition)
        result.has_hysteresis = result.hysteresis_width > (self.param_max - self.param_min) * 0.1
        result.direction_matters = self._directional_difference(
            result.forward_results, result.backward_results)
        return result

    def _sweep_forward(self, values: list[float]) -> list[PhaseSweepResult]:
        return [self._run_single(v) for v in values]

    def _sweep_backward(self, values: list[float]) -> list[PhaseSweepResult]:
        return [self._run_single(values[len(values) - 1 - i]) for i in range(len(values))]

    def _run_single(self, param_value: float) -> PhaseSweepResult:
        point = SweepPoint()
        setattr(point, {
            "rollbackThreshold": "rollout_threshold",
            "revisionCooldown": "revision_cooldown",
            "maxMutationSize": "max_mutation_size",
            "stabilityResistance": "stability_resistance",
            "constraintBudget": "constraint_budget",
            "enforcementCost": "enforcement_cost",
            "falsePositivePenalty": "false_positive_penalty",
            "shockFrequency": "shock_frequency",
            "shockMagnitude": "shock_magnitude",
        }.get(self.param_name, self.param_name), param_value)
        # A fresh stream per step, drawn from the sweep's seeded stream, so the
        # sequence of steps is reproducible and each step is independent.
        rng = random.Random(self._rng.getrandbits(64))
        ecology = SimpleConstraintEcology()
        ecology.set_parameters(point)
        memory = ConstraintMemory()
        policy = ConstraintEvolutionPolicy()
        limiter = ConstraintMutationLimiter()
        policy.rollback_threshold = point.rollout_threshold
        policy.cooldown_ticks = point.revision_cooldown
        policy.max_change_per_revision = point.max_mutation_size
        policy.stability_resistance_factor = point.stability_resistance
        limiter.rollback_threshold = point.rollout_threshold
        limiter.min_ticks_between_revisions = point.revision_cooldown
        rm = ConstraintRevisionManager(policy, limiter, memory, rng=rng)
        ids = ["C0", "C1", "C2", "C3"]
        for cid in ids:
            ecology.register_constraint(cid)
            memory.get_knowledge(cid)
        rm.set_ecology(ecology)
        collapsed = False
        for tick in range(self.ticks_per_run):
            ecology.tick(1.0)
            rm.begin_cycle(tick)
            if (point.shock_frequency > 0 and tick % point.shock_frequency == 0 and tick > 0):
                for cid in ids:
                    pop = ecology.get_population(cid)
                    if pop is not None and pop.enforcement_strength > 0.5:
                        ecology.record_violation(cid, False)
            if tick % 5 == 0:
                for cid in ids:
                    pop = ecology.get_population(cid)
                    if pop is not None and pop.enforcement_strength > 0.1:
                        ecology.record_violation(cid, pop.enforcement_strength > 0.5)
            if ecology.global_fitness_metric() < -10 and tick > 50:
                collapsed = True
                break
        result = PhaseSweepResult()
        result.parameters = point
        result.total_revisions = rm.get_total_revisions()
        result.total_rollbacks = rm.get_total_rollbacks()
        result.revision_rate = (result.total_revisions / self.ticks_per_run
                               if self.ticks_per_run > 0 else 0.0)
        result.rollback_rate = (result.total_rollbacks / result.total_revisions
                               if result.total_revisions > 0 else 0.0)
        result.collapsed = collapsed
        pops = ecology.all_populations()
        if pops:
            result.avg_fitness = sum(p.fitness for p in pops) / len(pops)
            result.avg_strength = sum(p.enforcement_strength for p in pops) / len(pops)
        result.regime = PhaseSweepResult.classify(
            result.revision_rate, result.rollback_rate, result.collapsed)
        return result

    @staticmethod
    def _find_transition(results: list[PhaseSweepResult], values: list[float]) -> float:
        for i in range(1, len(results)):
            if results[i].regime != results[i - 1].regime:
                return values[min(i, len(values) - 1)]
        return -1.0

    @staticmethod
    def _directional_difference(fwd: list[PhaseSweepResult],
                                 bwd: list[PhaseSweepResult]) -> bool:
        if len(fwd) != len(bwd):
            return True
        return any(f.regime != b.regime for f, b in zip(fwd, bwd))


# ─── Theory Bridge ─────────────────────────────────────────────────────

#: The register labels this package uses, and what each one claims.
#:
#: ``CONSISTENT_WITH_THIS_MODEL`` is the strongest claim the sweep can honestly
#: make. It means: running THIS model at THIS parameterisation produced output
#: matching what the model already predicted. That is an internal consistency
#: check, not external validation.
#:
#: Reproducing a model's own prediction cannot establish that the model is right
#: about anything outside itself. Nothing here compares against experiment, real
#: data, or an independent implementation. The previous wording -- printing
#: ``SUPPORTED`` -- read as though it were.
REGISTER_CONSISTENT = "CONSISTENT_WITH_THIS_MODEL"
REGISTER_INCONSISTENT = "INCONSISTENT_WITH_THIS_MODEL"
REGISTER_NOT_TESTED = "NOT_TESTED_BY_THIS_SWEEP"


@dataclass
class TheoryHypothesis:
    """One internal consistency check against this model's own prediction.

    ``register`` is a string label rather than a truth value, because the
    distinction between "matches" and "is validated" is exactly the distinction
    this field exists to preserve. The previous ``supported: bool`` made both
    readings available to a caller, and the CLI chose the wrong one.
    """

    description: str
    register: str = REGISTER_NOT_TESTED
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def consistent(self) -> bool:
        return self.register == REGISTER_CONSISTENT


class SweepTheoryBridge:
    @staticmethod
    def evaluate(report: SweepReport) -> list[TheoryHypothesis]:
        hypotheses = []
        results = report.results

        adaptive_points = [r for r in results if r.regime == PhaseRegime.ADAPTIVE]
        if adaptive_points:
            center_rt = sum(r.parameters.rollout_threshold for r in adaptive_points) / len(adaptive_points)
            center_cd = sum(r.parameters.revision_cooldown for r in adaptive_points) / len(adaptive_points)
            avg_plasticity = sum(r.plasticity_score for r in adaptive_points) / len(adaptive_points)

            h1 = TheoryHypothesis(
                description=(
                    f"Moderate constraint revision with low rollback "
                    f"produces stable adaptive regulatory regimes. "
                    f"Adaptive basin center: RT={center_rt:.2f}, CD={center_cd:.0f}"),
                register=REGISTER_CONSISTENT,
                evidence=[f"Adaptive basin detected: {len(adaptive_points)}/{len(results)} points",
                         f"Center: revision_cooldown={center_cd:.0f}, rollback={center_rt:.2f}",
                         f"Average plasticity: {avg_plasticity:.4f}"],
                confidence=0.8)
            hypotheses.append(h1)

        frozen_near_adaptive = any(
            r.regime == PhaseRegime.FROZEN and
            any(abs(r.parameters.rollout_threshold - a.parameters.rollout_threshold) < 0.05
                for a in adaptive_points)
            for r in results)
        if frozen_near_adaptive:
            h2 = TheoryHypothesis(
                description="Sharp phase boundary exists between FROZEN and ADAPTIVE regimes",
                register=REGISTER_CONSISTENT,
                evidence=["Adjacent parameter points produce different regimes"],
                confidence=0.6)
            hypotheses.append(h2)

        chaotic_points = [r for r in results if r.regime == PhaseRegime.CHAOTIC]
        if chaotic_points:
            h3 = TheoryHypothesis(
                description="High revision rate with insufficient rollback leads to chaos",
                register=REGISTER_CONSISTENT,
                evidence=[f"Chaotic regime occupies {len(chaotic_points)}/{len(results)} parameter points"],
                confidence=0.5)
            hypotheses.append(h3)

        return hypotheses


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

def run_sweep_and_report():
    print("=" * 60)
    print("  CoGeCo - Regulatory Phase Sweep")
    print("  Focused 2D: Rollback Threshold x Revision Cooldown")
    print("  Grid: 7x7 = 49 points")
    print("=" * 60)
    print()

    config = PhaseSweepConfig.focused2d()
    sweep = RegulatoryPhaseSweep(config)
    report = sweep.run()

    print()
    print(report.to_report(detailed=True))
    print()

    print("  --- MODEL-CONSISTENCY CHECKS ---")
    print("  These compare this run against what THIS MODEL already predicts.")
    print("  They are internal consistency checks, not external validation.")
    print("  Nothing here is compared against real data or an independent")
    print("  implementation, and no claim beyond this model is supported.")
    print()
    hypotheses = SweepTheoryBridge.evaluate(report)
    for h in hypotheses:
        print(f"  [{h.register}] {h.description}")
        for ev in h.evidence:
            print(f"    - {ev}")
        print(f"    Confidence: {h.confidence:.2f}")
    print()

    return report


def run_seed_test():
    print("=" * 60)
    print("  Seed Stability Test - Best Adaptive Candidate")
    print("=" * 60)

    config = PhaseSweepConfig.focused2d()
    mid_point = config.get_combination(24)
    print(f"  Testing point: {mid_point.to_short_key()}")

    svs = SeedVariedSweep(mid_point, seed_count=15)
    result = svs.run()
    print()
    print(result.to_report())
    print()
    return result


def run_hysteresis_test():
    print("=" * 60)
    print("  Hysteresis Test - Rollback Threshold")
    print("=" * 60)

    ds = DirectionalSweep("rollbackThreshold", 0.05, 0.5, 7, 300)
    result = ds.run()
    print()
    print(result.to_report())
    print()

    print("=" * 60)
    print("  Hysteresis Test - Revision Cooldown")
    print("=" * 60)

    ds2 = DirectionalSweep("revisionCooldown", 10, 500, 7, 300)
    result2 = ds2.run()
    print()
    print(result2.to_report())
    print()

    return result, result2


def run_basin_analysis(report: SweepReport):
    print("=" * 60)
    print("  ADAPTIVE BASIN ANALYSIS")
    print("=" * 60)
    print()

    adaptive = [r for r in report.results if r.regime == PhaseRegime.ADAPTIVE]
    if not adaptive:
        print("  No adaptive regime detected in this sweep.")
        return

    total = len(report.results)
    print(f"  Area: {len(adaptive)} / {total} parameter points")
    center_rt = sum(r.parameters.rollout_threshold for r in adaptive) / len(adaptive)
    center_cd = sum(r.parameters.revision_cooldown for r in adaptive) / len(adaptive)
    print(f"  Center: rollback_threshold = {center_rt:.2f}, revision_cooldown = {center_cd:.0f}")

    healthy = [r for r in adaptive if r.system_health > 0.7]
    print(f"  Healthy adaptive: {len(healthy)}/{len(adaptive)} (health > 0.7)")
    print(f"  Average system health: {sum(r.system_health for r in adaptive)/len(adaptive):.3f}")
    print(f"  Average plasticity: {sum(r.plasticity_score for r in adaptive)/len(adaptive):.4f}")
    print(f"  Average fitness: {sum(r.avg_fitness for r in adaptive)/len(adaptive):.4f}")

    rt_vals = sorted(set(r.parameters.rollout_threshold for r in adaptive))
    cd_vals = sorted(set(r.parameters.revision_cooldown for r in adaptive))
    print(f"  Rollback range: {min(rt_vals):.2f} - {max(rt_vals):.2f}")
    print(f"  Cooldown range: {min(cd_vals)} - {max(cd_vals)}")

    print()
    boundary_points = [r for r in report.results
                      if r.regime != PhaseRegime.ADAPTIVE and
                      any(abs(r.parameters.rollout_threshold - a.parameters.rollout_threshold) <= 0.05 and
                          abs(r.parameters.revision_cooldown - a.parameters.revision_cooldown) <= 100
                          for a in adaptive)]
    if boundary_points:
        boundary_regimes = {}
        for r in boundary_points:
            boundary_regimes[r.regime] = boundary_regimes.get(r.regime, 0) + 1
        print(f"  Boundary regimes (neighbors of adaptive):")
        for regime, count in sorted(boundary_regimes.items(), key=lambda x: -x[1]):
            print(f"    {regime.value}: {count}")
    print()


def save_report_json(report: SweepReport, path: str = "cogeco_sweep_results.json",
                     seed: Optional[int] = None,
                     reproducibility_status: str = "ESTABLISHED"):
    """Write the deterministic result artifact.

    This file is the reproducibility contract: two runs at the same code,
    parameters and seed must produce byte-identical output. Wall-clock runtime
    is therefore EXCLUDED -- it was previously written as ``elapsed_seconds``,
    which made every artifact unique and every diff meaningless.

    Runtime is still reported to the operator, in the human-readable report,
    labelled as operational metadata.

    ``seed`` and ``config_summary`` are included so a result is interpretable
    without reference to the command that produced it.
    """
    data = {
        "artifact": "cogeco-phase-sweep-result",
        "schema_version": 2,
        "reproducibility_status": reproducibility_status,
        "seed": seed,
        "config_summary": report.config.summary() if report.config else "",
        "total_combinations": report.total_combinations,
        "results": []
    }
    for r in report.results:
        data["results"].append({
            "parameters": r.parameters.__dict__.copy(),
            "revision_rate": r.revision_rate,
            "rollback_rate": r.rollback_rate,
            "regime": r.regime.value,
            "avg_fitness": r.avg_fitness,
            "avg_strength": r.avg_strength,
            "plasticity_score": r.plasticity_score,
            "system_health": r.system_health,
            "collapsed": r.collapsed,
            "total_revisions": r.total_revisions,
            "total_rollbacks": r.total_rollbacks,
        })
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Results saved to {path}")


if __name__ == "__main__":
    print("  CoGeCo Regulatory Phase Sweep")
    print("  =============================")
    print()

    report = run_sweep_and_report()

    print()
    run_basin_analysis(report)

    print()
    save_report_json(report)

    print()
    print("  Running Seed Stability Test...")
    print()
    seed_result = run_seed_test()

    print()
    print("  Running Hysteresis Tests...")
    print()
    hyst_results = run_hysteresis_test()

    print("Done.")
