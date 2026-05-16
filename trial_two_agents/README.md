# DynastySim — Two-Agent Local Trial

A minimal Mesa-based political simulation scaffold for testing locally before deployment to DGX.

## Quick Start

### 1. Install dependencies

```bash
cd trial_two_agents
python -m pip install -r requirements.txt
```

### 2. Run the Mesa-only simulation

```bash
python two_agent_run.py
```

Expected output:
- Simulates **Esperanza Garcia** (journalist) and **Manny Dimalanta** (vice-mayor) for 200 ticks
- Logs progress every 50 ticks
- Outputs final summary and saves day logs to `output_two/`

### 3. Inspect logs

After the run completes, check:
- `output_two/` — daily event logs in JSON format
- Console — summary of agent actions and world state

## File Structure

```
trial_two_agents/
├── sim/                          # Core Mesa simulation code (copied from root)
│   ├── model.py                  # BarangayModel — main engine
│   ├── agents/
│   │   ├── base.py              # BarangayAgent base class
│   │   ├── roles.py             # Role subclasses (Journalist, ViceMayor, etc.)
│   │   ├── relationships.py     # RelationshipGraph (NetworkX)
│   │   └── names.py             # random_name() and family ID assignment
│   ├── db/
│   │   └── logger.py            # SimLogger (SQLite + JSON day logs)
│   ├── inference/
│   │   └── qwen_client.py       # QwenClient (vLLM with fallback)
│   └── world/
│       ├── locations.py         # Barangay zone map
│       └── state.py             # Global state tracking
├── two_agents.csv               # Two-agent CSV (Esperanza + Manny)
├── two_agent_run.py             # Driver script
├── configs/                      # Agent configs for MCP/FastAPI runs
│   ├── esperanza.yaml           # OnIt/vLLM config for Esperanza
│   └── manny.yaml               # OnIt/vLLM config for Manny
├── mcp_servers/
│   └── dynasty_mcp_server.py    # MCP tools for networked agents
├── fastapi_server.py            # FastAPI + WebSocket UI server
├── requirements.txt             # Python dependencies
└── README.md                     # This file

output_two/                       # Generated at runtime
├── day_logs_*.json              # Daily event logs
└── sqlite.db                    # Simulation database (if populated)
```

## Next Steps

### For Mesa-only local testing:
- Run `python two_agent_run.py` multiple times with different seeds to validate stability
- Inspect `output_two/day_logs_*.json` to verify agent behavior

### For networked MCP + FastAPI testing:
1. Ensure vLLM Qwen endpoint is running (or modify `configs/*.yaml` to point to local Ollama)
2. Start MCP server: `python mcp_servers/dynasty_mcp_server.py`
3. Start FastAPI UI: `uvicorn fastapi_server:app --host 0.0.0.0 --port 5000`
4. Use OnIt with `configs/esperanza.yaml` and `configs/manny.yaml` to spawn networked agents

### For scaling to DGX:
- Copy scaffold contents to DGX VM A
- Adjust `QwenConfig` base_url in `sim/inference/qwen_client.py` to point to DGX vLLM
- Scale `two_agents.csv` to include more agents (copy rows from `barangay_agents.csv`)
- Run distributed simulation with process orchestration (see main repo `orchestrator.py`)

## Troubleshooting

**Import errors (ModuleNotFoundError: sim)?**
- Ensure you're running `python two_agent_run.py` from the `trial_two_agents/` folder
- The script adds `trial_two_agents/` to PYTHONPATH automatically

**Qwen endpoint unavailable warning?**
- This is expected; the simulation uses rule-based fallback
- For vLLM-backed decisions, set up the endpoint and adjust `QwenConfig.base_url`

**Database errors?**
- Delete `dynasty_world.db` and run again
- The simulator creates it on first run

## License

This is a development sandbox. Adapt to your needs.
