#!/bin/bash
# run_dual_sim.sh — launch control + anti-dynasty sims simultaneously,
# each with its own Django frontend on a different port.
#
# Usage: bash run_dual_sim.sh [steps]
# Default steps: 4320 (6 months at 1 hr/step)

STEPS=${1:-4320}
VENV=/home/student/197/generative_agents/venv/bin/python
FRONTEND=/home/student/197/generative_agents/environment/frontend_server

# ── Django port 8080: control sim ─────────────────────────────────────────
tmux new-session -d -s django_control \
  "cd $FRONTEND && DEFAULT_SIM_CODE=sim_control_500 $VENV manage.py runserver 0.0.0.0:8080"

# ── Django port 8081: anti-dynasty sim ────────────────────────────────────
tmux new-session -d -s django_antidynasty \
  "cd $FRONTEND && DEFAULT_SIM_CODE=sim_antidynasty_500 $VENV manage.py runserver 0.0.0.0:8081"

# ── Control sim ───────────────────────────────────────────────────────────
tmux new-session -d -s sim_control \
  "/home/student/run_week_prob.sh sim_control_500 $STEPS base_control_500"

# ── Anti-dynasty sim ──────────────────────────────────────────────────────
tmux new-session -d -s sim_antidynasty \
  "ANTIDYNASTY=1 /home/student/run_week_prob.sh sim_antidynasty_500 $STEPS base_antidynasty_500"

echo "Launched:"
echo "  Control sim    → http://10.158.24.217:8080  (tmux: sim_control, django_control)"
echo "  Anti-dynasty   → http://10.158.24.217:8081  (tmux: sim_antidynasty, django_antidynasty)"
echo ""
echo "Monitor:"
echo "  tmux attach -t sim_control"
echo "  tmux attach -t sim_antidynasty"
echo "  tail -f /tmp/sim_control_500.log"
echo "  tail -f /tmp/sim_antidynasty_500.log"
echo "  grep 'STEP.*DONE\\|ELECTION\\|NEWS' /tmp/sim_control_500.log | tail -10"
