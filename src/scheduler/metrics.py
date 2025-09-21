#-----------------------
# aggregate metrics
#---------------------

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load AI and Linux data
ai_logs = pd.read_csv("ai_scheduler_logs.csv")
ai_tasks = pd.read_csv("ai_scheduler_task_metrics.csv")
linux_logs = pd.read_csv("linux_baseline_logs.csv")
linux_tasks = pd.read_csv("linux_baseline_task_metrics.csv")

# ---- AI Metrics ----
def compute_metrics_ai(tasks: pd.DataFrame, logs: pd.DataFrame):
    metrics = {}
    # From per-task metrics
    metrics["Avg Waiting Time"] = tasks["waiting"].mean()
    metrics["Avg Turnaround Time"] = tasks["turnaround"].mean()
    metrics["Avg Response Time"] = tasks["response"].mean()
    metrics["Fairness (Jain Index)"] = (tasks["execution_time"].sum()**2) / (
        len(tasks) * (np.sum(tasks["execution_time"]**2) + 1e-9)
    )
    # From logs
    run_events = logs[logs["event"] == "RUN"]
    total_run_time = len(run_events)
    total_time = logs["time"].max() - logs["time"].min() + 1
    metrics["CPU Utilization (%)"] = 100 * total_run_time / (total_time * logs["core"].nunique())
    metrics["Throughput (tasks/unit time)"] = len(tasks) / total_time
    return metrics

# ---- Linux Metrics ----
def compute_metrics_linux(tasks: pd.DataFrame, logs: pd.DataFrame):
    metrics = {}
    metrics["Avg Waiting Time"] = tasks["waiting"].mean()
    metrics["Avg Turnaround Time"] = tasks["turnaround"].mean()
    metrics["Avg Response Time"] = tasks["response"].mean()
    metrics["Fairness (Jain Index)"] = (tasks["execution_time"].sum()**2) / (
        len(tasks) * (np.sum(tasks["execution_time"]**2) + 1e-9)
    )
    run_events = logs[logs["event"] == "RUN"]
    total_run_time = len(run_events)
    total_time = logs["time"].max() - logs["time"].min() + 1
    metrics["CPU Utilization (%)"] = 100 * total_run_time / (total_time * logs["core"].nunique())
    metrics["Throughput (tasks/unit time)"] = len(tasks) / total_time
    return metrics

# Compute both
ai_metrics = compute_metrics_ai(ai_tasks, ai_logs)
linux_metrics = compute_metrics_linux(linux_tasks, linux_logs)

# Compare side by side
comparison_df = pd.DataFrame([ai_metrics, linux_metrics], index=["AI Scheduler", "Linux Baseline"])
print("\n📊 Full Metrics Comparison:\n", comparison_df)

# Plot numeric metrics
comparison_df.T.plot(kind="bar", figsize=(12,7))
plt.title("AI Scheduler vs Linux Baseline - Metrics Comparison")
plt.ylabel("Value")
plt.xticks(rotation=30, ha="right")
plt.legend(title="Scheduler")
plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()
