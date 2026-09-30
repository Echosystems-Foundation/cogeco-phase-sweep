"""Pillar State Vector: the state representation the phase sweep reasons about.

Each pillar is a Bloch-sphere angle ``theta`` in [0, pi]. A state is the
16-vector of those angles, and the sweep's notion of a population's condition is
a distribution over them.

Carried here from the VNES-Lab research tree so this demo is self-contained.
Extracted unchanged apart from the ``to_metric`` import, which now refers to the
bridge module shipped beside this file rather than to an installed package.

Provenance: docs/PROVENANCE.md
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional

NUM_PILLARS = 16
PI = math.pi
TAU = 2 * PI

PILLAR_NAMES = [
    "Awareness", "Willpower", "Force", "Influence",
    "Resistance", "Integrity", "Cohesion", "Relation",
    "Presence", "Warmth", "Memory", "Attraction",
    "Harm", "Distortion", "Flux", "Depth",
]


@dataclass
class PillarState:
    """16-dimensional Pillar State Vector (PSV).
    Each pillar is a Bloch sphere angle theta in [0, PI].
    """
    theta: List[float] = field(default_factory=lambda: [PI / 2] * NUM_PILLARS)
    phi: List[float] = field(default_factory=lambda: [0.0] * NUM_PILLARS)

    @classmethod
    def random(cls, seed: Optional[int] = None) -> "PillarState":
        if seed is not None:
            random.seed(seed)
        return cls(
            theta=[random.random() * PI for _ in range(NUM_PILLARS)],
            phi=[random.random() * TAU for _ in range(NUM_PILLARS)],
        )

    @classmethod
    def from_values(cls, theta: List[float], phi: Optional[List[float]] = None) -> "PillarState":
        if phi is None:
            phi = [0.0] * NUM_PILLARS
        return cls(theta=theta[:], phi=phi[:])

    def copy(self) -> "PillarState":
        return PillarState(theta=self.theta[:], phi=self.phi[:])

    def clamp(self, soft: bool = True):
        # Upstream this iterated range(NUM_PILLARS) over whatever theta held,
        # so a state built with the wrong number of pillars raised IndexError
        # from inside the loop -- a confusing crash far from the mistake. The
        # length is now checked where the mistake is.
        if len(self.theta) != NUM_PILLARS or len(self.phi) != NUM_PILLARS:
            raise ValueError(
                f"a pillar state has exactly {NUM_PILLARS} components; got "
                f"theta={len(self.theta)}, phi={len(self.phi)}. The metric is "
                f"{NUM_PILLARS}x{NUM_PILLARS} and has no meaning for another "
                f"size."
            )
        for i in range(NUM_PILLARS):
            # Soft boundary damping before hard clamp
            if soft and self.theta[i] > PI * 0.95:
                self.theta[i] -= (self.theta[i] - PI * 0.95) * 0.25
            elif soft and self.theta[i] < 0.05:
                self.theta[i] += (0.05 - self.theta[i]) * 0.25
            self.theta[i] = max(0.0, min(PI, self.theta[i]))
            self.phi[i] = self.phi[i] % TAU

    def _check_size(self) -> None:
        if len(self.theta) != NUM_PILLARS or len(self.phi) != NUM_PILLARS:
            raise ValueError(
                f"a pillar state has exactly {NUM_PILLARS} components; got "
                f"theta={len(self.theta)}, phi={len(self.phi)}"
            )

    def magnitude(self) -> float:
        return math.sqrt(sum(t * t for t in self.theta)) / NUM_PILLARS

    def similarity(self, other: "PillarState") -> float:
        dot = sum(self.theta[i] * other.theta[i] for i in range(NUM_PILLARS))
        n1 = math.sqrt(sum(t * t for t in self.theta))
        n2 = math.sqrt(sum(t * t for t in other.theta))
        if n1 < 1e-12 or n2 < 1e-12:
            return 0.0
        return dot / (n1 * n2)

    def distance(self, other: "PillarState") -> float:
        return math.sqrt(sum((self.theta[i] - other.theta[i]) ** 2 for i in range(NUM_PILLARS)))

    def entropy(self) -> float:
        p = [t / PI for t in self.theta]
        s = 0.0
        for pi in p:
            pi = max(1e-12, min(1 - 1e-12, pi))
            s -= pi * math.log2(pi) + (1 - pi) * math.log2(1 - pi)
        return s / NUM_PILLARS

    # ── BCFVT Bridge ───────────────────────────────────────────────

    def to_field_state(self):
        """Convert PillarState theta values to BCFVT field state ℱ ∈ [-1, 1].

        VNES-Lab uses theta ∈ [0, π]. BCFVT field uses [-1, 1].
        Mapping: ℱ = cos(θ) = 1 - 2·(θ/π)

        Requires: the bridge module shipped with this package. See
        docs/PROVENANCE.md for where it came from.
        """
        import numpy as np
        return np.array(
            [1.0 - 2.0 * (t / PI) for t in self.theta],
            dtype=np.float64,
        )

    @classmethod
    def from_field_state(cls, field):
        """Construct PillarState from BCFVT field state ℱ ∈ [-1, 1].

        Mapping: θ = π·(1 - ℱ)/2

        Args:
            field: numpy array of 16 values in [-1, 1]

        Requires: the bridge module shipped with this package. See
        docs/PROVENANCE.md for where it came from.
        """
        import numpy as np
        arr = np.asarray(field, dtype=np.float64)
        thetas = [max(0.0, min(PI, PI * (1.0 - float(v)) / 2.0)) for v in arr]
        return cls(theta=thetas, phi=[0.0] * NUM_PILLARS)

    def to_metric(self, epsilon: float = 0.1, coherence_weight: float = 0.3):
        """Compute 16×16 BCFVT metric tensor from this pillar state.

        Returns numpy ndarray (16×16, SPD).

        Requires: the bridge module shipped with this package. See
        docs/PROVENANCE.md for where it came from.
        """
        from .bridges import BlochPillarData, compute_metric_from_bloch
        values = [t / PI for t in self.theta]  # map [0,π] → [0,1]
        coherence = 1.0 - (max(values) - min(values))  # uniform → high
        bd = BlochPillarData(
            thetas=self.theta[:],
            phis=self.phi[:],
            values=values,
            coherence=max(0.0, min(1.0, coherence)),
        )
        return compute_metric_from_bloch(bd, epsilon=epsilon,
                                         coherence_weight=coherence_weight)

    def __repr__(self) -> str:
        return f"PSV({[f'{t:.3f}' for t in self.theta[:4]]}...)"
