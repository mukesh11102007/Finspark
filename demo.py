import requests
import random
import urllib3
import json
import time
import sys

# Disable self-signed SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://127.0.0.1:5000"

def animate_text(text, delay=0.03):
    """Simulates a smooth typing animation in the terminal."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def print_header(title):
    print("\n" + "=" * 60)
    animate_text(f" {title} ".center(60, "="), 0.01)
    print("=" * 60)
    time.sleep(0.5)

def generate_random_user():
    num = random.randint(1000, 9999)
    return {
        "username": f"user_{num}",
        "email": f"user_{num}@demo.com",
        "password": "SecurePassword123"
    }

def setup_users():
    """Registers and authenticates target users for the simulation."""
    animate_text("[*] Initializing Attack Vectors and Generating Targets...")
    time.sleep(0.5)
    sender_session = requests.Session()
    
    recipient_info = generate_random_user()
    sender_info = generate_random_user()

    animate_text(f"[+] Registering Target (Victim): {sender_info['username']}", 0.02)
    s_resp = requests.post(f"{BASE_URL}/api/register", json=sender_info, verify=False)
    
    animate_text(f"[+] Registering Recipient (Mule): {recipient_info['username']}", 0.02)
    r_resp = requests.post(f"{BASE_URL}/api/register", json=recipient_info, verify=False)
    recipient_acc = r_resp.json()["account_number"]

    animate_text("[+] Exploiting session to log into Target Account...", 0.02)
    login_payload = {
        "username": sender_info["username"],
        "password": sender_info["password"],
        "device_id": "laptop-chrome-mac",
        "ip_address": "127.0.0.1"
    }
    sender_session.post(f"{BASE_URL}/api/login", json=login_payload, verify=False)
    time.sleep(0.5)
    return sender_session, sender_info, recipient_acc

def attack_bot_behavior(session, recipient_acc):
    """Simulates robotic mouse movements and copy-paste typing speeds to bypass UI."""
    print_header("Attack 1: Robotic Behavior (Mouse/Keyboard Anomaly)")
    animate_text("[-] Injecting synthetic mouse movements and impossible typing speeds...")
    time.sleep(1)
    
    telemetry_payload = {
        "mouse_movements": [
            {"x": 10, "y": 10, "time": 0},
            {"x": 400, "y": 600, "time": 10}  # Direct straight line, physically impossible for humans
        ],
        "typing_speed_wpm": 650.0  # Copy-paste speed
    }
    
    tel_resp = session.post(f"{BASE_URL}/api/telemetry/behavior", json=telemetry_payload, verify=False)
    animate_text(f"    [SERVER] Telemetry logged: {tel_resp.json().get('message')}", 0.01)
    time.sleep(0.5)
    
    animate_text("[-] Attempting fraudulent transfer of ₹1500...")
    tx_resp = session.post(f"{BASE_URL}/api/transfer", json={"to_account": recipient_acc, "amount": 1500.0}, verify=False)
    time.sleep(1)
    
    response_data = tx_resp.json()
    if "error" in response_data:
        animate_text("    [!] ATTACK BLOCKED BY ML ENGINE: " + response_data.get('reason', response_data.get('error')), delay=0.01)
    else:
        animate_text("    [X] ATTACK SUCCESSFUL (Bypass Failed!)")
    time.sleep(1.5)

def attack_data_exfiltration(session):
    """Simulates a massive data exfiltration attempt (Quantum Traffic Anomaly)."""
    print_header("Attack 2: Data Exfiltration (Quantum Traffic Anomaly)")
    animate_text("[-] Simulating massive encrypted payload transfer (1.5 GB in 2 seconds)...")
    time.sleep(1)
    
    quantum_payload = {
        "bytes_transferred": 1500 * 1024 * 1024 # 1.5 GB
    }
    q_resp = session.post(f"{BASE_URL}/api/telemetry/quantum", json=quantum_payload, verify=False)
    animate_text(f"    [SERVER] Traffic Analysis: {q_resp.json().get('message')}", 0.01)
    time.sleep(1)
    animate_text("    [!] ACCOUNT FLAGGED FOR CRITICAL RISK - Exfiltration halted.", delay=0.01)
    time.sleep(1.5)

def attack_threat_intel_injection(session):
    """Injects threat intelligence data simulating an impossible travel anomaly."""
    print_header("Attack 3: Impossible Travel / Threat Intel Injection")
    animate_text("[-] Injecting 'impossible_travel' threat intel event from remote exit node...")
    time.sleep(1)
    
    threat_payload = {
        "event_type": "impossible_travel",
        "device_id": "suspicious-proxy-node"
    }
    t_resp = session.post(f"{BASE_URL}/api/security/simulate", json=threat_payload, verify=False)
    animate_text(f"    [SERVER] Threat Engine Response: {t_resp.json().get('message')}", 0.01)
    time.sleep(1)
    
    animate_text("[-] Checking Current Account Risk Level...")
    me_resp = session.get(f"{BASE_URL}/api/me", verify=False)
    risk = me_resp.json().get("risk_level", "unknown")
    animate_text(f"    [!] ACCOUNT RISK LEVEL ELEVATED TO: {risk.upper()}", delay=0.01)
    time.sleep(1.5)

def run_all_attacks():
    """Orchestrates the entire attack simulation."""
    print_header("SecureBank Cyber Attack Simulator v2.0")
    try:
        session, sender_info, recipient_acc = setup_users()
        time.sleep(1)
        
        # Execute Modular Attacks
        attack_bot_behavior(session, recipient_acc)
        attack_data_exfiltration(session)
        attack_threat_intel_injection(session)
        
        print_header("Simulation Complete")
        animate_text("[*] All attack vectors have been executed and logged.")
        animate_text("[*] Review the Security Operations Center (Admin Dashboard) to analyze incidents.")
        
    except requests.exceptions.ConnectionError:
        animate_text("\n[!] CRITICAL ERROR: Could not establish connection to the target server.", 0.01)
        animate_text("    Ensure the Flask server is running on https://127.0.0.1:5000", 0.01)

if __name__ == "__main__":
    run_all_attacks()
