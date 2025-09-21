#!/bin/bash
echo "Starting CPU-Heavy workload for 1200 sec..."

# 1) stress-ng CPU hogs (4 workers)
stress-ng --cpu 4 --timeout 1200s &

# 2) Background infinite Python loops (no indent issues now)
for i in {1..4}; do
  python3 -c "import math; [math.sqrt(j) for j in range(10000000)]" &
done

# 3) Background gcc compile loop (to mimic real developer workload)
for i in {1..2}; do
  while true; do
    gcc -O2 -o /tmp/testprog /usr/include/*.h >/dev/null 2>&1
  done &
done

wait
