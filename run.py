"""
run.py
Entry point for the Barangay Mabuhay simulation.

Usage:
    python run.py                        # run both environments sequentially
    python run.py --env dynasty          # dynasty only
    python run.py --env no_dynasty       # non-dynasty only
    python run.py --env both --parallel  # both in parallel (needs 2x RAM)
    python run.py --qwen http://vm-a:8000  # point to remote Qwen VM
    python run.py --seed 123            # reproducible run
    python run.py --ticks 100           # run only 100 ticks (for testing)
"""

import argparse
import logging
import multiprocessing
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("simulation.log"),
    ],
)
logger = logging.getLogger("run")


def run_environment(dynasty_enabled: bool, args):
    """Run one environment. Designed to be called in a subprocess."""
    from sim.model import BarangayModel
    from sim.inference.qwen_client import QwenConfig

    label = "dynasty" if dynasty_enabled else "no_dynasty"
    logger.info(f"Starting {label} environment")

    qwen_cfg = QwenConfig(base_url=args.qwen) if args.qwen else None

    model = BarangayModel(
        dynasty_enabled=dynasty_enabled,
        qwen_config=qwen_cfg,
        output_dir=args.output,
        seed=args.seed,
    )

    if args.ticks:
        # Limited run (for testing)
        for i in range(args.ticks):
            if model.clock.is_done:
                break
            model.step()
            if i % 24 == 0:
                print(f"  [{label}] Tick {i}: {model.clock.label}")
        summary = model.summary()
        model.db.close()
    else:
        model.run()

    # Print summary
    summary = model.summary()
    print(f"\n{'='*50}")
    print(f"SUMMARY: {label.upper()}")
    print(f"{'='*50}")
    gf = summary["global_factors"]
    print(f"  Final corruption index : {gf['corruption_index']:.4f}")
    print(f"  Final welfare index    : {gf['welfare_index']:.4f}")
    print(f"  Final citizen trust    : {gf['citizen_trust']:.4f}")
    print(f"  Final dynasty score    : {gf['dynasty_score']:.4f}")
    print(f"  Final unrest level     : {gf['unrest_level']:.4f}")
    print(f"\n  Output: {args.output}/{model.run_id}")


def compare_results(output_dir: str, seed: int):
    """
    After both environments finish, print a side-by-side comparison
    and run a basic statistical test on corruption difference.
    """
    import sqlite3
    import os

    dynasty_db    = Path(output_dir) / f"barangay_dynasty_{seed}.db"
    no_dynasty_db = Path(output_dir) / f"barangay_no_dynasty_{seed}.db"

    if not dynasty_db.exists() or not no_dynasty_db.exists():
        logger.warning("One or both DB files not found — skipping comparison")
        return

    def get_corruption_series(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT corruption_index FROM global_state ORDER BY tick")
        series = [row[0] for row in c.fetchall()]
        conn.close()
        return series

    d_series  = get_corruption_series(dynasty_db)
    nd_series = get_corruption_series(no_dynasty_db)

    if not d_series or not nd_series:
        return

    d_mean  = sum(d_series)  / len(d_series)
    nd_mean = sum(nd_series) / len(nd_series)
    diff    = d_mean - nd_mean

    print(f"\n{'='*50}")
    print("COMPARATIVE ANALYSIS")
    print(f"{'='*50}")
    print(f"  Dynasty   avg corruption: {d_mean:.4f}")
    print(f"  No-dynasty avg corruption: {nd_mean:.4f}")
    print(f"  Difference (D - ND)      : {diff:+.4f}")

    if diff > 0.02:
        conclusion = "Dynasty environment shows meaningfully higher corruption."
    elif diff < -0.02:
        conclusion = "Non-dynasty environment shows higher corruption (unexpected)."
    else:
        conclusion = "No significant difference in corruption levels."

    print(f"\n  Conclusion: {conclusion}")
    print(f"\n  Full data in: {output_dir}/")
    print(f"  Load in frontend: open barangay_simulation.html")


def main():
    parser = argparse.ArgumentParser(
        description="Barangay Mabuhay Political Dynasty Simulation"
    )
    parser.add_argument(
        "--env", choices=["dynasty", "no_dynasty", "both"],
        default="both",
        help="Which environment to run (default: both)"
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="Run both environments in parallel (uses 2x RAM)"
    )
    parser.add_argument(
        "--qwen", type=str, default=None,
        help="Qwen vLLM endpoint URL (e.g. http://vm-a:8000)"
    )
    parser.add_argument(
        "--output", type=str, default="output",
        help="Output directory for logs and DB (default: output/)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--ticks", type=int, default=None,
        help="Limit to N ticks (omit for full 6-year run)"
    )
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    if args.env == "dynasty":
        run_environment(True, args)

    elif args.env == "no_dynasty":
        run_environment(False, args)

    elif args.env == "both":
        if args.parallel:
            logger.info("Running both environments in parallel")
            p1 = multiprocessing.Process(
                target=run_environment, args=(True, args)
            )
            p2 = multiprocessing.Process(
                target=run_environment, args=(False, args)
            )
            p1.start(); p2.start()
            p1.join();  p2.join()
        else:
            logger.info("Running dynasty environment first")
            run_environment(True, args)
            logger.info("Running non-dynasty environment second")
            run_environment(False, args)

        compare_results(args.output, args.seed)

    elapsed = time.time() - t0
    logger.info(f"Total wall-clock time: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
