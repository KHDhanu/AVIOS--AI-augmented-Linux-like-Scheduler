#!/bin/bash
echo "Starting Batch workload for 1200 sec..."

# 1) stress-ng I/O + VM (simulate batch jobs like backups, compaction, big data crunch)
stress-ng --vm 2 --vm-bytes 1G --timeout 1200s &

# 2) Matrix multiplications in Python (fixed syntax)
for i in {1..2}; do
  python3 - <<'EOF' &
import numpy as np, time
x = np.random.rand(3000, 3000)
for j in range(50):
    x = x @ x
    time.sleep(5)
EOF
done

# 3) Replace kernel compile with big tar extraction + compression (batch-like workload)
for i in {1..2}; do
  while true; do
    tar -cf /tmp/test.tar /usr/bin >/dev/null 2>&1
    gzip -f /tmp/test.tar
    gunzip -f /tmp/test.tar.gz
  done &
done

wait
