# SecureBank Anti-Fraud System (Finspark Hackathon)

SecureBank is a prototype web application demonstrating a modern, multi-layered digital banking protection system. Built for the **Finspark Hackathon**, it integrates security telemetry, real-time client-side behavioral biometrics, and a machine learning classifier to safeguard accounts from account takeover and automated transaction scripts (bots).

---

## 🏗️ Architectural Overview

The system consists of three core layers that protect every transaction request:

1. **Client Telemetry**: Gathers mouse movements, click tracking, and typing biometrics to distinguish humans from scripts.
2. **Machine Learning Classifier**: Evaluates transaction risk using a Random Forest model trained on telemetry and transaction data.
3. **Explainable AI (LLM)**: Provides real-time contextual explanations when transactions are flagged or blocked.

### Codebase Organization

*   **`app.py`**: The entry point for the Flask server.
*   **`database.py`**: SQLite database initialization (users, accounts, transactions, and security events).
*   **`routes/`**:
    *   **`auth.py`**: User authentication, tracks failed logins, and flags unfamiliar devices.
    *   **`telemetry.py`**: Collects client-side behavioral tracking (typing speed, mouse movements).
    *   **`banking.py`**: Executes transfers, assesses fraud risks via the ML classifier, and uses LLM (Ollama) for explainability.
*   **Machine Learning System**:
    *   **`generate_data.py`**: Synthesizes normal and bot-like telemetry rows.
    *   **`train_model.py`**: Trains the Random Forest Classifier.

---

## 🧠 Key Technologies & Mechanisms

### 1. Behavioral Biometrics Tracking
Unlike standard password/OTP layers, behavioral biometrics observe *how* an action is performed:
*   **Robotic Mouse Movement**: Detects teleportation, straight-line trajectories, or minimal travel distance.
*   **Typing Speed Anomalies**: Flags instantaneous pasting of payloads (e.g., > 200 WPM).

### 2. Machine Learning Fraud Classifier
When a user attempts a transfer, the server assesses:
*   **Geo-Distance calculation**: Uses the Haversine formula to compute distance from home location.
*   **Random Forest Scoring**: Computes a fraud probability score based on factors like amount, login attempts, device risk, and client biometrics. Transactions exceeding a **60% fraud probability** are blocked.

### 3. Explainable AI (LLM Explanations)
*   **Local LLM (Ollama)**: Dynamically generates friendly, professional explanations based on threat flags (e.g., using `gemma3:4b`).
*   **Deterministic Fallback**: Uses rule-based templates if the LLM is offline.

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Python installed along with the required standard and ML packages:

```bash
pip install flask flask-cors requests scikit-learn pandas numpy joblib pyopenssl
```

*Note: For the Explainable AI features to work, ensure [Ollama](https://ollama.com/) is installed and running locally with the `gemma3:4b` model (or update the code to match your preferred model).*

### Running the Application

1. **Start the Backend Server**:
   Run the Flask server from your project workspace:
   ```bash
   python app.py
   ```
   *The server runs on **`https://127.0.0.1:5000`** with a self-signed SSL certificate (`ssl_context='adhoc'`).*

2. **Run the Automated Demo**:
   While the server is running, execute the provided script to see the system in action:
   ```bash
   python demo.py
   ```
   **Demo Flow**:
   * Registers dummy users.
   * Executes a normal transfer (succeeds).
   * Injects anomalous telemetry (high typing speed, robotic mouse).
   * Attempts a fraudulent transfer (blocked by ML classifier).
   * Displays the AI explanation returned by the server.

---

## 📊 The Command Center (Admin View)

You can monitor the system visually by opening `https://127.0.0.1:5000` (or `https://127.0.0.1:5000/admin`) in your web browser:

1. **Sign in as Admin**: Use the username **`admin`** and password **`pass`**.
2. **View the Threat Dashboard**:
   * Monitor flagged transactions and global threat intel logs.
   * Inspect the **Anti-Fraud Network Graph** to detect money mule rings or cyclic transaction patterns.
   * Manually simulate telemetry events to see how risk scores change in real-time.

---
*Built with ❤️ for the Finspark Hackathon.*
