import pandas as pd
import numpy as np
from scipy.stats import ttest_rel, wilcoxon
import os

def cohen_d(x, y):
    diff = x - y
    return diff.mean() / diff.std(ddof=1)

def bootstrap_ci(data, n_boot=1000, alpha=0.05):
    means = []
    for _ in range(n_boot):
        sample = np.random.choice(data, size=len(data), replace=True)
        means.append(sample.mean())
    lower = np.percentile(means, 100*alpha/2)
    upper = np.percentile(means, 100*(1-alpha/2))
    return lower, upper

workloads = [
    "cpu_workload", "io_workload", "batch_workload",
    "real_time_workload", "stress_workload", "mixed_realistic_workload"
]

out_rows = []

for w in workloads:
    base = pd.read_csv(f"results/{w}/linux_baseline_task_metrics.csv")
    ai   = pd.read_csv(f"results/{w}/ai_scheduler_task_metrics.csv")

    for metric in ["turnaround", "response"]:
        if metric not in base.columns or metric not in ai.columns:
            print(f"⚠️ Skipping {w} - {metric} (not found in CSV)")
            continue

        x = base[metric].dropna().values
        y = ai[metric].dropna().values

        if len(x) == 0 or len(y) == 0:
            print(f"⚠️ No data for {w} - {metric}")
            continue

        diff = x - y

        # stats
        t_stat, p_ttest = ttest_rel(x, y)
        try:
            w_stat, p_wilcox = wilcoxon(diff)
        except:
            p_wilcox = np.nan  # if all diffs are zero

        d = cohen_d(x, y)
        ci_low, ci_high = bootstrap_ci(diff)

        out_rows.append({
            "Workload": w,
            "Metric": metric,
            "Baseline_Mean": x.mean(),
            "AI_Mean": y.mean(),
            "Mean_Diff": diff.mean(),
            "Cohen_d": d,
            "Paired_ttest_p": p_ttest,
            "Wilcoxon_p": p_wilcox,
            "95%CI_low": ci_low,
            "95%CI_high": ci_high
        })

df = pd.DataFrame(out_rows)
os.makedirs("results", exist_ok=True)
df.to_csv("results/stat_summary.csv", index=False)
print("✅ Saved results/stat_summary.csv")
