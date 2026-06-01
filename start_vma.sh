#!/bin/bash
# start_vma.sh  — bring up BOTH vLLM servers on VM A (the GPU box) after a reboot.
# Idempotent: skips a server that is already listening. GPU split keeps both in
# the 48 GB card (embeddings 0.15 ~7GB + LLM 0.65 ~31GB = ~38GB, ~9GB headroom).
export PATH="/home/student/.venv/bin:$PATH"
VLLM=/home/student/.venv/bin/vllm

up() { ss -tln 2>/dev/null | grep -q ":$1 "; }

# ── Embeddings (nomic) on :8002 ──────────────────────────────────────────────
if up 8002; then
  echo "[vma] :8002 already up"
else
  echo "[vma] starting embeddings on :8002"
  tmux kill-session -t embed_server 2>/dev/null
  tmux new-session -d -s embed_server \
    "export PATH=/home/student/.venv/bin:\$PATH; \
     $VLLM serve nomic-ai/nomic-embed-text-v1.5 --trust-remote-code \
     --gpu-memory-utilization 0.15 --port 8002 2>&1 | tee /tmp/embed.log"
  # wait until it grabs its memory before starting the LLM (avoid a GPU race)
  for i in $(seq 1 120); do up 8002 && break; sleep 2; done
  echo "[vma] :8002 ready (or timed out)"
fi

# ── LLM (4B abliterated) on :8000 ────────────────────────────────────────────
if up 8000; then
  echo "[vma] :8000 already up"
else
  echo "[vma] starting LLM on :8000"
  tmux kill-session -t llm_server 2>/dev/null
  tmux new-session -d -s llm_server \
    "/home/student/start_llm.sh 2>&1 | tee /tmp/llm_start.log"
fi

echo "[vma] startup invoked. Watch: tmux attach -t llm_server / embed_server"
