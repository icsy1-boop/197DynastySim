#!/bin/bash
# start_agents.sh
# Starts the MCP server and all 10 OnIt tier-1 agents in separate tmux windows.
# Run from: ~/197DynastySim on DGX

SESSION="dynasty"
cd "$(dirname "$0")"

tmux kill-session -t $SESSION 2>/dev/null
tmux new-session -d -s $SESSION -x 220 -y 50 -n "mcp"
tmux send-keys -t $SESSION "python mcp_servers/dynasty_mcp_server.py" Enter

# agent_key:config:port
AGENTS=(
  "gilberto:gilberto:9001"
  "isadora:isadora:9002"
  "pedro:pedro:9003"
  "cristina:cristina:9004"
  "noel:noel:9005"
  "manny:manny:9006"
  "nicanor:nicanor:9007"
  "esperanza:esperanza:9008"
  "josefa:josefa:9009"
  "joselito:joselito:9010"
)

for entry in "${AGENTS[@]}"; do
  key="${entry%%:*}";  rest="${entry#*:}"
  cfg="${rest%%:*}";   port="${rest##*:}"
  tmux new-window -t $SESSION -n "$key"
  tmux send-keys -t $SESSION \
    "onit --config configs/${cfg}.yaml --a2a --a2a-port ${port}" Enter
done

echo "Dynasty sim started in tmux session '$SESSION'."
echo "Attach: tmux attach -t $SESSION"
echo ""
echo "Verify model name: curl http://localhost:8000/v1/models"
echo "Update sim/onit/constants.py MODEL_NAME if needed, then:"
echo "python orchestrator.py"
