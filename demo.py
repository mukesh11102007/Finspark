import requests
import random
import urllib3
import json
import time
import sys

# Disable self-signed SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "http://127.0.0.1:5000"

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

def scenario_normal_transfer(session, recipient_acc):
    print_header("Scenario 1: Normal Human Transfer")
    animate_text("[-] Simulating normal human behavior (moderate typing, natural mouse curves)...")
    time.sleep(1)
    
    # Telemetry is generally not sent or sent with normal values.
    # We just make the transfer.
    animate_text("[-] Attempting normal transfer of ₹500...")
    tx_resp = session.post(f"{BASE_URL}/api/transfer", json={"to_account": recipient_acc, "amount": 500.0}, verify=False)
    time.sleep(1)
    
    response_data = tx_resp.json()
    if "error" not in response_data:
        animate_text(f"    [+] TRANSFER SUCCESSFUL. Transaction ID: {response_data.get('transaction_id')}")
    else:
        animate_text("    [!] TRANSFER FAILED: " + response_data.get('error'))
    time.sleep(1.5)

def scenario_bot_blocked(session, recipient_acc):
    """Simulates robotic mouse movements and copy-paste typing speeds to bypass UI."""
    print_header("Scenario 2: Robotic Behavior (Blocked by ML Engine)")
    animate_text("[-] Injecting synthetic mouse movements and impossible typing speeds (Bot behavior)...")
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
        return response_data.get("transaction_id")
    else:
        animate_text("    [X] ATTACK SUCCESSFUL (Bypass Failed!)")
        return None
    time.sleep(1.5)

def scenario_vpn_geo_anomaly(session, recipient_acc):
    """Simulates an impossible travel anomaly followed by a large transfer."""
    print_header("Scenario 3: The 'Phantom' Attack (Impossible Travel + Large Transfer)")
    animate_text("[-] Injecting threat intel: Login from a known malicious VPN exit node (simulating impossible travel)...")
    time.sleep(1)
    
    # Inject threat intel directly using the simulator endpoint
    # Since we are using the user's session, the simulator will apply it if we pass the target user id or device id
    # Wait, the simulator is an admin endpoint or public? It's public in this hackathon setup.
    # But it takes `target_user_id` optionally. Let's just do a login from a different IP first, or use the simulator.
    payload = {
        "event_type": "vpn_anomaly",
        "device_id": "laptop-chrome-mac" 
    }
    sim_resp = session.post(f"{BASE_URL}/api/security/simulate", json=payload, verify=False)
    animate_text(f"    [SERVER] Threat Intel Logged: {sim_resp.json().get('message')}", 0.01)
    time.sleep(1)
    
    animate_text("[-] Attempting a large transfer of ₹9,500...")
    animate_text("[-] A normal bank might just flag the VPN, but our ML correlates the impossible geographical distance.")
    tx_resp = session.post(f"{BASE_URL}/api/transfer", json={"to_account": recipient_acc, "amount": 9500.0}, verify=False)
    time.sleep(1)
    
    response_data = tx_resp.json()
    if "error" in response_data:
        animate_text("    [!] ATTACK BLOCKED BY ML ENGINE: " + response_data.get('reason', response_data.get('error')), delay=0.01)
    else:
        animate_text("    [X] ATTACK SUCCESSFUL (Bypass Failed!)")
    time.sleep(1.5)

def scenario_device_compromised_salami(session, recipient_acc):
    """Simulates a compromised device attempting a small transfer."""
    print_header("Scenario 4: The 'Salami Slicing' Mule (Compromised Device + Small Transfer)")
    animate_text("[-] Injecting threat intel: Endpoint Compromised (C2 beacon detected)...")
    time.sleep(1)
    
    payload = {
        "event_type": "device_compromised",
        "device_id": "laptop-chrome-mac"
    }
    sim_resp = session.post(f"{BASE_URL}/api/security/simulate", json=payload, verify=False)
    animate_text(f"    [SERVER] Threat Intel Logged: {sim_resp.json().get('message')}", 0.01)
    time.sleep(1)
    
    animate_text("[-] Attempting a very small transfer of ₹100...")
    animate_text("[-] A normal bank ignores small amounts. Our ML correlates the compromised device state and blocks it.")
    tx_resp = session.post(f"{BASE_URL}/api/transfer", json={"to_account": recipient_acc, "amount": 100.0}, verify=False)
    time.sleep(1)
    
    response_data = tx_resp.json()
    if "error" in response_data:
        animate_text("    [!] ATTACK BLOCKED BY ML ENGINE: " + response_data.get('reason', response_data.get('error')), delay=0.01)
    else:
        animate_text("    [X] ATTACK SUCCESSFUL (Bypass Failed!)")
    time.sleep(1.5)

def scenario_admin_feedback(blocked_txn_id):
    """Simulates an admin reviewing the blocked transaction and marking it as false positive."""
    print_header("Scenario 5: Admin Review & Feedback Loop")
    if not blocked_txn_id:
        animate_text("[!] No blocked transaction ID provided. Skipping admin feedback.")
        return
        
    animate_text("[-] Logging in to the SOC Command Center as Admin...")
    admin_session = requests.Session()
    login_payload = {
        "username": "admin",
        "password": "pass",
        "device_id": "admin-secure-terminal"
    }
    admin_session.post(f"{BASE_URL}/api/login", json=login_payload, verify=False)
    time.sleep(1)
    
    animate_text(f"[-] Admin reviewing Transaction #{blocked_txn_id}...")
    time.sleep(1)
    animate_text("[-] Marking transaction as a False Positive to retrain the ML model...")
    feedback_payload = {
        "transaction_id": blocked_txn_id,
        "feedback": "false_positive"
    }
    f_resp = admin_session.post(f"{BASE_URL}/api/admin/feedback", json=feedback_payload, verify=False)
    
    animate_text(f"    [SERVER] {f_resp.json().get('message')}", 0.01)
    time.sleep(1.5)

def run_all_scenarios():
    """Orchestrates the entire demo simulation."""
    print_header("SecureBank Demo Flow")
    try:
        session, sender_info, recipient_acc = setup_users()
        time.sleep(1)
        
        # Execute Scenarios
        scenario_normal_transfer(session, recipient_acc)
        blocked_txn_id = scenario_bot_blocked(session, recipient_acc)
        scenario_vpn_geo_anomaly(session, recipient_acc)
        scenario_device_compromised_salami(session, recipient_acc)
        scenario_admin_feedback(blocked_txn_id)
        
        print_header("Demo Complete")
        animate_text("[*] All scenarios executed.")
        animate_text("[*] You can view the admin dashboard at http://127.0.0.1:5000/admin")
        
    except requests.exceptions.ConnectionError:
        animate_text("\n[!] CRITICAL ERROR: Could not establish connection to the target server.", 0.01)
        animate_text("    Ensure the Flask server is running on http://127.0.0.1:5000", 0.01)

if __name__ == "__main__":
    run_all_scenarios()
