from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_db
from routes.auth import require_login

telemetry_bp = Blueprint("telemetry", __name__)

EVENT_CATALOGUE = {
    "new_device_login": ("medium", "Login detected from a device not seen before on this account."),
    "impossible_travel": ("high", "Two logins from geographically distant locations within minutes."),
    "malware_detected": ("critical", "Endpoint protection flagged malware / RAT signature on user's laptop."),
    "device_compromised": ("critical", "Laptop reported as compromised (C2 beacon traffic detected)."),
    "brute_force_attempt": ("high", "Multiple failed login attempts detected in a short window."),
    "vpn_anomaly": ("low", "User connected through an unrecognized VPN/proxy exit node."),
    "behavioral_anomaly": ("medium", "Client-side tracking detected unusual interaction patterns (mouse/keystrokes).")
}

def _log_security_event(db, user_id, event_type, device_id, ip_address, details=None):
    severity, default_detail = EVENT_CATALOGUE.get(event_type, ("low", "Unclassified event."))
    db.execute(
        "INSERT INTO security_events (user_id, event_type, severity, device_id, ip_address, details, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, event_type, severity, device_id, ip_address, details or default_detail,
         datetime.utcnow().isoformat()),
    )

@telemetry_bp.route("/api/security/simulate", methods=["POST"])
def simulate_security_event():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401

    data = request.get_json(force=True)
    event_type = data.get("event_type")
    if event_type not in EVENT_CATALOGUE:
        return jsonify({"error": "unknown event_type", "valid_types": list(EVENT_CATALOGUE.keys())}), 400

    device_id = data.get("device_id", "demo-device")
    ip_address = data.get("ip_address", request.remote_addr or "0.0.0.0")

    db = get_db()
    _log_security_event(db, user["id"], event_type, device_id, ip_address)

    severity = EVENT_CATALOGUE[event_type][0]
    if severity in ("high", "critical"):
        db.execute("UPDATE users SET risk_level = 'elevated' WHERE id = ? AND risk_level = 'normal'",
                   (user["id"],))
    db.commit()
    return jsonify({"message": f"simulated event '{event_type}' logged", "severity": severity})


@telemetry_bp.route("/api/security/events", methods=["GET"])
def security_events():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    db = get_db()
    rows = db.execute(
        "SELECT * FROM security_events WHERE user_id = ? ORDER BY timestamp DESC", (user["id"],)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@telemetry_bp.route("/api/telemetry/behavior", methods=["POST"])
def log_behavior():
    user = require_login()
    if not user:
        return jsonify({"error": "not authenticated"}), 401
    
    data = request.get_json(force=True)
    mouse_movements = data.get("mouse_movements", [])
    typing_speed = data.get("typing_speed_wpm", 0)
    
    db = get_db()
    if len(mouse_movements) < 5 and typing_speed > 200:
         _log_security_event(db, user["id"], "behavioral_anomaly", "tracked-device", request.remote_addr, "Unusually fast typing and robotic mouse movements detected.")
         db.commit()
         
    return jsonify({"message": "telemetry logged"})
