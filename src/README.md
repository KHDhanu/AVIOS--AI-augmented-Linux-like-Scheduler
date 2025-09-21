# Source Code

This folder contains the main implementation of AVIOS.

- **scheduler/** – Core scheduling logic (AI scheduler, Linux baseline simulators, metrics, task models).
- **models/** – Trained ML models (Random Forest, XGBoost) and feature definitions.
- **workloads/** – Synthetic workload scripts (CPU, IO, Batch, Real-time, Stress, Mixed realistic).
- **tools/** – Helper utilities (collector for Linux traces).

Entry points:
- `src/scheduler/ai_simulator.py` – Run AI-augmented scheduler.
- `src/scheduler/linux_simulator.py` – Run Linux baseline scheduler.

