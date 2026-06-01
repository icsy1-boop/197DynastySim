#!/bin/bash
# run_sim_resumable.sh <sim_name> <target_step> <fork_base>
# Resume-aware sim launcher used by the watchdog. Uses "run until <target>",
# so it works whether the sim is fresh (forks from base at step 0) or resuming
# from an autosaved meta.json — it always drives toward <target_step>.
# Waits for the LLM/embedding endpoints before starting so a reboot that brings
# VM B up before VM A doesn't burn steps on all-SKIP.

cd /home/student/197/generative_agents/reverie/backend_server
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1
export ABLITERATED_ENDPOINT=http://10.158.24.216:8000
export ABLITERATED_MODEL=huihui-ai/Huihui-Qwen3.5-4B-abliterated
export QWEN_ENDPOINT=${QWEN_ENDPOINT:-http://202.92.159.240:8007}
export QWEN_MODEL=${QWEN_MODEL:-Qwen/Qwen3.6-27B}
export EMBEDDING_ENDPOINT=http://10.158.24.216:8002
export EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5

VENV=/home/student/197/generative_agents/venv/bin/python
SIM_NAME=${1:-sim_control_500}
TARGET=${2:-4320}
FORK_BASE=${3:-base_control_500}

# Derive ANTIDYNASTY + agent CSV from the SIM NAME (robust across tmux/cron, no
# reliance on inherited env). The CSV must match this sim's population or
# corruption/election/news read the wrong agents.
case "$SIM_NAME" in
  *antidynasty*)
    export ANTIDYNASTY=1
    export BARANGAY_CSV=/home/student/197/barangay_agents_500_dynasty_antidynasty.csv ;;
  *)
    export ANTIDYNASTY=0
    export BARANGAY_CSV=/home/student/197/barangay_agents_500_dynasty.csv ;;
esac

# ── Wait for all three endpoints (curl is not installed; use python urllib) ──
echo "[resumable] waiting for endpoints..."
$VENV - <<'PYWAIT'
import urllib.request, time
eps = ["http://10.158.24.216:8000/v1/models",
       "http://10.158.24.216:8002/v1/models",
       "http://202.92.159.240:8007/v1/models"]
for url in eps:
    for _ in range(150):  # up to ~5 min each
        try:
            urllib.request.urlopen(url, timeout=5); break
        except Exception:
            time.sleep(2)
PYWAIT
echo "[resumable] endpoints ready (or timed out); starting $SIM_NAME -> step $TARGET"

$VENV headless_env.py "$SIM_NAME" &
HEADLESS_PID=$!

printf "${FORK_BASE}\n${SIM_NAME}\nrun until ${TARGET}\nfin\n" | \
  $VENV -u reverie.py 2>&1 | tee -a /tmp/${SIM_NAME}.log

kill $HEADLESS_PID 2>/dev/null
