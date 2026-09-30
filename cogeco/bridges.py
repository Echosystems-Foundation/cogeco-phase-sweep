"""BCFVT Integration Bridges — connects Substrate_Echo dynamics to the
wider Van Nueman ecosystem (DeveloperConsole, MultiverseScreensaver,
VNES-Lab, Engine).

Each bridge defines the exact data contract the other system must provide.
No cross-repo imports — bridges are pure data transformers.

Contracts resolved:
- 01-1: compute_metric(BlochPSV data) → MetricTensor
- 04-3: foam_tick(foam node data) → TopologyTransition events
- BCFVT-05↔VNES-Lab: PSV adapter (scalar[] ↔ pillar_state)
- BCFVT-06↔Engine: Engine buffer serializer (MetricTensor → float[256])
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable
import numpy as np
import math


# ═══════════════════════════════════════════════════════════════════
# Bridge 1: BlochPSV → MetricTensor  (finding 01-1)
# ═══════════════════════════════════════════════════════════════════

N = 16


@dataclass
class BlochPillarData:
    """Minimal data a BlochPSV must provide for metric computation.

    This is the contract DeveloperConsole/backend/models/bloch_psv.py
    must satisfy.  BlochPSV.to_bridge_data() produces this.
    """
    thetas: list[float]  # length 16, polar angles [0, π]
    phis: list[float]    # length 16, azimuthal angles [0, 2π)
    values: list[float]  # length 16, Z-projections (cos θ + 1) / 2
    coherence: float     # scalar, [0, 1]


def compute_metric_from_bloch(bloch: BlochPillarData,
                              epsilon: float = 0.1,
                              coherence_weight: float = 0.3
                              ) -> np.ndarray:
    """Compute 16×16 metric tensor G_ij from BlochPSV state.

    The metric encodes how pillar space is curved by the current state.
    High coherence → metric isotropic (identity-like, pillars aligned).
    Low coherence → metric anisotropic (distorted by dominant pillar).

    G_ij = (1 - c_w·(1-coh)) · (δ_ij + ε · s_i · s_j)
         + c_w·(1-coh) · δ_ij

    Returns:
        16×16 symmetric positive-definite metric tensor
    """
    assert len(bloch.thetas) == N and len(bloch.phis) == N
    assert len(bloch.values) == N

    # Pillar coupling vector: how strongly each pillar "pulls" on geometry
    s = np.array(bloch.values, dtype=np.float64)

    # Normalize to unit vector for outer product
    s_norm = np.linalg.norm(s)
    if s_norm > 1e-12:
        s = s / s_norm

    # Anisotropic part: metric distorted by pillar state
    anisotropic = epsilon * np.outer(s, s)

    # Isotropic part: high coherence → more identity (isotropic)
    iso_boost = coherence_weight * (1.0 - bloch.coherence)
    isotropic = (1.0 - iso_boost) * np.eye(N, dtype=np.float64)

    # Combined metric
    G = isotropic + anisotropic

    # Project to SPD (symmetrize + ensure positive eigenvalues)
    G = 0.5 * (G + G.T)
    eigvals = np.linalg.eigvalsh(G)
    min_eig = min(eigvals)
    if min_eig < 1e-10:
        G += (1e-10 - min_eig) * np.eye(N, dtype=np.float64)

    return G


@dataclass
class EngineMetricBuffer:
    """Serialization of metric tensor for Engine's psv_compute.cu.

    The Engine uses a flat float[256] buffer (16×16) passed as a
    Vulkan uniform or CUDA device pointer.  This class handles the
    conversion.
    """
    data: list[float]  # 256 floats, row-major 16×16

    @classmethod
    def from_metric(cls, G: np.ndarray) -> EngineMetricBuffer:
        """Serialize 16×16 metric to flat float[256]."""
        assert G.shape == (N, N), f"Expected ({N},{N}), got {G.shape}"
        return cls(data=G.flatten().tolist())

    def to_metric(self) -> np.ndarray:
        """Deserialize flat float[256] back to 16×16 metric."""
        arr = np.array(self.data, dtype=np.float64)
        assert len(arr) == N * N, f"Expected {N*N} floats, got {len(arr)}"
        return arr.reshape(N, N)

    def to_bytes(self) -> bytes:
        """Serialize to raw bytes for GPU upload."""
        return np.array(self.data, dtype=np.float32).tobytes()

    @classmethod
    def from_bytes(cls, raw: bytes) -> EngineMetricBuffer:
        """Deserialize from raw GPU bytes."""
        arr = np.frombuffer(raw, dtype=np.float32)
        return cls(data=arr.tolist())


# ═══════════════════════════════════════════════════════════════════
# Bridge 2: MultiverseScreensaver Foam → TopologyManager  (04-3)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class FoamNodeData:
    """Data a single foam node provides to the topology manager.

    Contract for MultiverseScreensaver/src/MultiverseManager to produce
    each tick.  Maps to VacuumDefect in DeveloperConsole/void_svt.py.
    """
    node_id: int
    position: list[float]     # 3D position in foam space
    energy: float             # node energy density
    phase: float              # phase angle [0, 2π)
    purity: float             # Bloch state purity [0, 1]
    is_superfluid: bool       # superfluid flag from SVTKernels
    connections: list[int]    # IDs of connected nodes
    mass_density: float       # linear mass density (from VacuumDefect)


@dataclass
class FoamTickData:
    """Complete foam state for one tick.

    Produced by MultiverseManager each frame, passed to
    TopologyManager.check_foam_transitions().
    """
    nodes: list[FoamNodeData]
    temperature: float        # background temperature
    dt: float                 # time step
    foam_energy: float        # total foam energy


def check_foam_transitions(foam: FoamTickData,
                           field_config: np.ndarray,
                           topology_manager,
                           ) -> list:
    """Check foam nodes for topology transitions.

    Translates FoamTickData into candidate_finals for the
    TopologyManager and returns the accepted transitions.

    Args:
        foam: current foam state from MultiverseScreensaver
        field_config: current BCFVT field ℱ (16D)
        topology_manager: TopologyManager instance

    Returns:
        list of TopologyTransition events that passed rate limiting
    """
    candidates = []
    positions = []

    for node in foam.nodes:
        # Each foam node is a potential transition site
        # Candidate final: field state with node's phase injected
        candidate = field_config.copy()

        # Phase injection: shift field toward node's phase
        phase_shift = node.phase / (2.0 * math.pi)
        candidate = candidate * (1.0 - 0.1 * phase_shift)

        # Energy modulation: high-energy nodes are more likely to transition
        if node.energy > foam.temperature * 2.0:
            candidate *= 0.9  # suppress amplitude (toward vortex)

        candidates.append(candidate)
        positions.append(np.array(node.position, dtype=np.float64))

    if not candidates:
        return []

    return topology_manager.check_transitions(
        field_config,
        candidate_finals=candidates,
        positions=positions,
    )


# ═══════════════════════════════════════════════════════════════════
# Bridge 3: VNES-Lab PSV ↔ PillarCoupling  (BCFVT-05)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class VNESLabPSV:
    """VNES-Lab PSV representation.

    VNES-Lab's psv_core.py stores PSV as a list of 16 floats [0, 1]
    plus regression metrics.  This is the bridge data format.
    """
    pillars: list[float]        # 16 scalar values [0, 1]
    metrics: dict[str, float]   # regression metrics (ignored by bridge)
    timestamp: float = 0.0


def psv_to_pillar_state(vnes_psv: VNESLabPSV) -> np.ndarray:
    """Convert VNES-Lab PSV to BCFVT pillar state vector.

    VNES-Lab PSV values are already in [0, 1] — same range as
    pillar_coupling.py expects.  Direct copy with shape assertion.
    """
    assert len(vnes_psv.pillars) == N, \
        f"Expected {N} pillars, got {len(vnes_psv.pillars)}"
    return np.array(vnes_psv.pillars, dtype=np.float64)


def pillar_state_to_psv(state: np.ndarray,
                        metrics: Optional[dict[str, float]] = None
                        ) -> VNESLabPSV:
    """Convert BCFVT pillar state back to VNES-Lab PSV format."""
    assert len(state) == N
    return VNESLabPSV(
        pillars=np.clip(state, 0.0, 1.0).tolist(),
        metrics=metrics or {},
    )


# ═══════════════════════════════════════════════════════════════════
# Bridge 4: MetricInterface ↔ DeveloperConsole.compute_metric  (01-1)
# ═══════════════════════════════════════════════════════════════════

def bloch_psv_to_field_state(bloch: BlochPillarData) -> np.ndarray:
    """Convert BlochPSV scalars to BCFVT field state ℱ.

    BlochPSV values are [0, 1] (Z-projections).
    BCFVT field uses [-1, 1] internally.
    """
    return 2.0 * np.array(bloch.values, dtype=np.float64) - 1.0


def field_state_to_bloch_psv(field: np.ndarray) -> BlochPillarData:
    """Convert BCFVT field state back to BlochPSV format.

    ℱ ∈ [-1, 1] → value ∈ [0, 1]
    θ = acos(2v - 1)
    φ = 0 (field state doesn't carry phase information)
    """
    values = ((field + 1.0) / 2.0).clip(0.0, 1.0).tolist()
    thetas = [math.acos(max(-1.0, min(1.0, 2.0 * v - 1.0)))
              for v in values]
    phis = [0.0] * N  # no phase in scalar field state

    # Coherence: how aligned are the pillar values
    arr = np.array(values)
    coherence = 1.0 - float(np.std(arr)) * 2.0  # high std → low coherence
    coherence = max(0.0, min(1.0, coherence))

    return BlochPillarData(
        thetas=thetas, phis=phis, values=values, coherence=coherence,
    )
