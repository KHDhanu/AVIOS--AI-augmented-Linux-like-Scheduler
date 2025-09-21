# Models

This folder contains the **trained ML models, encoders, and feature definitions** used by AVIOS.

### Files
- `resource_model_rf.pkl` — RandomForest trained on resource features.
- `interactivity_model_xgb.pkl` — XGBoost trained on interactivity features.
- `priority_model_rf.pkl` — RandomForest for task priority.
- `execution_model_rf.pkl` — RandomForest for execution length (short/medium/long).

### Encoders
- Stored in `/encoders/` (e.g., `le_resource_model.pkl`).
- Used for label ↔ index mapping.

### Feature JSON
- Stored in `/features_json/`.
- Example: `resource_features.json` = ordered list of features used at inference time.

### Training
- All models trained in `notebooks/AVIOS_part2_training_classification_models.ipynb`.
- For reproducibility, serialized models are included.  
  To retrain: open Part 2 notebook → save models → replace in this folder.

⚠️ Models and encoders are auto-loaded via data_models.py and consumed by ai_scheduler.py
