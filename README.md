# SBX Anti-Fraud System (Finspark Hackathon)

SBX is a prototype web application demonstrating a modern, multi-layered digital banking protection system. Built for the **Finspark Hackathon**, it integrates security telemetry, real-time client-side behavioral biometrics, and a machine learning classifier to safeguard accounts from account takeover and automated transaction scripts (bots).

---

## 🏗️ Architectural Overview

The system consists of three core layers that protect every transaction request:

1. **Client Telemetry**: Gathers mouse movements, click tracking, and typing biometrics to distinguish humans from scripts.
2. **Machine Learning Classifier**: Evaluates transaction risk using a Random Forest model trained on telemetry and transaction data.
3. **Explainable AI (LLM)**: Provides real-time contextual explanations when transactions are flagged or blocked.

### Codebase Organization

*   **`app.py`**: The entry point for the Flask backend server.
*   **`demo.py`**: Automated CLI script simulating real-world attacks (Bots, VPN anomalies, Money Mules).
*   **`reset_db.py`**: Utility script to easily wipe and reset the SQLite database.
*   **`admin.html`**: The premium frontend Security Operations Center (SOC) dashboard.
*   **`hack.html`**: A dedicated "Advanced Persistent Threat" simulator to execute attacks via a hacker console.
*   **`database.py`**: SQLite database initialization (users, accounts, transactions, and security events).
*   **`routes/`**:
    *   **`auth.py`**: User authentication, tracks failed logins, and flags unfamiliar devices. Includes a stealth backdoor (`HACKER_BYPASS`) for demo purposes.
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
The system uses a Kaggle-sourced dataset (`banking_transactions.csv`) robustly augmented with synthesized biometric features to train a Random Forest model.

**Features included in the Random Forest Classifier:**
*   **Base Transaction Data:** `transaction_amount`, `login_attempts`, `device_risk_score`, `transfer_frequency`, `anomaly_score`, `account_age_days`, `transaction_time_hour`, `failed_transactions_last_30d`, `avg_monthly_balance`, `daily_transaction_count`, `geo_distance_km`, `session_duration_minutes`, `transaction_velocity_score`, `card_present_flag`, `international_transaction_flag`, `suspicious_ip_flag`.
*   **Categorical Features:** `payment_channel` and `authentication_type` (label-encoded).
*   **Synthesized Behavioral Biometrics:** 
    *   `typing_wpm` (Humans: 30-110, Bots: 400-1200)
    *   `mouse_distance_total` (Humans: 800-4000px, Bots: 50-200px straight lines)
    *   `mouse_speed_avg` (Humans: 1-4, Bots: 20-50)

**How data is fed to the model during a live transaction:**
When a transfer request hits the `/api/transfer` endpoint (`routes/banking.py`), the system dynamically constructs the feature vector before passing it to the ML model:
1. **Live Context Gathering**: The system queries the database for the user's base context (account age, balance) and real-time security events (e.g., recent `behavioral_anomaly` or `vpn_anomaly` flags).
2. **Dynamic Biometrics & Geo-Location**: Rather than hardcoding static bot metrics, the system calculates a simulated geographic distance using the **Haversine formula** based on recent VPN/travel anomalies. For behavioral biometrics, if the telemetry layer has flagged a recent anomaly, it feeds extreme values (e.g., 600 WPM, 100px mouse distance) to the model; otherwise, it feeds normal human baseline values.
3. **Threat Scoring Overlays**: Device risk scores and login attempts are dynamically elevated if the sender or recipient is under an active threat status.
4. **Feature Alignment**: All features are combined into a dictionary, including necessary static defaults (e.g., categorical encoding for Web Banking/OTP), and loaded into a Pandas DataFrame. The dataframe columns are strictly ordered against `model_features.joblib` (saved during training) to ensure perfect alignment.
5. **Prediction**: The dataframe is passed to the Random Forest's `predict_proba()` method. If the returned fraud probability exceeds **60%**, the transaction is blocked immediately.

### 3. Explainable AI (LLM Explanations)
*   **Local LLM (Ollama)**: Dynamically generates friendly, professional explanations based on threat flags (e.g., using `gemma3:4b`).
*   **Deterministic Fallback**: Uses rule-based templates if the LLM is offline.

---

## 🚀 Getting Started (Run/Install)

### Prerequisites
Make sure you have Python installed. The project uses a `requirements.txt` file for easy setup.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Environment Variables (Optional but recommended)
# Copy .env.example to .env and set your FLASK_SECRET_KEY and ADMIN_PASSWORD
cp .env.example .env
```

*Note: For the Explainable AI features to work, ensure [Ollama](https://ollama.com/) is installed and running locally with the `gemma3:4b` model. If Ollama is unavailable, the system will gracefully log a warning and fall back to rule-based explanations.*

### Running the Application

1. **Start the Backend Server**:
   Run the Flask server from your project workspace:
   ```bash
   python app.py
   ```
   *The server runs on **`http://127.0.0.1:5000`**.*

2. **Run the Automated Demo**:
   While the server is running, execute the provided script to see the system in action:
   ```bash
   python demo.py
   ```
   **Demo Flow**:
   * **Scenario 1:** Normal Human Transfer (Succeeds).
   * **Scenario 2:** Robotic Behavior (Injects bot telemetry, blocked by ML Engine).
   * **Scenario 3:** The 'Phantom' Attack (Impossible travel VPN anomaly + large transfer, blocked by ML Engine).
   * **Scenario 4:** The 'Salami Slicing' Mule (Compromised endpoint beacon + micro transfer, blocked by ML Engine).
   * **Scenario 5:** Admin Review & Feedback Loop (Marks the blocked transfer as a false positive).

3. **Resetting the Database**:
   If reviewers want to start fresh, simply run the reset script to recreate the `bank.db` and the default admin account:
   ```bash
   python reset_db.py
   ```

---

## 📊 The Command Center (Admin View)

![Admin Dashboard Mockup](C:/Users/HAPPY/.gemini/antigravity-ide/brain/09c670c9-dbc8-4a37-823d-371f20ba9329/admin_dashboard_mockup_1784109466180.png)

You can monitor the system visually by opening `https://127.0.0.1:5000/admin` in your web browser:

1. **Sign in as Admin**: Use the username **`admin`** and password **`pass`** (unless changed via `.env`).
2. **View the Threat Dashboard**:
   * Monitor flagged transactions and global threat intel logs along with Explainable AI texts.
   * Provide direct feedback (e.g., mark as 'False Positive') to improve the model.
   * Inspect the **Anti-Fraud Network Graph** to detect money mule rings or cyclic transaction patterns.

---

## 🔒 Security & Production Notes

> [!WARNING]
> This repository contains hardcoded configurations (like self-signed certificates and placeholder `.env` files) designed specifically for the hackathon demo to ensure a frictionless evaluation. 

For a true production environment, the following hardening steps are mandatory:
* **Secrets Management**: Remove all hardcoded default passwords. Use a secure vault (e.g., AWS Secrets Manager, HashiCorp Vault) and strictly enforce `.env` usage.
* **Rate Limiting**: Implement strict rate limits on the `/api/login` and `/api/transfer` endpoints to prevent brute-force attacks and abuse.
* **Model Security**: The `fraud_model.joblib` should be stored securely and loaded into memory from a private bucket, rather than residing in the public file structure.
* **Authentication Hardening**: Enforce true JWT-based auth or secure HTTP-only cookies instead of basic session IDs, and require MFA for admin routes.
* **Frontend Telemetry Privacy**: The stretch-goal telemetry capture script currently logs raw X/Y coordinates for the demo. In production, this data must be anonymized, heavily secured, and explicitly consented to by the user.

---
*Built with ❤️ for the Finspark Hackathon.*
