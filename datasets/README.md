# Datasets

### Columns
- **PID**: Task identifier.
- **Timestamp / Arrival_Sec**: Arrival time of the task (in simulated *seconds*). Derived from raw logs.
- **Total_Time_Ticks**: Total execution demand of the task, expressed in *ticks* (scheduler granularity unit).
- **CPU_Usage_%**: Observed CPU usage (%).
- **IO_Read_Bytes / IO_Write_Bytes**: I/O activity per task.
- **Voluntary_ctxt_switches / Nonvoluntary_ctxt_switches**: Context switch counters.
- **Nice / Priority**: Scheduling hint fields.
- **State / Scheduling_Policy**: Categorical labels from the OS.
- some more task features.

### Files
- `cpu_workload.csv` — synthetic CPU-bound heavy load.
- `io_workload.csv` — I/O-bound heavy load.
- `batch_workload.csv` — long batch jobs.
- `real_time_workload.csv` — latency-sensitive RT tasks.
- `stress_workload.csv` — stress-ng mixed stress load.
- `mixed_realistic_workload.csv` — realistic mixed activity (editing, browsing, downloads, etc.).
- `AVIOS-dataset--training.csv` — dataset used to train classifiers

- **mixed_realistic_workload.csv** → included in repo (demo-ready, ~1.2k tasks).  
- Other workloads (CPU, IO, Batch, Real-time, Stress) are hosted on Google Drive due to size limits.

📂 Download link: [Google Drive Datasets](https://drive.google.com/drive/folders/1StTN6ZuV-hEf2z6RSj3fCP6tR2DM4plA?usp=sharing)

After downloading, place the CSV files inside `datasets/` before running notebooks or simulations.

⚠️ Units:  
- **Ticks** = simulation steps (scheduler granularity).  
- **Seconds** = wall-clock approximation for arrivals.

## Collecting live Linux traces (collector.py)

This repo includes a helper `collector.py` that samples per-process Linux state and /proc/sched fields.

Usage (run on the machine whose workload you want to record; `sudo` required for some /proc reads):

```bash
# from repo root
python3 src/tools/collector.py --interval 1.0 --out datasets/linux_dataset.csv
# or
sudo python3 src/tools/collector.py --interval 0.5 --out datasets/linux_dataset.csv
