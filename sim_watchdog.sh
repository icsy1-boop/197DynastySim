#!/bin/bash
# sim_watchdog.sh — keep both sims + both Django frontends alive across reboots
# and crashes. Run by cron @reboot and every few minutes.
#
# - Skips anything already running (tmux session present).
# - Resumes a down sim from its last autosaved step toward TARGET via
#   run_sim_resumable.sh (uses "run until", so no step math).
# - Stops touching a sim once it has reached TARGET.
# - Honors a pause flag: `touch ~/.sim_paused` to stop the watchdog from
#   restarting things (e.g. when you intentionally stop a sim).

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TARGET=4320
STORAGE=/home/student/197/generative_agents/environment/frontend_server/storage
FRONTEND=/home/student/197/generative_agents/environment/frontend_server
VENV=/home/student/197/generative_agents/venv/bin/python

[ -f /home/student/.sim_paused ] && { echo "$(date) paused"; exit 0; }

step_of() {
  $VENV -c "import json;print(json.load(open('$STORAGE/$1/reverie/meta.json'))['step'])" 2>/dev/null || echo 0
}

ensure_sim() {  # name session base anti
  local sim=$1 sess=$2 base=$3 anti=$4
  tmux has-session -t "$sess" 2>/dev/null && return
  local step; step=$(step_of "$sim")
  if [ "$step" -ge "$TARGET" ]; then
    echo "$(date) $sim done (step $step)"; return
  fi
  echo "$(date) restarting $sim from step $step -> $TARGET (antidynasty=$anti)"
  ANTIDYNASTY=$anti tmux new-session -d -s "$sess" \
    "/home/student/run_sim_resumable.sh $sim $TARGET $base"
}

ensure_django() {  # session port sim
  local sess=$1 port=$2 sim=$3
  tmux has-session -t "$sess" 2>/dev/null && return
  echo "$(date) restarting $sess on :$port"
  tmux new-session -d -s "$sess" \
    "cd $FRONTEND && DEFAULT_SIM_CODE=$sim $VENV manage.py runserver 0.0.0.0:$port"
}

ensure_django django_control      8080 sim_control_500
ensure_django django_antidynasty  8081 sim_antidynasty_500
ensure_sim    sim_control_500      sim_control      base_control_500      0
ensure_sim    sim_antidynasty_500  sim_antidynasty  base_antidynasty_500  1
