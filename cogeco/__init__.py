"""cogeco-phase-sweep: a reproducible regulatory phase sweep.

Does a constraint-governance simulation show regime boundaries in its parameter
space? This package runs the sweep, writes a deterministic result artifact, and
lets you prove the result reproduces.

The scientific registers are kept distinct on purpose. Read
``docs/METRICS.md`` before quoting a number, and in particular before treating
a ``CONSISTENT_WITH_THIS_MODEL`` label as validation.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
