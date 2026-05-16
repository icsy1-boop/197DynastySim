"""
two_agent_run.py
Minimal Mesa-based two-agent simulation runner.
Run: python two_agent_run.py
"""

import os
import sys
from pathlib import Path

# Add sim/ to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from sim.model import BarangayModel


def main():
    # Create output directory
    output_dir = Path("output_two")
    output_dir.mkdir(exist_ok=True)
    
    # Instantiate model with two agents from CSV
    print("Initializing BarangayModel with two agents...")
    model = BarangayModel(
        scenario="competitive",
        qwen_config=None,  # No vLLM; uses rule-based fallback
        seed=42,
        agents_csv="two_agents.csv",
        output_dir=str(output_dir),
    )
    
    print(f"Model created with {len(model.agents)} agents:")
    for agent in model.agents:
        print(f"  - {agent.name} ({agent.ROLE})")
    
    print("\nRunning simulation for 200 ticks...")
    for tick in range(200):
        model.step()
        if (tick + 1) % 50 == 0:
            print(f"  Completed tick {tick + 1}/200")
    
    print("\nSimulation complete.")
    summary = model.summary()
    print("\nFinal summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
