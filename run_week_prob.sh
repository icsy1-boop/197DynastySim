#!/bin/bash
# run_week_prob.sh <sim_name> <steps> [fork_base]
# ANTIDYNASTY and the agent CSV are derived from the SIM NAME (robust — no
# reliance on inline env propagating through tmux): any sim whose name contains
# "antidynasty" runs the anti-dynasty treatment with the demoted-officials CSV;
# everything else is the dynasty control.
cd /home/student/197/generative_agents/reverie/backend_server
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1
export ABLITERATED_ENDPOINT=http://10.158.24.216:8000
export ABLITERATED_MODEL=huihui-ai/Huihui-Qwen3.5-4B-abliterated
export QWEN_ENDPOINT=${QWEN_ENDPOINT:-http://202.92.159.240:8007}
export QWEN_MODEL=${QWEN_MODEL:-Qwen/Qwen3.6-27B}
export EMBEDDING_ENDPOINT=http://10.158.24.216:8002
export EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5

SIM_NAME=${1:-week_prob_reflect}
STEPS=${2:-336}
FORK_BASE=${3:-base_barangay}

case "$SIM_NAME" in
  *antidynasty*)
    export ANTIDYNASTY=1
    export BARANGAY_CSV=/home/student/197/barangay_agents_500_dynasty_antidynasty.csv ;;
  *)
    export ANTIDYNASTY=0
    export BARANGAY_CSV=/home/student/197/barangay_agents_500_dynasty.csv ;;
esac

/home/student/197/generative_agents/venv/bin/python headless_env.py "$SIM_NAME" &
HEADLESS_PID=$!

printf "${FORK_BASE}\n${SIM_NAME}\nrun ${STEPS}\nfin\n" | \
  /home/student/197/generative_agents/venv/bin/python -u reverie.py 2>&1 | \
  tee /tmp/${SIM_NAME}.log

kill $HEADLESS_PID 2>/dev/null
