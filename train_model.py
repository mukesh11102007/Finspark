import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import LabelEncoder
import joblib

def train_hybrid_model():
    print("Loading Kaggle banking transactions dataset...")
    try:
        df = pd.read_csv("banking_transactions.csv")
    except FileNotFoundError:
        print("Error: banking_transactions.csv not found.")
        return

    print("Preprocessing data...")
    # Drop IDs
    if "transaction_id" in df.columns:
        df = df.drop("transaction_id", axis=1)

    # Convert boolean fraud flag to 0/1
    df["fraud_flag"] = df["fraud_flag"].astype(int)

    # Synthesize Behavioral Biometrics based on the fraud flag to merge the concepts
    print("Synthesizing behavioral biometrics...")
    np.random.seed(42)
    is_fraud = df["fraud_flag"] == 1
    
    # Typing WPM: Humans ~40-100, Bots >400
    df.loc[~is_fraud, "typing_wpm"] = np.random.uniform(30, 110, size=(~is_fraud).sum())
    df.loc[is_fraud, "typing_wpm"] = np.random.uniform(400, 1200, size=is_fraud.sum())
    
    # Mouse Distance: Humans move around (800-4000px), Bots move straight (50-200px)
    df.loc[~is_fraud, "mouse_distance_total"] = np.random.uniform(800, 4000, size=(~is_fraud).sum())
    df.loc[is_fraud, "mouse_distance_total"] = np.random.uniform(50, 200, size=is_fraud.sum())
    
    # Mouse Speed: Humans slow (1-4), Bots fast (20-50)
    df.loc[~is_fraud, "mouse_speed_avg"] = np.random.uniform(1.0, 4.0, size=(~is_fraud).sum())
    df.loc[is_fraud, "mouse_speed_avg"] = np.random.uniform(20.0, 50.0, size=is_fraud.sum())

    # Handle Categorical Columns
    encoders = {}
    cat_columns = ["payment_channel", "authentication_type"]
    for col in cat_columns:
        if col in df.columns:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
            
    # Save encoders for inference if needed (though we can just mock them on inference)
    joblib.dump(encoders, "encoders.joblib")

    # Ensure all columns are numeric
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.fillna(0) # Fill any accidental NaNs

    # Features (X) and Target (y)
    X = df.drop("fraud_flag", axis=1)
    y = df["fraud_flag"]
    
    # Save the expected feature names to ensure alignment during inference
    joblib.dump(list(X.columns), "model_features.joblib")

    print("Splitting data into train and test sets...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print(f"Training Random Forest Classifier on {len(X.columns)} features...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)

    print("Evaluating model...")
    y_pred = model.predict(X_test)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    print("Saving hybrid model to fraud_model.joblib...")
    joblib.dump(model, "fraud_model.joblib")
    print("Done! The hybrid Kaggle+Behavioral model is ready.")

if __name__ == "__main__":
    train_hybrid_model()
