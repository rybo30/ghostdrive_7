# [Everything_else/health_manager.py]

import os
import json
from datetime import datetime, timedelta
from core.paths import HEALTH_DIR
from Everything_else.health_engine import HealthEngine

def get_health_path(username):
    return os.path.join(HEALTH_DIR, f"{username}_health.enc")

def load_health_data(username, fernet):
    path = get_health_path(username)
    # Ensure 'age' is in the default profile
    default_data = {
        "profile": {
            "height": 0, 
            "age": 0,
            "sex": "", 
            "weight": 0, 
            "weight_goal": 0, 
            "activity_level": 1.2
        },
        "logs": {}, 
        "settings": {"protein_goal": 200}
    }
    if not os.path.exists(path):
        return default_data
    try:
        with open(path, "rb") as f:
            decrypted_data = fernet.decrypt(f.read())
        return json.loads(decrypted_data.decode())
    except:
        return default_data

def save_health_data(username, fernet, data):
    path = get_health_path(username)
    raw_json = json.dumps(data).encode()
    encrypted_data = fernet.encrypt(raw_json)
    with open(path, "wb") as f:
        f.write(encrypted_data)

def calculate_running_total(data):
    """
    Iterates through all logs and sums the Daily Change.
    Uses Projected Weight (Anchor logic) for days without a manual weigh-in.
    """
    logs = data.get("logs", {})
    profile = data.get("profile", {})
    engine = HealthEngine(profile)
    
    total_net_calories = 0
    
    # Sort dates to ensure chronological calculation
    sorted_dates = sorted(logs.keys())
    
    for date_str in sorted_dates:
        day = logs[date_str]
        current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Pull data for the calculation
        intake = day.get('calories', 0)
        activity = day.get('activity', 5) # Default to 5 instead of 1 for more realistic TDEE
        workout = day.get('workout_burn', 0)
        
        # USE ANCHOR LOGIC: 
        # If the day has a manual weight, use it. 
        # Otherwise, calculate what the weight likely was on that day.
        manual_weight = day.get('weight', 0)
        if manual_weight > 0:
            effective_weight = manual_weight
        else:
            effective_weight = engine.get_projected_weight(logs, current_date)
        
        # Get the delta for this specific day
        daily_delta = engine.get_daily_delta(intake, activity, effective_weight, workout)
        
        # Only add to total if the day is "complete" (has intake)
        if daily_delta is not None:
            total_net_calories += daily_delta
            
    return total_net_calories

def calculate_protein_consistency(logs, goal):
    today = datetime.now()
    met_count = 0
    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if logs.get(date_str, {}).get("protein", 0) >= goal:
            met_count += 1
    return met_count


class FoodItem:
    """A clean wrapper for a USDA food entry."""
    def __init__(self, raw_data):
        self.name = raw_data.get("description", "Unknown Food")
        self.id = raw_data.get("fdcId")
        self.nutrients = {}
        
        # Mapping specific USDA IDs to friendly names
        # 1008 = kcal, 1003 = Protein, 1004 = Fat, 1005 = Carbs
        mapping = {1008: "calories", 1003: "protein", 1004: "fat", 1005: "carbs"}
        
        for n in raw_data.get("foodNutrients", []):
            n_id = n.get("nutrient", {}).get("id")
            if n_id in mapping:
                # Store value (usually per 100g)
                self.nutrients[mapping[n_id]] = n.get("amount", 0)

class USDAFoodDatabase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(USDAFoodDatabase, cls).__new__(cls)
            cls._instance.library = []
            cls._instance.load_library()
        return cls._instance

    def load_library(self):
        # Point this to where you keep FoodData.json
        from core.paths import EVERYTHING_ELSE
        path = os.path.join(EVERYTHING_ELSE, "FoodData.json")
        
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.library = [FoodItem(f) for f in data.get("FoundationFoods", [])]
            except Exception as e:
                print(f"Food Library Load Error: {e}")

    def search(self, query):
        if not query: return []
        query = query.lower()
        # Simple fuzzy search: does the name contain the query?
        return [f for f in self.library if query in f.name.lower()][:20] # Limit to top 20