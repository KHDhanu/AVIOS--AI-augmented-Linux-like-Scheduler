# ================================
# data_model.py — Preprocess + Save Dataset for AI Scheduler
# ================================
import pandas as pd
import joblib
import json
import numpy as np
import os
import argparse
from pathlib import Path

# -------------------------------
# Globals
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR.parent / "models"

# ----------------------------------
# Load models + encoders
# ----------------------------------
rf_resource_model = joblib.load(MODELS_DIR / "resource_model_rf.pkl")
le_resource = joblib.load(MODELS_DIR / "encoders/le_resource_model.pkl")

xgb_inter_model = joblib.load(MODELS_DIR / "interactivity_model_xgb.pkl")
le_inter = joblib.load(MODELS_DIR / "encoders/le_interactivity_model.pkl")

rf_priority_model = joblib.load(MODELS_DIR / "priority_model_rf.pkl")
le_priority = joblib.load(MODELS_DIR / "encoders/le_priority_model.pkl")

rf_execution_model = joblib.load(MODELS_DIR / "execution_model_rf.pkl")
le_execution = joblib.load(MODELS_DIR / "encoders/le_execution_model.pkl")

print("✅ Models + LabelEncoders loaded.")

# ----------------------------------
# Load feature lists
# ----------------------------------
resource_feats      = json.load(open(MODELS_DIR / "features_json/resource_features.json"))
interactivity_feats = json.load(open(MODELS_DIR / "features_json/interactivity_features.json"))
priority_feats      = json.load(open(MODELS_DIR / "features_json/priority_features.json"))
execution_feats     = json.load(open(MODELS_DIR / "features_json/execution_features.json"))

print("✅ Feature sets loaded.")


# ----------------------------------
# Preprocessing function
# ----------------------------------
def preprocess_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Clean + engineer features to match training pipeline."""

    # Convert VmRSS (kB → float)
    if 'VmRSS' in df.columns:
        df['VmRSS'] = (
            df['VmRSS']
            .astype(str)
            .str.replace('kB', '', regex=False)
            .astype(float)
            .fillna(0.0)
        )

    # Safe numeric conversion
    num_cols = [
        'CPU_Usage_%','Nice','Priority','Total_Time_Ticks',
        'Elapsed_Time_sec','Voluntary_ctxt_switches','Nonvoluntary_ctxt_switches',
        'IO_Read_Bytes','IO_Write_Bytes','IO_Read_Count','IO_Write_Count',
        'se.sum_exec_runtime','se.load.weight'
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Avoid divide by zero
    df['Elapsed_Time_sec'] = df['Elapsed_Time_sec'].replace(0, 1e-5)

    # Engineered features
    df['avg_cpu_time'] = df['Total_Time_Ticks'] / df['Elapsed_Time_sec']
    df['cpu_to_elapsed_ratio'] = df['CPU_Usage_%'] / df['Elapsed_Time_sec']
    df['interactivity_score'] = (
        df['Voluntary_ctxt_switches'] / (df['Nonvoluntary_ctxt_switches'] + 1)
    )
    df['is_sleeping'] = (
        df['State'].astype(str).str.lower().str.contains('sleeping', na=False).astype(int)
    )

    return df


# ----------------------------------
# Main CLI
# ----------------------------------
def main():
    parser = argparse.ArgumentParser(description="Preprocess dataset for AI Scheduler")
    parser.add_argument("--input", required=True, help="Path to raw dataset CSV")
    parser.add_argument("--out", default="ai_scheduler_input.csv", help="Output CSV path")

    args = parser.parse_args()

    # Load dataset
    df = pd.read_csv(args.input)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.sort_values(by="Timestamp")

    print(f"📊 Original dataset shape: {df.shape}")

    # Keep only first occurrence of each PID
    first_occ = df.drop_duplicates(subset=["PID"], keep="first").reset_index(drop=True)
    print(f"📊 First occurrence dataset shape: {first_occ.shape}")

    # Apply preprocessing
    first_occ = preprocess_dataset(first_occ)
    first_occ['Arrival_Sec'] = (
        (first_occ['Timestamp'] - first_occ['Timestamp'].iloc[0])
        .dt.total_seconds()
        .astype(int)
    )

    # Save
    out_path = Path(args.out)
    first_occ.to_csv(out_path, index=False)
    print(f"✅ Saved {out_path} (clean + preprocessed)")


if __name__ == "__main__":
    main()
