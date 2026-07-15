#!/usr/bin/env python3
"""
plot_metrics.py — thesis figures from one or more corruption_log.csv files.

Usage:
  python plot_metrics.py <csv>[:<label>] [<csv>[:<label>] ...] [-o out.png]

Examples:
  python plot_metrics.py _log_sim_control_30d.csv:Control _log_sim_antidynasty_30d.csv:Anti-dynasty
  python plot_metrics.py storage/sim_control_30d2/reverie/corruption_log.csv:Control \
                         storage/sim_antidynasty_30d2/reverie/corruption_log.csv:Anti-dynasty \
                         -o figures/metrics_v2.png

Handles both log formats: v1 (6 columns) and mem2 (+ corr/gov/grv mass,
aggrieved_share, formula). Mass panels are drawn per run when present.
"""
import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Two-run comparison palette (validated: CVD dE > 120, contrast > 3:1 on white).
RUN_COLORS = ["#2563EB", "#EA580C", "#7C3AED", "#0D9488"]
# Memory-class trio (validated; also direct-labeled so identity is not color-alone).
CLASS_COLORS = {"corruption": "#DC2626", "governance": "#059669", "grievance": "#D97706"}

INK = "#1F2937"       # primary text
INK_MUTED = "#6B7280" # secondary text / axes
GRID = "#E5E7EB"      # recessive grid


def load_log(path):
    """Return dict of column -> list[float], plus 'step'. Tolerates both formats."""
    cols = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                step = int(row["step"])
            except (KeyError, TypeError, ValueError):
                continue
            cols.setdefault("step", []).append(step)
            for k in ("corruption_index", "dynasty_bonus", "welfare", "unrest",
                      "corr_mass", "gov_mass", "grv_mass", "aggrieved_share"):
                v = row.get(k)
                if v not in (None, ""):
                    try:
                        cols.setdefault(k, []).append(float(v))
                    except ValueError:
                        cols.setdefault(k, []).append(float("nan"))
                elif k in cols:
                    cols[k].append(float("nan"))
    return cols


def style_axis(ax, title, ylabel=""):
    ax.set_title(title, fontsize=11, color=INK, loc="left", pad=8)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(INK_MUTED)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.set_xlabel("step (1 h each; 24 = 1 sim-day)", fontsize=9, color=INK_MUTED)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=INK_MUTED)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+", help="csv path, optionally :Label suffix")
    ap.add_argument("-o", "--out", default="figures/metrics_compare.png")
    args = ap.parse_args()

    runs = []   # (label, cols)
    for spec in args.logs:
        # Split on the LAST colon only if what follows is not a path (win drives!)
        path, label = spec, None
        if ":" in spec:
            head, _, tail = spec.rpartition(":")
            if head and not (len(tail) > 1 and ("/" in tail or "\\" in tail)) \
               and not (len(head) == 1 and head.isalpha()):
                path, label = head, tail
        if label is None:
            label = os.path.basename(path).replace(".csv", "")
        if not os.path.exists(path):
            sys.exit(f"not found: {path}")
        runs.append((label, load_log(path)))

    index_panels = [
        ("corruption_index", "Corruption index", "corr / (corr + gov) memory mass"),
        ("welfare", "Welfare", "mean per-agent satisfaction"),
        ("unrest", "Unrest", "share personally aggrieved"),
        ("dynasty_bonus", "Dynasty seat-share (diagnostic)", "(seats−1) × 0.05 per family"),
    ]
    mass_runs = [(lbl, c) for lbl, c in runs if "corr_mass" in c]

    n_index = len(index_panels)
    n_mass = len(mass_runs)
    ncols = 2
    nrows = (n_index + n_mass + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 3.4 * nrows))
    fig.patch.set_facecolor("white")
    axes = [ax for row in (axes if nrows > 1 else [axes]) for ax in row]

    for i, (key, title, sub) in enumerate(index_panels):
        ax = axes[i]
        for j, (label, cols) in enumerate(runs):
            if key not in cols:
                continue
            ax.plot(cols["step"], cols[key], color=RUN_COLORS[j % len(RUN_COLORS)],
                    linewidth=2, label=label, solid_capstyle="round")
        style_axis(ax, f"{title}\n", "0–1" if key != "dynasty_bonus" else "")
        ax.text(0, 1.02, " " * 0, transform=ax.transAxes)  # spacing guard
        ax.set_title(title, fontsize=11, color=INK, loc="left", pad=16)
        ax.text(0.0, 1.01, sub, transform=ax.transAxes, fontsize=8.5,
                color=INK_MUTED, va="bottom")
        if key != "dynasty_bonus":
            ax.set_ylim(0, 1)

    for k, (label, cols) in enumerate(mass_runs):
        ax = axes[n_index + k]
        for cls, color in CLASS_COLORS.items():
            key = {"corruption": "corr_mass", "governance": "gov_mass",
                   "grievance": "grv_mass"}[cls]
            if key not in cols:
                continue
            ax.plot(cols["step"], cols[key], color=color, linewidth=2,
                    solid_capstyle="round")
            # direct label at line end (identity never color-alone)
            ax.annotate(cls, (cols["step"][-1], cols[key][-1]),
                        xytext=(4, 0), textcoords="offset points",
                        fontsize=8.5, color=color, va="center")
        style_axis(ax, f"Memory mass — {label}", "Σ poignancy × recency")

    for ax in axes[n_index + n_mass:]:
        ax.set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    if len(labels) > 1:
        fig.legend(handles, labels, loc="upper center", ncol=len(labels),
                   frameon=False, fontsize=10, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.96 if len(labels) > 1 else 1))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150, facecolor="white")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
