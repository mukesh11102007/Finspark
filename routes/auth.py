from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
from database import get_db

auth_bp = Blueprint("auth", __name__)

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def require_login():
    user = current_user()
    if not user:
        return None
    return user

def gen_account_number():
    return "BNK" + "".join(random.choices("0123456789", k=10))

@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        return jsonify({"error": "username already taken"}), 409

    pw_hash = generate_password_hash(password)
    now = datetime.utcnow().isoformat()
    # Mock some realistic coordinates for India or anywhere (using random around India)
    home_lat = 20.0 + random.uniform(-5.0, 5.0)
    home_lon = 78.0 + random.uniform(-5.0, 5.0)
    
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, created_at, home_lat, home_lon, failed_login_attempts, device_risk_score) VALUES (?, ?, ?, ?, ?, ?, 0, 0.0)",
        (username, email, pw_hash, now, home_lat, home_lon),
    )
    user_id = cur.lastrowid

    # Every new user gets one bank account with a starter balance
    acc_no = gen_account_number()
    db.execute(
        "INSERT INTO accounts (user_id, account_number, balance) VALUES (?, ?, ?)",
        (user_id, acc_no, 5000.0),
    )
    db.commit()

    return jsonify({"message": "registered", "account_number": acc_no})


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    device_id = data.get("device_id") or "unknown-device"
    ip_address = data.get("ip_address") or request.remote_addr or "0.0.0.0"

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        from routes.telemetry import _log_security_event
        if user:
            # Increment failed attempts
            db.execute("UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = ?", (user["id"],))
            _log_security_event(db, user["id"], "brute_force_attempt", device_id, ip_address,
                                 "Failed login attempt with incorrect password.")
            db.commit()
        return jsonify({"error": "invalid username or password"}), 401

    # Successful login, reset failed attempts
    db.execute("UPDATE users SET failed_login_attempts = 0 WHERE id = ?", (user["id"],))

    # Has this device_id been seen before for this user?
    seen = db.execute(
        "SELECT 1 FROM security_events WHERE user_id = ? AND device_id = ? LIMIT 1",
        (user["id"], device_id),
    ).fetchone()
    
    if not seen:
        from routes.telemetry import _log_security_event
        _log_security_event(db, user["id"], "new_device_login", device_id, ip_address,
                             f"First-time login from device '{device_id}'.")
        # Increase device risk score slightly for new devices
        db.execute("UPDATE users SET device_risk_score = device_risk_score + 10.0 WHERE id = ?", (user["id"],))

    session["user_id"] = user["id"]
    db.commit()
    return jsonify({"message": "logged in", "username": user["username"]})


@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "logged out"})


@auth_bp.route("/api/me", methods=["GET"])
def me():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    db = get_db()
    accounts = db.execute("SELECT * FROM accounts WHERE user_id = ?", (user["id"],)).fetchall()
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "risk_level": user["risk_level"],
        "accounts": [dict(a) for a in accounts],
    })


@auth_bp.route("/api/settings", methods=["POST"])
def settings():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    data = request.get_json(force=True)
    db = get_db()

    new_email = data.get("email")
    new_password = data.get("password")

    if new_email is not None:
        db.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user["id"]))
    if new_password:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new_password), user["id"]))
    db.commit()
    return jsonify({"message": "settings updated"})
