from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_db
from routes.auth import require_login

banking_bp = Blueprint("banking", __name__)

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

    now = datetime.utcnow().isoformat()

    if from_acc["balance"] < amount:
        db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status) VALUES (?, ?, ?, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "failed"),
        )
        db.commit()
        return jsonify({"error": "insufficient funds"}), 400

    # perform transfer
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_acc["id"]))
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc["id"]))
    cur = db.execute(
        "INSERT INTO transactions (from_account, to_account, amount, timestamp, status) VALUES (?, ?, ?, ?, ?)",
        (from_acc["account_number"], to_account, amount, now, "success"),
    )
    txn_id = cur.lastrowid
    db.commit()

    # ML Model Integration
    flagged = False
    flag_reason = None
    
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
            
        # Construct feature dict matching Kaggle dataset + Behavioral
        feature_dict = {
            "transaction_amount": amount,
            "login_attempts": user_dict.get("failed_login_attempts") or 0,
            "device_risk_score": user_dict.get("device_risk_score") or 0.0,
            "transfer_frequency": 5, # Baseline
            "anomaly_score": 0.1, # Baseline
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
        
        if fraud_prob > 0.60:
            flagged = True
            flag_reason = f"AI blocked transfer (Kaggle+Telemetry). Fraud Prob: {fraud_prob*100:.1f}% | GeoDist: {geo_dist:.0f}km | Age: {account_age_days}d"
            db.execute("UPDATE transactions SET flagged=1, ai_fraud_score=?, flag_reason=? WHERE id=?", (fraud_prob, flag_reason, txn_id))
            db.commit()

    return jsonify({
        "message": "transfer complete",
        "transaction_id": txn_id,
        "flagged": flagged,
        "flag_reason": flag_reason,
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
        "SELECT se.*, u.username FROM security_events se JOIN users u ON u.id = se.user_id "
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
