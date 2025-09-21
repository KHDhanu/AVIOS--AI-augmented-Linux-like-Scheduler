# Notebooks

The notebooks are organized in a logical pipeline.  
Run in this order for full reproducibility:

1. **AVIOS_part1_manual_task_classification.ipynb**  
   - Feature inspection, rules, and initial manual labeling.

2. **AVIOS_part2_training_classification_models.ipynb**  
   - Training ML classifiers (RandomForest, XGBoost).
   - Models + encoders saved to `/src/models/`.

3. **AVIOS_part3_ai_scheduler_vs_linux_baseline.ipynb**  
   - Simulator run (baseline vs AI).
   - Exports per-task metrics & aggregate CSVs.

4. **workloads_*.ipynb**  
   - Benchmark notebooks per workload type (CPU, IO, Batch, Real-time, Stress, Mixed realistic).
   - Load metrics & plots for each workload.

5. **ablation_study/**  
   - Contains exploratory ablation notebooks:  
     - `AI-Scheduler_assignment.ipynb`  
     - `AI-vruntime_&_quantum.ipynb`  
     - `AI-Combination.ipynb`  

⚠️ Part 1 → 3 are the **core reproducible pipeline**.  
Workload notebooks = evaluation.  
Ablation = research/exploratory.
