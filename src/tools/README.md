# Tools

Utility scripts for data collection and system integration.

- **collector.py** – Linux process scheduler feature collector.
  - Collects per-process PCB-style features from `/proc`.
  - Output is a CSV trace used for ML training and simulation.

### Usage
```bash
sudo python3 tools/collector.py --interval 1.0 --out datasets/linux_dataset.csv
