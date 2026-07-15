import os
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_cors import CORS
from database import init_db
from routes.auth import auth_bp
from routes.banking import banking_bp
from routes.telemetry import telemetry_bp

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback-secret-for-dev")

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(banking_bp)
app.register_blueprint(telemetry_bp)

@app.teardown_appcontext
def close_db_context(exception):
    from database import close_db
    close_db(exception)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/admin")
def admin():
    return send_from_directory(".", "admin.html")

if __name__ == "__main__":
    init_db()
    # Run on plain HTTP (removed ssl_context='adhoc' to avoid Chrome warnings)
    app.run(debug=True, port=5000)
