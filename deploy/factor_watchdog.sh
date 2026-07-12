#!/usr/bin/env bash
# Keep the FACTOR AMD stack alive on the organizer instance (which restarts often).
# A server counts as UP if it answers HTTP at all (200/401/404 = process listening);
# only "no response" (connection refused / timeout) triggers a re-run of start_all.sh.
cd /workspace
reach() { c=$(curl -s -o /dev/null -m "${2:-6}" -w '%{http_code}' "$1" 2>/dev/null); [ -n "$c" ] && [ "$c" != 000 ]; }
allup() {
  reach http://127.0.0.1:8000/v1/models &&   # chat
  reach http://127.0.0.1:7860/           &&   # embeddings
  reach http://127.0.0.1:8501/                # image
}
while true; do
  allup || bash /workspace/start_all.sh >>/workspace/start_all.log 2>&1
  sleep 30
done
