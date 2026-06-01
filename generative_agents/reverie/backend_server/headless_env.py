"""
headless_env.py

Headless environment forwarder — replaces the Phaser3 frontend for test runs.

The reverie.py backend loop:
  1. Reads  environment/{step}.json  (agent positions)
  2. Runs LLM planning / movement
  3. Writes movement/{step}.json     (target positions + paths)
  4. Waits for environment/{step+1}.json

This script watches for each new movement file and immediately writes the
next environment file using the target positions, so the sim can run without
a browser.

Usage (run alongside reverie.py):
  python headless_env.py <sim_name> [--steps N]

  --steps N  stop after forwarding N environment files (default: unlimited)
"""
import argparse
import json
import os
import sys
import time

STORAGE_ROOT = "../../environment/frontend_server/storage"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sim", help="Simulation storage name (e.g. test100)")
    parser.add_argument("--steps", type=int, default=None,
                        help="Stop after forwarding this many steps")
    args = parser.parse_args()

    sim_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), STORAGE_ROOT, args.sim))

    move_dir = os.path.join(sim_dir, "movement")
    env_dir  = os.path.join(sim_dir, "environment")

    if not os.path.isdir(sim_dir):
        print(f"Waiting for sim dir: {sim_dir} ...")
        while not os.path.isdir(sim_dir):
            time.sleep(0.5)
        print("Sim dir created, starting.")

    step = 0
    forwarded = 0
    print(f"headless_env: watching {sim_dir}")
    print(f"Waiting for movement/{step}.json ...")

    while True:
        if args.steps is not None and forwarded >= args.steps:
            print(f"headless_env: reached {args.steps} steps, done.")
            break

        move_path = os.path.join(move_dir, f"{step}.json")
        if not os.path.exists(move_path):
            time.sleep(0.2)
            continue

        # Read movement file.
        try:
            with open(move_path) as f:
                move_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            time.sleep(0.1)
            continue

        # Build next environment file: carry forward all positions from current
        # env, then update with movement targets (agents that timed out keep
        # their current position so reverie.py doesn't KeyError on them).
        curr_env_path = os.path.join(env_dir, f"{step}.json")
        try:
            with open(curr_env_path) as f:
                env = json.load(f)
        except (json.JSONDecodeError, OSError):
            env = {}
        for persona_name, data in move_data.get("persona", {}).items():
            mv = data.get("movement", [0, 0])
            env[persona_name] = {"x": mv[0], "y": mv[1]}

        next_env_path = os.path.join(env_dir, f"{step + 1}.json")
        with open(next_env_path, "w") as f:
            json.dump(env, f)

        forwarded += 1
        print(f"  step {step} → environment/{step + 1}.json written "
              f"({len(env)} agents)", flush=True)
        step += 1


if __name__ == "__main__":
    main()
