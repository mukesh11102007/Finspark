from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_db
from routes.auth import require_login
import requests
import os
import logging
import json

from dotenv import load_dotenv

load_dotenv()

banking_bp = Blueprint("banking", __name__)

def generate_ai_explanation(reason_details):
    
    prompt = (
        f"Explain to a banking user in one short, professional, and friendly sentence "
        f"why their transaction was blocked or flagged. Reason: {reason_details}. "
        f"Do not include any greeting, JSON, or meta-commentary, just the sentence itself."
    )
    
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=5.0
            )
            if r.status_code == 200:
                explanation = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if explanation:
                    return explanation
            else:
                logging.warning(f"Groq API returned status {r.status_code}: {r.text}")
        except Exception as e:
            logging.warning(f"Groq API call failed: {e}")
    else:
        logging.warning("GROQ_API_KEY not found in environment.")
            
    # Rule-based fallback if API is unavailable
    logging.warning("Using rule-based fallback for explanation.")
    
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

    # ========================================================
    # SELF TRANSFER BYPASS (No risk scoring for own account)
    # ========================================================
    is_self_transfer = data.get("self_transfer", False) or (from_acc["account_number"] == to_account)
    import json
    
    if is_self_transfer:
        # Self-transfer: credit the amount directly to the account balance (no deduction)
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, from_acc["id"]))
        cur = db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, ai_fraud_score, score_features) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "success", 0.0, json.dumps(["Self-transfer: no risk applied"])),
        )
        db.commit()
        return jsonify({
            "message": "self transfer complete",
            "transaction_id": cur.lastrowid,
            "flagged": False,
            "flag_reason": None,
            "fraud_score": 0.0
        })

    if from_acc["balance"] < amount:
        reason = "Insufficient funds to complete the transfer."
        ai_exp = generate_ai_explanation(reason)
        db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, flag_reason) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (from_acc["account_number"], to_account, amount, now, "failed", ai_exp),
        )
        db.commit()
        return jsonify({"error": "insufficient funds", "reason": ai_exp}), 400

    # ========================================================
    # CORRELATION ENGINE & ML HYBRID GUARD
    # ========================================================
    risk_score = 0
    features = []
    
    # 1. Base User Risk
    user_rec = db.execute("SELECT risk_level FROM users WHERE id = ?", (user["id"],)).fetchone()
    base_risk = user_rec["risk_level"] if user_rec else "normal"
    if base_risk == "high":
        risk_score += 40
        features.append("High base user risk")
    elif base_risk == "elevated":
        risk_score += 20
        features.append("Elevated base user risk")
        
    # 2. Transaction Amount Heuristic
    if amount > 50000:
        risk_score += 30
        features.append(f"Unusually large transfer (₹{amount})")
    elif amount > 10000:
        risk_score += 15
        features.append("Large transfer amount")
        
    # 3. Cyber Telemetry Correlation (Recent events in last hour)
    recent_events = db.execute(
        "SELECT event_type, severity FROM security_events WHERE user_id = ? AND timestamp > datetime('now', '-1 hour')", 
        (user["id"],)
    ).fetchall()
    
    for ev in recent_events:
        if ev["severity"] == "critical":
            risk_score += 50
            features.append(f"Critical event: {ev['event_type']}")
        elif ev["severity"] == "high":
            risk_score += 30
            features.append(f"High risk event: {ev['event_type']}")
        elif ev["severity"] == "medium":
            risk_score += 15
            features.append(f"Medium risk event: {ev['event_type']}")
            
    risk_score = min(100.0, float(risk_score))
    
    # 4. ML Random Forest Model Classifier
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
    fraud_prob = 0.0
    
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
            features.append("Geographic travel anomaly detected")
        else:
            txn_lat, txn_lon = home_lat + 0.01, home_lon + 0.01 # Close by
            
        geo_dist = haversine(home_lat, home_lon, txn_lat, txn_lon)
        
        # Behavioral telemetry
        recent_anomaly = db.execute("SELECT 1 FROM security_events WHERE user_id = ? AND event_type='behavioral_anomaly' ORDER BY timestamp DESC LIMIT 1", (user["id"],)).fetchone()
        if recent_anomaly:
            mouse_dist, typing_wpm, mouse_speed = 100.0, 600.0, 30.0 # Bot
            features.append("Robotic typing and mouse movements flagged")
        else:
            mouse_dist, typing_wpm, mouse_speed = 2000.0, 60.0, 2.0  # Human
            
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
        
    final_fraud_score = max(risk_score, fraud_prob * 100)

    # Flag if fraud_prob > 0.60, or if risk_score >= 70, or if either sender or receiver is under active threat
    if fraud_prob > 0.60 or risk_score >= 70 or sender_threat or receiver_threat:
        if sender_threat:
            core_reason = f"the sender has active security threats (risk level: {user['risk_level']})"
        elif receiver_threat:
            core_reason = f"the recipient's account has high risk indicators (risk level: {receiver['risk_level']})"
        elif risk_score >= 70:
            core_reason = "High Session Risk detected. Transaction blocked pending step-up verification."
        else:
            core_reason = f"the anti-fraud model detected suspicious transaction patterns resembling ML fraud score of {fraud_prob*100:.1f}%"
            
        # Add to features list
        if fraud_prob > 0.60:
            features.append(f"AI ML flagged transfer ({fraud_prob*100:.1f}%)")
            
        ai_exp = generate_ai_explanation(core_reason)
        flag_reason = f"AI Blocked: {ai_exp}"
        
        cur = db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, flag_reason, ai_fraud_score, score_features) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "blocked", flag_reason, final_fraud_score, json.dumps(features)),
        )
        txn_id = cur.lastrowid
        db.commit()
        
        return jsonify({
            "error": flag_reason,
            "flagged": True,
            "flag_reason": flag_reason,
            "transaction_id": txn_id,
            "fraud_score": final_fraud_score
        }), 400
    else:
        # Perform actual balance transfer ONLY if the transaction passed security checks
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_acc["id"]))
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc["id"]))
        cur = db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, ai_fraud_score, score_features) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "success", final_fraud_score, json.dumps(features)),
        )
        txn_id = cur.lastrowid
        db.commit()

        return jsonify({
            "message": "transfer complete",
            "transaction_id": txn_id,
            "flagged": False,
            "flag_reason": None,
            "fraud_score": final_fraud_score
        })


@banking_bp.route("/api/transactions", methods=["GET"])
def transactions():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    db = get_db()
    acc = db.execute("SELECT account_number FROM accounts WHERE user_id = ?", (user["id"],)).fetchone()
    if not acc:
        return jsonify([])  # User has no account (e.g. admin)
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
    
    nodes = [{"id": a["account_number"], "label": f"User {a['user_id']}\n\n{a['account_number']}"} for a in all_accounts]
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

@banking_bp.route("/api/admin/feedback", methods=["POST"])
def admin_feedback():
    user = require_login()
    if not user or user["username"] != "admin":
        return jsonify({"error": "unauthorized"}), 403
        
    data = request.get_json(force=True)
    txn_id = data.get("transaction_id")
    feedback = data.get("feedback") # 'true_positive' or 'false_positive'
    
    if feedback not in ('true_positive', 'false_positive'):
        return jsonify({"error": "invalid feedback"}), 400
        
    db = get_db()
    db.execute("UPDATE transactions SET feedback = ? WHERE id = ?", (feedback, txn_id))
    db.commit()
    
    return jsonify({"message": f"Feedback '{feedback}' recorded for ML retraining loop."})

@banking_bp.route("/api/admin/set_risk", methods=["POST"])
def admin_set_risk():
    user = require_login()
    if not user or user["risk_level"] != "admin":
        return jsonify({"error": "unauthorized"}), 403
        
    data = request.get_json(force=True)
    target_user_id = data.get("user_id")
    risk_level = data.get("risk_level")
    
    if risk_level not in ('normal', 'elevated', 'high', 'critical'):
        return jsonify({"error": "invalid risk level"}), 400
        
    db = get_db()
    # Log the manual action
    from routes.telemetry import _log_security_event
    _log_security_event(db, target_user_id, "admin_manual_override", "admin-dashboard", request.remote_addr,
                         f"Admin manually set risk level to {risk_level}.")
                         
    db.execute("UPDATE users SET risk_level = ? WHERE id = ?", (risk_level, target_user_id))
    db.commit()
    
    return jsonify({"message": f"User risk level updated to {risk_level}."})


@banking_bp.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():
    user = require_login()
    if not user or user["risk_level"] != "admin":
        return jsonify({"error": "unauthorized"}), 403
        
    data = request.get_json(force=True)
    target_user_id = data.get("user_id")
    
    db = get_db()
    # Get account number first
    acc = db.execute("SELECT account_number FROM accounts WHERE user_id = ?", (target_user_id,)).fetchone()
    if acc:
        acc_no = acc["account_number"]
        db.execute("DELETE FROM transactions WHERE from_account = ? OR to_account = ?", (acc_no, acc_no))
    db.execute("DELETE FROM security_events WHERE user_id = ?", (target_user_id,))
    db.execute("DELETE FROM accounts WHERE user_id = ?", (target_user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
    db.commit()
    
    return jsonify({"message": "User and all associated data deleted."})
