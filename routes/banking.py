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

    # ========================================================
    # SELF TRANSFER BYPASS (No risk scoring for own account)
    # ========================================================
    is_self_transfer = data.get("self_transfer", False) or (from_acc["account_number"] == to_account)
    import json
    
    if is_self_transfer:
        # Self-transfer: credit and debit cancel out — just log the transaction
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

    # ========================================================
    # CORRELATION ENGINE (Proactive Prevention Loop)
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
        
    # 3. Cyber Telemetry Correlation (Recent events)
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
            
    # Cap score at 100
    risk_score = min(100.0, float(risk_score))
    
    # Proactive Prevention Loop Decision
    is_flagged = False
    flag_reason = None
    import json
    
    if risk_score >= 70:
        is_flagged = True
        flag_reason = "High Session Risk detected. Transaction blocked pending step-up verification."
        db.execute(
            "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, flagged, flag_reason, ai_fraud_score, score_features) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (from_acc["account_number"], to_account, amount, now, "blocked", 1, flag_reason, risk_score, json.dumps(features)),
        )
        db.commit()
        return jsonify({
            "error": flag_reason,
            "flagged": True,
            "flag_reason": flag_reason,
            "fraud_score": risk_score
        }), 403
    
    # perform transfer if safe
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_acc["id"]))
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc["id"]))
    cur = db.execute(
        "INSERT INTO transactions (from_account, to_account, amount, timestamp, status, ai_fraud_score, score_features) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (from_acc["account_number"], to_account, amount, now, "success", risk_score, json.dumps(features)),
    )
    txn_id = cur.lastrowid
    db.commit()

    return jsonify({
        "message": "transfer complete",
        "transaction_id": txn_id,
        "flagged": False,
        "flag_reason": None,
        "fraud_score": risk_score
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
