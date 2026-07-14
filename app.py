from flask import Flask, send_from_directory
from flask_cors import CORS
from database import init_db
from routes.auth import auth_bp
from routes.banking import banking_bp
from routes.telemetry import telemetry_bp

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.secret_key = "finspark26-demo-secret-change-me"  # fine for a hackathon demo

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

if __name__ == "__main__":
    init_db()
    # Run with adhoc SSL for HTTPS to encrypt traffic
    # Note: Requires 'pyopenssl' installed
    app.run(debug=True, port=5000, ssl_context='adhoc')
