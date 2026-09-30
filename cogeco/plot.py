"""Phase diagram visualization for CoGeCo sweep results."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from pathlib import Path

#: Set by main(); every figure is written here.
_OUTPUT_DIR = Path(".")

REGIME_ORDER = ["FROZEN", "STABLE", "ADAPTIVE", "CHAOTIC", "COLLAPSED", "UNKNOWN"]
REGIME_CMAP = {
    "FROZEN":    "#4a6fa5",
    "STABLE":    "#6bbf59",
    "ADAPTIVE":  "#f4a261",
    "CHAOTIC":   "#e76f51",
    "COLLAPSED": "#555555",
    "UNKNOWN":   "#dddddd",
}
REGIME_CODE = {r: i for i, r in enumerate(REGIME_ORDER)}

def load_results(path="cogeco_sweep_results.json"):
    with open(path) as f:
        return json.load(f)

def plot_phase_diagram(data, output=None):
    """Render this figure into the active output directory."""
    if output is None:
        output = str(_OUTPUT_DIR / "phase_diagram.png")
    results = data["results"]
    rt_vals = sorted(set(r["parameters"]["rollout_threshold"] for r in results))
    cd_vals = sorted(set(r["parameters"]["revision_cooldown"] for r in results))
    n_rt, n_cd = len(rt_vals), len(cd_vals)
    grid = np.full((n_rt, n_cd), -1, dtype=int)
    health_grid = np.full((n_rt, n_cd), np.nan)
    for r in results:
        xi = rt_vals.index(r["parameters"]["rollout_threshold"])
        yi = cd_vals.index(r["parameters"]["revision_cooldown"])
        grid[xi, yi] = REGIME_CODE.get(r["regime"], -1)
        health_grid[xi, yi] = r["system_health"]

    all_regimes = REGIME_ORDER
    cmap = mcolors.ListedColormap([REGIME_CMAP[r] for r in all_regimes])
    bounds = np.arange(-0.5, len(all_regimes) + 0.5, 1)
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    im = axes[0].pcolormesh(cd_vals, rt_vals, grid, cmap=cmap, norm=norm, shading="auto")
    axes[0].set_xlabel("Revision Cooldown (ticks)", fontsize=11)
    axes[0].set_ylabel("Rollback Threshold", fontsize=11)
    axes[0].set_title("Regulatory Phase Diagram", fontsize=13, fontweight="bold")
    for i, regime in enumerate(REGIME_ORDER):
        axes[0].plot([], [], "s", color=REGIME_CMAP[regime], label=regime)
    axes[0].legend(loc="upper right", fontsize=9)
    axes[0].set_xticks(cd_vals)
    axes[0].set_yticks(rt_vals)

    im2 = axes[1].pcolormesh(cd_vals, rt_vals, health_grid, cmap="RdYlGn",
                             shading="auto", vmin=0.5, vmax=0.9)
    axes[1].set_xlabel("Revision Cooldown (ticks)", fontsize=11)
    axes[1].set_ylabel("Rollback Threshold", fontsize=11)
    axes[1].set_title("System Health", fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im2, ax=axes[1], label="Health")
    axes[1].set_xticks(cd_vals)
    axes[1].set_yticks(rt_vals)

    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Phase diagram saved: {output}")

def plot_revision_rollback_scatter(data, output=None):
    """Render this figure into the active output directory."""
    if output is None:
        output = str(_OUTPUT_DIR / "revision_rollback_scatter.png")
    results = data["results"]
    fig, ax = plt.subplots(figsize=(8, 6))
    for r in results:
        regime = r["regime"]
        rr = r["revision_rate"]
        rb = r["rollback_rate"]
        ax.scatter(rr, rb, c=REGIME_CMAP.get(regime, "#ccc"), s=80,
                   edgecolors="black", linewidths=0.5, zorder=5)
        ax.annotate(f"RT={r['parameters']['rollout_threshold']:.2f}\nCD={r['parameters']['revision_cooldown']}",
                    (rr, rb), fontsize=5, alpha=0.6, ha="left", va="bottom")

    ax.axhline(y=0.4, color="red", linestyle="--", alpha=0.5, label="Rollback threshold (0.4)")
    ax.axvline(x=0.01, color="blue", linestyle="--", alpha=0.5, label="Revision threshold (0.01)")
    ax.set_xlabel("Revision Rate", fontsize=11)
    ax.set_ylabel("Rollback Rate", fontsize=11)
    ax.set_title("Phase Classification: Revision Rate vs Rollback Rate", fontsize=12)
    for regime in REGIME_ORDER:
        ax.plot([], [], "o", color=REGIME_CMAP[regime], label=regime)
    ax.legend(fontsize=9)
    ax.set_xlim(-0.01, 0.45)
    ax.set_ylim(-0.05, 1.1)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Scatter plot saved: {output}")

def plot_plasticity_heatmap(data, output=None):
    """Render this figure into the active output directory."""
    if output is None:
        output = str(_OUTPUT_DIR / "plasticity_heatmap.png")
    results = data["results"]
    rt_vals = sorted(set(r["parameters"]["rollout_threshold"] for r in results))
    cd_vals = sorted(set(r["parameters"]["revision_cooldown"] for r in results))
    n_rt, n_cd = len(rt_vals), len(cd_vals)
    grid = np.full((n_rt, n_cd), np.nan)
    for r in results:
        xi = rt_vals.index(r["parameters"]["rollout_threshold"])
        yi = cd_vals.index(r["parameters"]["revision_cooldown"])
        grid[xi, yi] = r["plasticity_score"]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(cd_vals, rt_vals, grid, cmap="plasma", shading="auto", vmin=0, vmax=1)
    ax.set_xlabel("Revision Cooldown (ticks)", fontsize=11)
    ax.set_ylabel("Rollback Threshold", fontsize=11)
    ax.set_title("Plasticity Score", fontsize=13, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, label="Plasticity")
    ax.set_xticks(cd_vals)
    ax.set_yticks(rt_vals)
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plasticity heatmap saved: {output}")

def main(artifact="cogeco_sweep_results.json", outdir="."):
    """Render every figure from an existing result artifact.

    Takes the artifact path and an output directory rather than assuming a
    filename in the working directory, so a figure can always be traced back to
    the exact artifact that produced it. It never re-runs the simulation: a plot
    that disagreed with the numbers it claimed to show would be worse than no
    plot.
    """
    global _OUTPUT_DIR
    data = load_results(artifact)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    results = data["results"]
    _OUTPUT_DIR = outdir

    regime_counts = {}
    for r in results:
        regime_counts[r["regime"]] = regime_counts.get(r["regime"], 0) + 1

    print("=== Regime Distribution ===")
    for regime, count in sorted(regime_counts.items(), key=lambda x: -x[1]):
        print(f"  {regime}: {count}/{len(results)} ({count/len(results)*100:.0f}%)")

    print()
    plot_phase_diagram(data)
    plot_revision_rollback_scatter(data)
    plot_plasticity_heatmap(data)
    print()
    print("All visualizations generated.")

if __name__ == "__main__":
    main()
