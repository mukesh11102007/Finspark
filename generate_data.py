import csv
import random
import math

# Configuration
NUM_ROWS = 5000
FILENAME = "synthetic_fraud_data.csv"

def generate_human_behavior():
    """Simulates a normal human transaction"""
    # Normal transfer amount
    amount = round(random.uniform(10.0, 5000.0), 2)
    
    # 95% of the time, no severe security events (0: None, 1: Low)
    # 5% of the time, a false positive Medium event
    severity = random.choice([0, 0, 0, 1, 1, 2]) if random.random() < 0.05 else random.choice([0, 0, 0, 0, 1])
    
    # Humans move the mouse around a lot (curves, overshooting)
    mouse_distance_total = random.uniform(800.0, 4500.0) 
    
    # Average human typing speed
    typing_wpm = random.uniform(25.0, 110.0)
    
    # Slower, variable mouse speed
    mouse_speed_avg = random.uniform(0.5, 3.5)
    
    return [amount, severity, mouse_distance_total, typing_wpm, mouse_speed_avg, 0] # 0 = Normal

def generate_bot_fraud_behavior():
    """Simulates a bot, script, or account takeover fraud"""
    # Often try to drain accounts
    amount = round(random.uniform(10000.0, 150000.0), 2)
    
    # Usually triggers high severity events (e.g. Impossible Travel, Malware)
    severity = random.choice([2, 3, 4, 4])
    
    # Bots move in perfectly straight lines to the exact button coordinates, minimizing distance
    mouse_distance_total = random.uniform(50.0, 300.0)
    
    # Scripts "type" instantly by pasting payloads
    typing_wpm = random.uniform(400.0, 1500.0)
    
    # Near instantaneous cursor teleportation
    mouse_speed_avg = random.uniform(15.0, 50.0)
    
    return [amount, severity, mouse_distance_total, typing_wpm, mouse_speed_avg, 1] # 1 = Fraud/Bot

def main():
    print(f"Generating {NUM_ROWS} rows of synthetic telemetry and transaction data...")
    
    headers = [
        "amount", 
        "security_event_severity", 
        "mouse_distance_total", 
        "typing_wpm", 
        "mouse_speed_avg", 
        "is_fraud"
    ]
    
    with open(FILENAME, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        
        for _ in range(NUM_ROWS):
            # 85% normal traffic, 15% fraud/bot traffic (imbalanced, like real life)
            if random.random() < 0.85:
                row = generate_human_behavior()
            else:
                row = generate_bot_fraud_behavior()
            
            # Add some random noise to make it realistic
            row[0] = max(1.0, row[0] + random.uniform(-100, 100)) # Noise to amount
            
            writer.writerow(row)
            
    print(f"Data successfully saved to '{FILENAME}'.")
    print("You can now use this CSV to train a scikit-learn Random Forest model!")

if __name__ == "__main__":
    main()
