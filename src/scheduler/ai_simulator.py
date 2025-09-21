# ================================
# SIMULATION DRIVER (AI Scheduler)
# ================================

from .task import Task
from .ai_scheduler import AIScheduler

import pandas as pd
import time
from collections import defaultdict

# --- Config ---
INPUT_CSV = "ai_scheduler_input.csv"
LOG_OUT   = "ai_scheduler_logs.csv"
TASK_MET  = "ai_scheduler_task_metrics.csv"
MAX_SIM_SECONDS_MULT = 5
PROGRESS_EVERY = 1000

# 1) Load dataset & prepare arrivals
df = pd.read_csv(INPUT_CSV)
if "Timestamp" in df.columns:
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')

if 'Arrival_Sec' not in df.columns:
    if 'Timestamp' in df.columns and not df['Timestamp'].isnull().all():
        start_ts = df['Timestamp'].min()
        df['Arrival_Sec'] = ((df['Timestamp'] - start_ts).dt.total_seconds()
                             .fillna(0).astype(int))
    else:
        df['Arrival_Sec'] = 0

df = df.sort_values(by='Arrival_Sec').reset_index(drop=True)
last_arrival = int(df['Arrival_Sec'].max())
print(f"📊 Loaded dataset: {len(df)} tasks, last arrival @ {last_arrival}s")

# Build arrivals dict for fast lookup
arrivals = defaultdict(list)
for _, row in df.iterrows():
    arrivals[int(row['Arrival_Sec'])].append(row)

# 2) Initialize scheduler
scheduler = AIScheduler(num_cores=4)   # tune cores if needed
print("✅ AIScheduler initialized.")

# 3) Compute recommended max_ticks
if "Total_Time_Ticks" in df.columns:
    total_work = df["Total_Time_Ticks"].fillna(0).astype(float).sum()
elif "se.sum_exec_runtime" in df.columns:
    total_work = df["se.sum_exec_runtime"].fillna(0).astype(float).sum()
else:
    total_work = 0.0

num_cores = scheduler.num_cores if hasattr(scheduler, "num_cores") else 4

max_ticks = 70000
print(f"Using max_ticks = {max_ticks} "
      f"(last_arrival={last_arrival}, total_work={total_work}, cores={num_cores})")

# 4) Run simulation loop
current_time = 0
start_time_wall = time.time()

while True:
    # Admit arrivals at this tick
    if current_time in arrivals:
        for row in arrivals[current_time]:
            t = Task.from_row(row)
            scheduler.admit(t, current_time)

    # Run one tick
    scheduler.tick(current_time)

    # Progress print
    if current_time % PROGRESS_EVERY == 0 and current_time > 0:
        print(f"⏱ tick {current_time} — queues empty? {scheduler.all_queues_empty()}")

    # Termination condition (stop only after all arrivals & queues empty)
    if current_time > last_arrival and scheduler.all_queues_empty():
        print("All tasks completed and no pending arrivals -> stopping.")
        break

    current_time += 1
    if current_time > max_ticks:
        print("⚠️ Reached safety max_ticks — stopping simulation to avoid runaway.")
        break

wall_elapsed = time.time() - start_time_wall
print(f"✅ Simulation finished in {wall_elapsed:.1f}s (simulated ticks: {current_time})")

# 5) Export logs & per-task metrics
logs_df = scheduler.export_logs()
logs_df.to_csv(LOG_OUT, index=False)
print(f"📑 Logs saved to {LOG_OUT} (rows: {len(logs_df)})")

task_metrics_df = scheduler.export_task_metrics()
task_metrics_df.to_csv(TASK_MET, index=False)
print(f"📊 Per-task metrics saved to {TASK_MET} (rows: {len(task_metrics_df)})")

# 6) Print aggregate metrics in table
agg = scheduler.compute_aggregate_metrics()
print("\n📈 Aggregate metrics (AI Scheduler):")
for k, v in agg.items():
    print(f"  {k}: {v}")
