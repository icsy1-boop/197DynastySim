# sim/onit/constants.py
# Single place to change model name, tier assignments, and Smallville thresholds.

# Verify your deployment name with: curl http://localhost:8000/v1/models
MODEL_NAME    = "Qwen/Qwen2.5-27B-Instruct"
VLLM_BASE_URL = "http://localhost:8000/v1"
DB_PATH       = "dynasty_world.db"
CSV_PATH      = "barangay_agents.csv"

# Tier 1 — OnIt A2A agents (agent_id → {port, key})
TIER1_CONFIG = {
    1:  {"port": 9001, "key": "gilberto"},
    7:  {"port": 9002, "key": "isadora"},
    2:  {"port": 9003, "key": "pedro"},
    3:  {"port": 9004, "key": "cristina"},
    9:  {"port": 9005, "key": "noel"},
    12: {"port": 9006, "key": "manny"},
    8:  {"port": 9007, "key": "nicanor"},
    19: {"port": 9008, "key": "esperanza"},
    27: {"port": 9009, "key": "josefa"},
    32: {"port": 9010, "key": "joselito"},
}

# Tier 2 — direct vLLM batch inference
TIER2_ROLES = {
    "board_member", "mayor", "vice_mayor", "councilor",
    "barangay_captain", "contractor", "journalist",
    "auditor", "police", "business_owner",
}

# Smallville parity thresholds
REFLECT_THRESHOLD = 24    # trigger reflection when importance_accum >= this
PLAN_INTERVAL     = 8     # regenerate daily plan every N ticks
INTERACT_CHANCE   = 0.35  # probability two co-located tier1/2 agents interact
TIER2_BATCH_SIZE  = 20    # max concurrent vLLM requests
