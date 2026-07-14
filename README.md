# SecureBank: FinSpark'26 Hackathon Demo
> Problem Statement 2: AI-Driven Correlation of Cybersecurity Telemetry & Transactional Behaviour

This is the enhanced, modularized, and secure version of the SecureBank demo. It provides the foundation for an advanced anti-fraud and Threat Intelligence system by capturing both backend security events (e.g., Impossible Travel, Quantum-Harvest Risks) and frontend behavioral telemetry (e.g., Mouse Movements, Keystroke Timing).

## Features Implemented
- **Modular Backend:** The monolithic Flask application is now split into scalable `routes/` (auth, banking, telemetry).
- **Encrypted Traffic (HTTPS):** All traffic is routed over a self-signed TLS/SSL certificate to ensure secure transit.
- **Behavioral Telemetry System:** Client-side JavaScript captures user interactions to help detect non-human/bot behaviors or account takeovers.
- **Admin Network Graph:** Visualizes accounts as nodes and transactions as edges to help detect Money Mules and cyclical money laundering patterns.
- **Modern UI:** Professional, premium dashboard interface replacing the basic prototype.

---

## How to Run

### 1. Install Dependencies
Make sure you have Flask and PyOpenSSL installed:
```bash
pip install flask pyopenssl werkzeug
```

### 2. Start the Server
Run the Flask application:
```bash
python app.py
```

### 3. Access the Application
Open your browser and navigate to:
**https://127.0.0.1:5000**
*(Note: Because we are using an `adhoc` self-signed certificate for local HTTPS, your browser will show a "Your connection is not private" warning. Click "Advanced" -> "Proceed to 127.0.0.1" to view the app).*

---

## 🤖 Guide: Implementing the AI Correlation Model

The hardcoded correlation engine has been explicitly removed so that you can plug in your own Machine Learning model to solve the hackathon problem statement. 

Here is what you need to do next to connect your ML model:

### Step 1: Train Your Model
Use Python data science libraries (like `scikit-learn` or `pandas`) to train a model. You can extract the dummy data from the `bank.db` SQLite database (specifically the `transactions` and `security_events` tables). Your model should learn to classify a transaction as Fraud (`1`) or Not Fraud (`0`) based on:
- Transaction Amount
- Time since last `high` or `critical` severity security event.
- Anomalies in behavioral telemetry (mouse movements, WPM).

### Step 2: Create an Inference Endpoint (Optional)
If you build your ML model as a separate Python script or FastAPI service, you can expose a `/predict` endpoint that takes transaction and telemetry data and returns a fraud score.

### Step 3: Connect to the Transfer Pipeline
Open `routes/banking.py` and locate the `transfer()` function. Right before the transaction is finalized, inject your AI call:

```python
# Inside routes/banking.py -> transfer()

# 1. Fetch recent security events for the user
recent_events = db.execute("SELECT * FROM security_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (user["id"],)).fetchall()

# 2. Pass data to your AI Model (Pseudo-code)
fraud_probability, explanation = my_ai_model.predict(
    amount=amount, 
    events=recent_events,
    behavior=recent_telemetry
)

# 3. Flag the transaction if threshold is exceeded
if fraud_probability > 0.85:
    db.execute(
        "UPDATE transactions SET flagged = 1, ai_fraud_score = ?, flag_reason = ? WHERE id = ?", 
        (fraud_probability, explanation, txn_id)
    )
    db.commit()
```

By completing Step 3, your application will meet the Hackathon requirements: correlating cybersecurity telemetry with transactional behavior, detecting quantum risks, and providing explainable AI-driven threat intelligence.
