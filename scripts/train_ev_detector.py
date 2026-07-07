import os
import glob

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from src.ev_detector import FEATURE_COLUMNS, SAMPLING_RATE, extract_features_from_capture


TRAIN_DIR = "train"
TEST_DIR = "test"
MODEL_PATH = "models/ev_detector.joblib"


def normalize_label(label):
    label = str(label).lower().strip()
    label = label.replace("-", "_").replace(" ", "_")

    if label in ["ev", "electric", "electric_vehicle"]:
        return "ev"

    if label in ["non_ev", "nonev", "non_electric", "petrol", "diesel", "gas", "on_ev"]:
        return "non_ev"

    return label


def load_folder(folder_path):
    files = glob.glob(os.path.join(folder_path, "*.csv"))
    if not files:
        raise ValueError(f"No CSV files found in folder: {folder_path}")

    all_features = []
    for file_path in files:
        df = pd.read_csv(file_path)
        df.columns = [str(column).lower().strip() for column in df.columns]

        if "time_sec" not in df.columns:
            df["time_sec"] = df.index / SAMPLING_RATE

        for column in ["time_sec", "x", "y", "z", "label"]:
            if column not in df.columns:
                raise ValueError(f"Column '{column}' missing in file: {file_path}")

        label = normalize_label(df["label"].dropna().iloc[0])
        capture = df[["time_sec", "x", "y", "z"]].copy()
        for column in ["time_sec", "x", "y", "z"]:
            capture[column] = pd.to_numeric(capture[column], errors="coerce")
        capture = capture.dropna().sort_values("time_sec").reset_index(drop=True)

        features = extract_features_from_capture(capture)
        features["label"] = label
        features["source_file"] = os.path.basename(file_path)
        all_features.append(features)

    return pd.concat(all_features, ignore_index=True)


def main():
    train_features = load_folder(TRAIN_DIR)
    test_features = load_folder(TEST_DIR)

    x_train = train_features[FEATURE_COLUMNS]
    y_train = train_features["label"]
    x_test = test_features[FEATURE_COLUMNS]
    y_test = test_features["label"]

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight="balanced",
        max_depth=None,
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("Classification Report:")
    print(classification_report(y_test, y_pred))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS}, MODEL_PATH)
    print(f"Saved {MODEL_PATH}")


if __name__ == "__main__":
    main()
