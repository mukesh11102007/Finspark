import os
from database import init_db

DB_PATH = "bank.db"

def reset_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[*] Deleted existing database: {DB_PATH}")
    else:
        print(f"[*] No existing database found at {DB_PATH}")

    init_db()
    print("[+] Database initialized successfully with default tables and admin account.")

if __name__ == "__main__":
    print("Resetting SecureBank Database...")
    reset_database()
