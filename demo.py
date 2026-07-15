import requests
import random
import urllib3
import json

# Disable self-signed SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://127.0.0.1:5000"

def generate_random_user():
    num = random.randint(1000, 9999)
    return {
        "username": f"user_{num}",
        "email": f"user_{num}@demo.com",
        "password": "SecurePassword123"
    }

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)

def run_demo():
    print_header("SecureBank Anti-Fraud Demo")
    print(f"Connecting to Flask API at: {BASE_URL}")
    
    # 1. Create a request session to persist login cookies
    sender_session = requests.Session()
    recipient_session = requests.Session()
    
    # Generate user details
    recipient_info = generate_random_user()
    sender_info = generate_random_user()
    
    # 2. Register Recipient
    print("\n[+] Registering Recipient User...")
    try:
        r_resp = requests.post(f"{BASE_URL}/api/register", json=recipient_info, verify=False)
    except requests.exceptions.ConnectionError:
        print("\n[!] ERROR: Could not connect to the server.")
        print("Please make sure you run the Flask server first with: python app.py")
        return
        
    if r_resp.status_code != 200:
        print(f"[-] Registration failed: {r_resp.text}")
        return
    
    recipient_acc = r_resp.json()["account_number"]
    print(f"    Recipient Username: {recipient_info['username']}")
    print(f"    Recipient Account:  {recipient_acc}")
    
    # 3. Register Sender
    print("\n[+] Registering Sender User...")
    s_resp = requests.post(f"{BASE_URL}/api/register", json=sender_info, verify=False)
    sender_acc = s_resp.json()["account_number"]
    print(f"    Sender Username:    {sender_info['username']}")
    print(f"    Sender Account:     {sender_acc}")
    
    # 4. Login Sender
    print("\n[+] Logging in Sender User...")
    login_payload = {
        "username": sender_info["username"],
        "password": sender_info["password"],
        "device_id": "laptop-chrome-mac",
        "ip_address": "127.0.0.1"
    }
    l_resp = sender_session.post(f"{BASE_URL}/api/login", json=login_payload, verify=False)
    if l_resp.status_code == 200:
        print("    Sender login successful! Session cookie stored.")
    else:
        print(f"[-] Login failed: {l_resp.text}")
        return
        
    # Check Sender Balance
    me_resp = sender_session.get(f"{BASE_URL}/api/me", verify=False)
    balance = me_resp.json()["accounts"][0]["balance"]
    print(f"    Sender Balance:     ₹{balance}")

    # 5. Perform Normal Transfer (Should succeed)
    print_header("Test Case 1: Normal Transfer (Human Behavior)")
    print(f"Attempting to transfer ₹500 to {recipient_acc}...")
    transfer_payload = {
        "to_account": recipient_acc,
        "amount": 500.0
    }
    tx_resp = sender_session.post(f"{BASE_URL}/api/transfer", json=transfer_payload, verify=False)
    print(f"Response status: {tx_resp.status_code}")
    print(f"Response body:   {json.dumps(tx_resp.json(), indent=4)}")
    
    # Confirm updated balance
    me_resp = sender_session.get(f"{BASE_URL}/api/me", verify=False)
    balance = me_resp.json()["accounts"][0]["balance"]
    print(f"    New Sender Balance: ₹{balance}")

    # 6. Simulate Bot/Script Telemetry (Triggering behavioral anomaly)
    print_header("Test Case 2: Blocked Transfer (Behavioral Telemetry Anomaly)")
    print("Sending robotic interaction telemetry to server...")
    print("Criteria triggered: High typing speed (>200 WPM) and robotic mouse movement count (< 5 movements)")
    
    telemetry_payload = {
        "mouse_movements": [
            {"x": 10, "y": 10, "time": 0},
            {"x": 400, "y": 600, "time": 10}  # Direct straight line
        ],
        "typing_speed_wpm": 650.0  # Robotic typing speed (pasted credentials)
    }
    
    tel_resp = sender_session.post(f"{BASE_URL}/api/telemetry/behavior", json=telemetry_payload, verify=False)
    print(f"Telemetry Status: {tel_resp.status_code} - {tel_resp.json().get('message')}")
    
    # 7. Attempt Transfer again (Should fail)
    print("\nAttempting to transfer another ₹1000 under anomaly flags...")
    transfer_payload_2 = {
        "to_account": recipient_acc,
        "amount": 1000.0
    }
    tx_resp_2 = sender_session.post(f"{BASE_URL}/api/transfer", json=transfer_payload_2, verify=False)
    print(f"Response status: {tx_resp_2.status_code}")
    
    response_data = tx_resp_2.json()
    print(f"Response body:\n{json.dumps(response_data, indent=4)}")
    
    if "error" in response_data:
        print("\n[!] TRANSACTION SUCCESSFULLY BLOCKED BY SECURITY ENGINE!")
        print(f"Reason details: {response_data.get('error')}")
    else:
        print("\n[-] Warning: Transaction went through unexpectedly.")
        
    print_header("Demo Complete")
    print("Review the tables in the Admin Control Center by logging in as 'admin' (password: 'pass')")

if __name__ == "__main__":
    run_demo()
