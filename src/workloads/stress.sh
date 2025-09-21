#!/bin/bash
DURATION=1200
echo "Starting Stress workload for $DURATION sec..."

# Massive short sleeps
for i in {1..2000}; do
  (sleep 0.1) &
done

# Stress-ng combo
stress-ng --cpu 4 --io 4 --vm 2 --hdd 1 --timeout $DURATION &

# Random mix of commands
for i in {1..100}; do
  (dd if=/dev/zero of=tempfile$i bs=1M count=5; rm tempfile$i) &
done

# Many pings (network stress)
for i in {1..50}; do
  ping -i 0.2 8.8.8.8 > /dev/null &
done

sleep $DURATION
echo "Stress workload finished."
