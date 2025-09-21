# Results

This folder contains **per-workload logs, metrics, and plots** comparing the Linux baseline vs AI-augmented scheduler.

### Subfolders
- `cpu_workload/` — metrics & plots for CPU-bound traces.
- `io_workload/` — I/O heavy workload results.
- `batch_workload/` — batch long jobs.
- `real_time_workload/` — latency-sensitive RT jobs.
- `stress_workload/` — stress-ng stress tests.
- `mixed_realistic_workload/` — realistic mix of interactive + background tasks.
- `ablation_study/` — isolated experiments (assignment only, vruntime and quantum only, combined).

### Each folder contains
- `ai_scheduler_task_metrics.csv`
- `linux_baseline_task_metrics.csv`
- `metrics_&_plot.pdf` — *main summary plots* for quick comparison.

- `ai_scheduler_logs.csv`  --- heavy files(not uploaded) ---> can be generated from running demo/notebooks
- `linux_baseline_logs.csv` --- heavy files(not uploaded) ---> can be generated from running demo/notebooks

🔑 **Main results to look at**:  
Open the PDF inside each workload folder → shows turnaround, response, fairness, and utilization comparisons.
