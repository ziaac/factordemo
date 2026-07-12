#!/usr/bin/env bash
# One command to run after the organizer restarts the AMD instance. Idempotent & safe to repeat:
# (re)start the model stack only if needed, wait for the chat model to load, arm the keep-alive
# watchdog, then report the status of all three servers + GPU VRAM.
cd /workspace

# 1) start the stack if the chat endpoint is not answering yet
if ! curl -sf -o /dev/null http://127.0.0.1:8000/v1/models; then
  echo "servers down -> start_all.sh"
  bash /workspace/start_all.sh >>/workspace/start_all.log 2>&1
fi

# 2) wait for Gemma 27B to finish loading (can take ~1-2 min after a cold start)
printf "waiting :8000 "
for _ in $(seq 1 90); do
  curl -sf -o /dev/null http://127.0.0.1:8000/v1/models && break
  printf "."; sleep 2
done; echo

# 3) arm the watchdog AFTER the stack is up (avoids a double start)
python3 /workspace/_arm_watchdog.py

# 4) status report
echo "---- STATUS ----"
for pair in "8000:gemma-3-27b chat" "7860:bge-m3 embed" "8501:sdxl image"; do
  port=${pair%%:*}; name=${pair#*:}
  (exec 3<>/dev/tcp/127.0.0.1/"$port") 2>/dev/null && echo "  UP   $port  $name" || echo "  DOWN $port  $name"
done
ps aux | grep -E "llama_cpp|embed_server|sdxl_server" | grep -v grep | awk '{printf "  pid %-6s %s\n",$2,$NF}'
rocm-smi --showmeminfo vram 2>/dev/null | grep -iE "Used" | head -1
echo "watchdog log: tail -f /workspace/watchdog.log"
