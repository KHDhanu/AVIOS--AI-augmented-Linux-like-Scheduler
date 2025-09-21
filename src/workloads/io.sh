#!/bin/bash
DURATION=1200
echo "Starting IO-Heavy workload for $DURATION sec..."

# Disk/file spam
for i in {1..100}; do
  dd if=/dev/zero of=tempfile$i bs=1M count=50 &
done

# File searching
for i in {1..20}; do
  find /usr -name "*.conf" > /dev/null 2>&1 &
done

# Grep recursion
for i in {1..20}; do
  grep -r "main" /usr > /dev/null 2>&1 &
done

# Stress I/O tool
stress-ng --io 4 --timeout $DURATION &

sleep $DURATION
rm -f tempfile*
echo "IO-Heavy workload finished."
