import sqlite3
from flask import g

DB_PATH = "bank.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            risk_level TEXT DEFAULT 'normal'
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_account TEXT,
            to_account TEXT,
            amount REAL NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            flagged INTEGER DEFAULT 0,
            flag_reason TEXT,
            ai_fraud_score REAL DEFAULT 0.0,
            score_features TEXT,
            feedback TEXT
        );

        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            device_id TEXT,
            ip_address TEXT,
            details TEXT,
            timestamp TEXT NOT NULL
        );
        """
    )
    
    # Create admin user if it doesn't exist
    from werkzeug.security import generate_password_hash
    from datetime import datetime
    
    admin = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not admin:
        now = datetime.utcnow().isoformat()
        db.execute(
            "INSERT INTO users (username, password_hash, created_at, risk_level) VALUES (?, ?, ?, ?)",
            ("admin", generate_password_hash("pass"), now, "admin")
        )

    db.commit()
    db.close()
