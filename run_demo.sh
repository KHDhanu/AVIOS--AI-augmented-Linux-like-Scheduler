#!/bin/bash
# Reproduce a demo workload run for AVIOS
# Runs preprocessing, AI scheduler sim, Linux baseline sim, and comparison metrics

set -e  # exit on error

# Step 1: Preprocess dataset
echo "🔄 Preprocessing dataset..."
python -m src.scheduler.data_model \
  --input datasets/mixed_realistic_workload.csv \
  --out ai_scheduler_input.csv

# Step 2: Run AI Scheduler Simulation
echo "🚀 Running AI-augmented scheduler simulation..."
python -m src.scheduler.ai_simulator \
  --input ai_scheduler_input.csv \
  --out results/mixed_realistic_workload/

# Copy outputs for metrics.py compatibility
cp results/mixed_realistic_workload/ai_scheduler_logs.csv .
cp results/mixed_realistic_workload/ai_scheduler_task_metrics.csv .

# Step 3: Run Linux Baseline Simulation
echo "🖥️ Running Linux baseline scheduler simulation..."
python -m src.scheduler.linux_simulator \
  --input ai_scheduler_input.csv \
  --out results/mixed_realistic_workload/

# Copy outputs for metrics.py compatibility
cp results/mixed_realistic_workload/linux_baseline_logs.csv .
cp results/mixed_realistic_workload/linux_baseline_task_metrics.csv .

# Step 4: Compute & Plot Metrics
echo "📊 Comparing results (AI vs Linux)..."
python -m src.scheduler.metrics

echo "✅ Demo complete! Check results/mixed_realistic_workload/ for raw outputs and plots."
