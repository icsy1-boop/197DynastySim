#!/bin/bash
# snapshot_replay.sh <sim_code>
# Make a watchable /demo replay of a sim WITHOUT stopping it (no "fin" needed).
# compress_sim_storage.py reads the live movement/*.json + personas + meta and
# writes compressed_storage/<sim>/master_movement.json, which the /demo player
# loads for smooth, adjustable-speed (1-6x) playback up to the current step.
# Re-run anytime to refresh the snapshot with newer steps.
#
# Then watch:  http://10.158.24.217:8080/demo/<sim_code>/1/3/
#   (path is /demo/<sim>/<start_step>/<play_speed>/ ; speed 1..6)

set -e
SIM=${1:?usage: snapshot_replay.sh <sim_code>}
GA=/home/student/197/generative_agents
VENV=$GA/venv/bin/python
COMPRESSED=$GA/environment/frontend_server/compressed_storage/$SIM

# compress_sim_storage.copy uses shutil.copytree which fails if the target
# already exists, so clear any previous snapshot first.
rm -rf "$COMPRESSED"

# Run from reverie/ (its paths are relative to there) with backend_server on the
# path so `from global_methods import *` resolves.
cd "$GA/reverie"
PYTHONPATH="$GA/reverie/backend_server" "$VENV" -c \
  "from compress_sim_storage import compress; compress('$SIM')"

echo "Snapshot ready for $SIM (up to the latest completed step)."
echo "Watch: http://10.158.24.217:8080/demo/$SIM/1/3/"
