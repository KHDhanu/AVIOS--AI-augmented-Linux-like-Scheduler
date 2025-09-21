#!/bin/bash
DURATION=1200
echo "Starting Real-Time workload for $DURATION sec..."

# Video/audio encoding (RT-like jobs)
ffmpeg -f lavfi -i testsrc=duration=300:size=1280x720:rate=30 out.mp4 -y &
ffmpeg -f lavfi -i sine=frequency=1000:duration=300 audio.wav -y &

# High-priority simulated RT tasks
for i in {1..5}; do
  sudo chrt -f 80 stress-ng --cpu 1 --timeout 300 &
done

# Periodic small scripts (simulate sensor read)
for i in {1..50}; do
  (while true; do echo "ping" > /dev/null; sleep 0.5; done) &
done

sleep $DURATION
echo "Real-Time workload finished."
