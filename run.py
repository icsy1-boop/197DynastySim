"""
run.py
Entry point for Mabuhay Province simulation (2020-2026).

Usage:
    python run.py                              # all 3 scenarios, sequential
    python run.py --scenario dynasty_dominant  # one scenario
    python run.py --scenario reform
    python run.py --parallel                   # all 3 in parallel (3x RAM)
    python run.py --qwen http://202.92.159.240:8000  # Qwen on DGX
    python run.py --ticks 168                  # 1 sim-week (quick test)
    python run.py --seed 99
    python run.py --agents-csv barangay_agents.csv  # pre-seeded roster
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

SCENARIOS = ("dynasty_dominant", "competitive", "reform")


def run_scenario(scenario: str, args) -> dict:
    """Run one scenario; returns its summary dict."""
    from sim.model import BarangayModel
    from sim.inference.qwen_client import QwenConfig

    logger.info(f"Starting scenario: {scenario}")
    qwen_cfg = QwenConfig(base_url=args.qwen) if args.qwen else None

    model = BarangayModel(
        scenario=scenario,
        qwen_config=qwen_cfg,
        output_dir=args.output,
        seed=args.seed,
        agents_csv=args.agents_csv,
    )

    if args.ticks:
        for i in range(args.ticks):
            if model.clock.is_done:
                break
            model.step()
            if i % 24 == 0:
                print(f"  [{scenario}] {model.clock.label}")
        model.db.close()
    else:
        model.run()   # run() calls db.close() internally

    summary = model.summary()
    _print_summary(summary)
    return summary


def _print_summary(s: dict):
    scenario = s["scenario"]
    gf       = s["global_factors"]
    print(f"\n{'='*55}")
    print(f"SUMMARY: {scenario.upper()}")
    print(f"{'='*55}")
    print(f"  Final year          : {s['clock']['calendar_year']}")
    print(f"  Corruption index    : {gf['corruption_index']:.4f}")
    print(f"  Welfare index       : {gf['welfare_index']:.4f}")
    print(f"  Citizen trust       : {gf['citizen_trust']:.4f}")
    print(f"  Dynasty score       : {gf['dynasty_score']:.4f}")
    print(f"  Unrest level        : {gf['unrest_level']:.4f}")
    print(f"  Pandemic severity   : {gf['pandemic_severity']:.4f}")
    print(f"  Infrastructure      : {gf['infrastructure_quality']:.4f}")
    print(f"  Output              : {s['run_id']}")


def compare_results(output_dir: str, seed: int):
    import sqlite3

    results = {}
    for sc in SCENARIOS:
        db_path = Path(output_dir) / f"mabuhay_{sc}_{seed}.db"
        if not db_path.exists():
            logger.warning(f"DB not found for scenario '{sc}': {db_path}")
            continue
        conn = sqlite3.connect(db_path)
        c    = conn.cursor()
        c.execute("SELECT AVG(corruption_index), AVG(welfare_index), AVG(citizen_trust) "
                  "FROM global_state")
        row = c.fetchone()
        conn.close()
        results[sc] = {"corruption": row[0], "welfare": row[1], "trust": row[2]}

    if len(results) < 2:
        return

    print(f"\n{'='*55}")
    print("COMPARATIVE ANALYSIS — MABUHAY PROVINCE 2020-2026")
    print(f"{'='*55}")
    print(f"{'Metric':<22} {'Dynasty':>12} {'Competitive':>12} {'Reform':>12}")
    print("-" * 60)
    for metric in ("corruption", "welfare", "trust"):
        row = f"  {metric.capitalize():<20}"
        for sc in SCENARIOS:
            val = results.get(sc, {}).get(metric)
            row += f" {val:>12.4f}" if val is not None else f" {'N/A':>12}"
        print(row)

    # Key finding
    d  = results.get("dynasty_dominant", {}).get("corruption", 0)
    r  = results.get("reform",           {}).get("corruption", 0)
    diff = d - r
    print(f"\n  Dynasty vs. Reform corruption gap: {diff:+.4f}")
    if diff > 0.03:
        print("  Finding: Reform scenario meaningfully reduces corruption.")
    elif diff < -0.03:
        print("  Finding: Unexpected — reform scenario shows higher corruption.")
    else:
        print("  Finding: No significant corruption difference across scenarios.")
    print(f"\n  Full data in: {output_dir}/")
    print(f"  Visualize  : open barangay_simulation.html")


def main():
    parser = argparse.ArgumentParser(
        description="Mabuhay Province Political Dynasty Simulation 2020-2026"
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS) + ["all"],
        default="all",
        help="Which scenario to run (default: all three)"
    )
    parser.add_argument("--parallel",   action="store_true",
                        help="Run all scenarios in parallel (3x RAM)")
    parser.add_argument("--qwen",       type=str, default=None,
                        help="Qwen vLLM URL (e.g. http://202.92.159.240:8000)")
    parser.add_argument("--output",     type=str, default="output")
    parser.add_argument("--seed",       type=int, default=42)
    parser.add_argument("--ticks",      type=int, default=None,
                        help="Limit to N ticks (omit for full 7-year run)")
    parser.add_argument("--agents-csv", type=str, default=None,
                        dest="agents_csv",
                        help="Path to barangay_agents.csv (generated by agent_creation.py)")
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    scenarios_to_run = SCENARIOS if args.scenario == "all" else (args.scenario,)

    if args.parallel and len(scenarios_to_run) > 1:
        logger.info(f"Running {len(scenarios_to_run)} scenarios in parallel")
        procs = [
            multiprocessing.Process(target=run_scenario, args=(sc, args))
            for sc in scenarios_to_run
        ]
        for p in procs: p.start()
        for p in procs: p.join()
    else:
        for sc in scenarios_to_run:
            run_scenario(sc, args)

    if len(scenarios_to_run) > 1:
        compare_results(args.output, args.seed)

    elapsed = time.time() - t0
    logger.info(f"Total wall-clock time: {elapsed:.1f}s ({elapsed/60:.1f} min)")


if __name__ == "__main__":
    main()
