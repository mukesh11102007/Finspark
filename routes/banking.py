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

    # NOTE: Correlation logic removed for ML integration

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
