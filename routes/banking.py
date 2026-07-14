from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_db
from routes.auth import require_login
import requests
import json

banking_bp = Blueprint("banking", __name__)

def generate_ai_explanation(reason_details):
    prompt = (
        f"Explain to a banking user in one short, professional, and friendly sentence "
        f"why their transaction was blocked or flagged. Reason: {reason_details}. "
        f"Do not include any greeting, JSON, or meta-commentary, just the sentence itself."
    )
    
    # Try local Ollama with installed gemma3:4b first, then other tags as fallback
    models = ["gemma3:4b", "gemma:2b", "gemma:latest", "llama3"]
    for model in models:
        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=3.0
            )
            if r.status_code == 200:
                explanation = r.json().get("response", "").strip()
                if explanation:
                    return explanation
        except Exception:
            continue
            
    # Rule-based fallback if Ollama is unavailable
    reason_lower = reason_details.lower()
    if "insufficient funds" in reason_lower:
        return "The transfer could not be completed because your account balance is insufficient for this amount."
    elif "sender" in reason_lower:
        return "As a precaution, this transaction was blocked because your account currently has active security alerts."
    elif "receiver" in reason_lower:
        return "This transfer was flagged because the recipient's account has elevated security and risk indicators."
    elif "fraud" in reason_lower or "ai blocked" in reason_lower:
        return "Our security system flagged this transaction due to patterns resembling unauthorized transfer activity."
    else:
        return f"This transaction was flagged due to security policy guidelines: {reason_details}"

@banking_bp.route("/api/accounts", methods=["GET"])
def accounts():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    db = get_db()
    rows = db.execute("SELECT * FROM accounts WHERE user_id = ?", (user["id"],)).fetchall()
    return jsonify([dict(r) for r in rows])


@banking_bp.route("/api/transfer", methods=["POST"])
def transfer():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401

    data = request.get_json(force=True)
    to_account = (data.get("to_account") or "").strip()
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid amount"}), 400

    if amount <= 0:
        return jsonify({"error": "amount must be positive"}), 400

    db = get_db()
    from_acc = db.execute("SELECT * FROM accounts WHERE user_id = ?", (user["id"],)).fetchone()
    if not from_acc:
        return jsonify({"error": "sender account not found"}), 404

    to_acc = db.execute("SELECT * FROM accounts WHERE account_number = ?", (to_account,)).fetchone()
    if not to_acc:
        return jsonify({"error": "recipient account not found"}), 404

    # Fetch receiver details
    receiver = db.execute("SELECT * FROM users WHERE id = ?", (to_acc["user_id"],)).fetchone()

    # Check threat status of sender and receiver
    sender_threat = user["risk_level"] in ("elevated", "high", "critical")
    receiver_threat = receiver and receiver["risk_level"] in ("elevated", "high", "critical")

    now = datetime.utcnow().isoformat()

    if from_acc["balance"] < amount:
        reason = "Insufficient funds to complete the transfer."
        ai_exp = generate_ai_explanation(reason)
        db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, flag_reason) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (from_acc["account_number"], to_account, amount, now, "failed", ai_exp),
        )
        db.commit()
        return jsonify({"error": "insufficient funds", "reason": ai_exp}), 400

    # ML Model Integration
    flagged = False
    flag_reason = None
    fraud_prob = 0.0
    
    import joblib
    import os
    import pandas as pd
    import math
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371 # km
        dlat = math.radians(lat2-lat1)
        dlon = math.radians(lon2-lon1)
        a = math.sin(dlat/2)*math.sin(dlat/2) + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)*math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    model_path = "fraud_model.joblib"
    features_path = "model_features.joblib"
    
    if os.path.exists(model_path) and os.path.exists(features_path):
        fraud_model = joblib.load(model_path)
        model_features = joblib.load(features_path)
        
        # Calculate real DB features
        user_dict = dict(user)
        created_at = datetime.fromisoformat(user_dict.get("created_at") or datetime.utcnow().isoformat())
        account_age_days = max(0, (datetime.utcnow() - created_at).days)
        
        home_lat = user_dict.get("home_lat") or 20.0
        home_lon = user_dict.get("home_lon") or 78.0
        
        # Check for VPN/Impossible travel to simulate geo distance
        last_event = db.execute("SELECT event_type FROM security_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user["id"],)).fetchone()
        if last_event and last_event["event_type"] in ["vpn_anomaly", "impossible_travel"]:
            txn_lat, txn_lon = home_lat + 20.0, home_lon + 20.0 # Far away
        else:
            txn_lat, txn_lon = home_lat + 0.01, home_lon + 0.01 # Close by
            
        geo_dist = haversine(home_lat, home_lon, txn_lat, txn_lon)
        
        # Behavioral telemetry
        recent_anomaly = db.execute("SELECT 1 FROM security_events WHERE user_id = ? AND event_type='behavioral_anomaly' ORDER BY timestamp DESC LIMIT 1", (user["id"],)).fetchone()
        if recent_anomaly:
            mouse_dist, typing_wpm, mouse_speed = 100.0, 600.0, 30.0 # Bot
        else:
            mouse_dist, typing_wpm, mouse_speed = 2000.0, 60.0, 2.0  # Human
            
        # Adjust features based on threat level of sender and receiver
        login_attempts = user_dict.get("failed_login_attempts") or 0
        device_risk_score = user_dict.get("device_risk_score") or 0.0
        if sender_threat:
            device_risk_score += 50.0
            login_attempts += 5
        if receiver_threat:
            device_risk_score += 30.0

        # Construct feature dict matching Kaggle dataset + Behavioral
        feature_dict = {
            "transaction_amount": amount,
            "login_attempts": login_attempts,
            "device_risk_score": device_risk_score,
            "transfer_frequency": 10 if (sender_threat or receiver_threat) else 5,
            "anomaly_score": 0.8 if (sender_threat or receiver_threat) else 0.1,
            "account_age_days": account_age_days,
            "transaction_time_hour": datetime.utcnow().hour,
            "failed_transactions_last_30d": 0,
            "avg_monthly_balance": float(from_acc["balance"]),
            "daily_transaction_count": 1,
            "geo_distance_km": geo_dist,
            "session_duration_minutes": 5,
            "transaction_velocity_score": 10.0,
            "payment_channel": 1, # Label encoded Web Banking
            "authentication_type": 1, # Label encoded OTP
            "card_present_flag": 0,
            "international_transaction_flag": 1 if geo_dist > 1000 else 0,
            "suspicious_ip_flag": 1 if last_event and last_event["event_type"] == "vpn_anomaly" else 0,
            "typing_wpm": typing_wpm,
            "mouse_distance_total": mouse_dist,
            "mouse_speed_avg": mouse_speed
        }
        
        # Ensure exact column order
        input_df = pd.DataFrame([feature_dict])[model_features]
        
        fraud_prob = fraud_model.predict_proba(input_df)[0][1]
        
    # Flag if fraud_prob > 0.60, or if either sender or receiver is under active threat
    if fraud_prob > 0.60 or sender_threat or receiver_threat:
        flagged = True
        
        # Determine explanation context
        if sender_threat:
            core_reason = f"the sender has active security threats (risk level: {user['risk_level']})"
        elif receiver_threat:
            core_reason = f"the recipient's account has high risk indicators (risk level: {receiver['risk_level']})"
        else:
            core_reason = f"the anti-fraud model detected suspicious transaction patterns resembling ML fraud score of {fraud_prob*100:.1f}%"
            
        # Generate AI explanation
        ai_exp = generate_ai_explanation(core_reason)
        flag_reason = f"AI Blocked: {ai_exp}"
        
        # Insert flagged/blocked transaction as FAILED (amount NOT deducted)
        cur = db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, flag_reason, ai_fraud_score) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "failed", flag_reason, fraud_prob),
        )
        txn_id = cur.lastrowid
        db.commit()
        
        return jsonify({
            "error": flag_reason,
            "flagged": True,
            "flag_reason": flag_reason,
            "transaction_id": txn_id
        }), 400
    else:
        # Perform actual balance transfer ONLY if the transaction passed security checks
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_acc["id"]))
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc["id"]))
        cur = db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, ai_fraud_score) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (from_acc["account_number"], to_account, amount, now, "success", fraud_prob),
        )
        txn_id = cur.lastrowid
        db.commit()

        return jsonify({
            "message": "transfer complete",
            "transaction_id": txn_id,
            "flagged": False,
            "flag_reason": None,
        })


@banking_bp.route("/api/transactions", methods=["GET"])
def transactions():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    db = get_db()
    acc = db.execute("SELECT account_number FROM accounts WHERE user_id = ?", (user["id"],)).fetchone()
    rows = db.execute(
        "SELECT * FROM transactions WHERE from_account = ? OR to_account = ? ORDER BY timestamp DESC",
        (acc["account_number"], acc["account_number"]),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@banking_bp.route("/api/admin/overview", methods=["GET"])
def admin_overview():
    db = get_db()
    users = db.execute("SELECT id, username, risk_level FROM users").fetchall()
    flagged_txns = db.execute(
        "SELECT * FROM transactions WHERE flagged = 1 ORDER BY timestamp DESC"
    ).fetchall()
    recent_events = db.execute(
        "SELECT se.*, COALESCE(u.username, 'Non-existent / Unknown User') as username "
        "FROM security_events se LEFT JOIN users u ON u.id = se.user_id "
        "ORDER BY se.timestamp DESC LIMIT 25"
    ).fetchall()
    
    # Network Graph Data
    all_accounts = db.execute("SELECT account_number, user_id FROM accounts").fetchall()
    all_txns = db.execute("SELECT from_account, to_account, amount FROM transactions WHERE status='success'").fetchall()
    
    nodes = [{"id": a["account_number"], "label": f"User {a['user_id']}\\n{a['account_number']}"} for a in all_accounts]
    edges = [{"from": t["from_account"], "to": t["to_account"], "value": t["amount"]} for t in all_txns]
    
    return jsonify({
        "users": [dict(u) for u in users],
        "flagged_transactions": [dict(t) for t in flagged_txns],
        "recent_events": [dict(e) for e in recent_events],
        "graph_data": {"nodes": nodes, "edges": edges}
    })

@banking_bp.route("/api/admin/reset", methods=["POST"])
def admin_reset():
    user = require_login()
    if not user or user["risk_level"] != "admin":
        return jsonify({"error": "unauthorized"}), 403
        
    db = get_db()
    # Delete all transactions
    db.execute("DELETE FROM transactions")
    # Delete all security events
    db.execute("DELETE FROM security_events")
    # Reset user balances to 5000
    db.execute("UPDATE accounts SET balance = 5000.0")
    # Reset user risk metrics
    db.execute("UPDATE users SET failed_login_attempts = 0, device_risk_score = 0.0, risk_level = 'normal' WHERE username != 'admin'")
    db.commit()
    
    return jsonify({"message": "All records cleared and demo reset successfully."})
