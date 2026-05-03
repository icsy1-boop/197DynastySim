# Barangay Mabuhay — Political Dynasty Simulation

Agent-based simulation of a 5,000-person Philippine municipality.
Tests whether removing political dynasties reduces corruption.

## Project structure

```
barangay_sim/
├── run.py                  ← entry point
├── requirements.txt
└── sim/
    ├── model.py            ← Mesa model (main world)
    ├── agents/
    │   ├── base.py         ← BarangayAgent base class
    │   ├── roles.py        ← All 17 role subclasses
    │   ├── relationships.py← NetworkX trust graph
    │   └── names.py        ← Filipino name generator + family assignment
    ├── world/
    │   ├── state.py        ← GlobalFactors + SimClock
    │   └── locations.py    ← All 18 town locations
    ├── inference/
    │   └── qwen_client.py  ← Qwen vLLM client + prompt builder
    └── db/
        └── logger.py       ← SQLite + JSON day log writer
```

## Setup (VM B)

```bash
pip install -r requirements.txt
```

## Running

```bash
# Full 6-year run, both environments, sequential
python run.py

# Both in parallel (needs ~2x RAM)
python run.py --parallel

# Quick test — 100 ticks only
python run.py --ticks 100

# Point to Qwen on VM A
python run.py --qwen http://<vm-a-ip>:8000

# Dynasty only
python run.py --env dynasty --qwen http://<vm-a-ip>:8000

# Reproducible run
python run.py --seed 99
```

## Output

```
output/
├── barangay_dynasty_42.db         ← SQLite, full relational data
├── barangay_no_dynasty_42.db
├── barangay_dynasty_42/
│   └── days/
│       ├── y01_d001.json          ← Daily snapshot for frontend replay
│       ├── y01_d002.json
│       └── ...
└── barangay_no_dynasty_42/
    └── days/
        └── ...
```

## VM A setup (Qwen inference)

```bash
pip install vllm
python -m vllm.entrypoints.api_server \
    --model Qwen/Qwen-14B \
    --port 8000 \
    --max-num-batched-tokens 4096
```

Then point VM B at it:
```bash
python run.py --qwen http://<vm-a-internal-ip>:8000
```

If VM A is unreachable, the simulation falls back to rule-based
agent decisions automatically — no crashes.

## Key design decisions

- **Event-driven inference**: Qwen is only called every 4 ticks for
  political agents, and only when triggered for citizens.
  Between calls, agents execute their committed task in Python.

- **Dynasty as structural advantage**: In the dynasty environment,
  family members share elevated relationship floors, checkers
  auto-approve family members' budgets, and dynasty score feeds
  back to suppress audit strength.

- **Corruption as emergent**: No agent is hardcoded to be corrupt.
  Corruption emerges from trait combinations (high greed + low
  integrity) meeting low audit strength and high dynasty score.

- **Null hypothesis**: Both environments start with identical
  conditions and agent wealth. Only the family_id assignments
  and anti-dynasty constraint differ.

## Frontend

Open `barangay_simulation.html` in any browser.
- Live mode: connects to VM B's FastAPI on :5000
- Replay mode: load day JSON files from output/ directory
