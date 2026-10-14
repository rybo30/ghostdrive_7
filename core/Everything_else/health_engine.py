# [Everything_else\health_engine.py]

from datetime import datetime, timedelta, date

class HealthEngine:
    def __init__(self, user_profile):
        self.profile = user_profile

    def calculate_bmr(self, current_weight=None):
        w_lbs = current_weight if current_weight is not None else self.profile.get('weight', 0)
        h_in = self.profile.get('height', 0)
        age = self.profile.get('age', 0)
        
        if not all([w_lbs, h_in, age]): 
            return 0

        w_kg = w_lbs / 2.20462
        h_cm = h_in * 2.54
        
        # Mifflin-St Jeor Equation
        if str(self.profile.get('sex', '')).lower() in ['male', 'm']:
            return (10 * w_kg) + (6.25 * h_cm) - (5 * age) + 5
        return (10 * w_kg) + (6.25 * h_cm) - (5 * age) - 161


    # Add to HealthEngine class in health_engine.py
    def calculate_calories_from_macros(self, p, c, f):
        """Standard 4/4/9 thermal values for macronutrients."""
        return (int(p) * 4) + (int(c) * 4) + (int(f) * 9)


    def project_goal_date(self, current_weight, target_weight, avg_deficit):
        # Safety checks for invalid math
        if avg_deficit is None or avg_deficit == 0:
            return "Awaiting Daily Logs"
            
        # If gaining weight or already at goal
        if avg_deficit > 0:
            return "Surplus (Gaining)"
        if current_weight <= target_weight:
            return "GOAL REACHED"
        
        # 3500 kcal = 1lb
        calories_to_burn = (current_weight - target_weight) * 3500
        days_remaining = calories_to_burn / abs(avg_deficit)
        
        # Limit projection to 5 years to avoid overflow errors
        if days_remaining > 1825:
            return "Indefinite (>5yrs)"
            
        return date.today() + timedelta(days=int(days_remaining))

    def map_activity_to_multiplier(self, score):
        """Maps 1-10 rating to 1.2 - 1.9 multiplier."""
        score = max(1, min(10, score))
        return 1.2 + (score - 1) * (0.7 / 9)

    def get_daily_delta(self, intake, activity_score, current_weight, workout_burn=0):
        if not intake or intake == 0: 
            return None 
            
        bmr = self.calculate_bmr(current_weight)
        if bmr == 0: 
            return None
        
        # Applying 0.75 multiplier to make calculation more conservative
        tdee = bmr * self.map_activity_to_multiplier(activity_score) * 0.75
        total_out = tdee + workout_burn
        
        return intake - total_out


    def get_latest_weigh_in(self, logs):
        if not logs:
            return float(self.profile.get("weight", 0))

        sorted_date_strs = sorted(logs.keys(), reverse=True)
        
        for date_str in sorted_date_strs:
            weight = logs[date_str].get("weight", 0)
            if weight > 0:
                return float(weight)
        
        return float(self.profile.get("weight", 0))


    def get_projected_weight(self, logs, target_date):
        """Historical and forward source of truth for the chart line."""
        if isinstance(target_date, datetime):
            target_date = target_date.date()

        # 1. Manual override check
        date_str = target_date.strftime("%Y-%m-%d")
        if logs.get(date_str, {}).get("weight", 0) > 0:
            return float(logs[date_str]["weight"])

        # 2. Logic unification: Find most recent anchor weight
        base_weight = float(self.profile.get("weight", 0))
        anchor_date = None
        anchor_weight = base_weight
        
        log_dates = []
        for d_str in logs.keys():
            try:
                log_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
            except ValueError: continue
        log_dates.sort(reverse=True)

        for d in log_dates:
            if d < target_date and logs[d.strftime("%Y-%m-%d")].get("weight", 0) > 0:
                anchor_date = d
                anchor_weight = float(logs[d.strftime("%Y-%m-%d")]["weight"])
                break
        
        if not anchor_date:
            anchor_date = log_dates[-1] if log_dates else target_date

        # 3. The Walk: Step forward day-by-day to ensure simulation matches chart
        total_kcal_delta = 0
        curr = anchor_date + timedelta(days=1)
        while curr <= target_date:
            day_data = logs.get(curr.strftime("%Y-%m-%d"), {})
            intake = day_data.get('calories', 0)
            
            if intake > 0:
                # Use current sim weight for BMR to prevent drift
                bmr = self.calculate_bmr(anchor_weight + (total_kcal_delta / 3500))
                tdee = bmr * self.map_activity_to_multiplier(day_data.get('activity', 5))
                total_kcal_delta += (intake - (tdee + day_data.get('workout_burn', 0)))
            curr += timedelta(days=1)

        return round(anchor_weight + (total_kcal_delta / 3500), 1)

    def get_estimated_arrival_date(self, logs, target_weight):
        """Uses the same 'Walk' logic to find the date where sim_weight <= target."""
        if not logs: return "Awaiting Data"
        
        current_weight = self.get_latest_weigh_in(logs)
        if current_weight <= target_weight: return "GOAL REACHED"

        # Calculate avg deficit from last 7 days of actual logging
        sorted_dates = sorted(logs.keys(), reverse=True)
        deficits = []
        for date_str in sorted_dates:
            day_data = logs[date_str]
            if day_data.get('calories', 0) > 0:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                hist_w = self.get_projected_weight(logs, dt)
                delta = self.get_daily_delta(day_data['calories'], day_data.get('activity', 5), hist_w, day_data.get('workout_burn', 0))
                if delta is not None: deficits.append(delta)
            if len(deficits) >= 7: break

        if not deficits or sum(deficits) / len(deficits) >= 0:
            return "Surplus (Gaining)" if deficits else "Awaiting Logs"

        avg_deficit = sum(deficits) / len(deficits)
        sim_weight = current_weight
        projected_date = date.today()
        
        # Simulation loop must match the chart's step exactly
        for _ in range(1825):
            if sim_weight <= target_weight:
                return projected_date.strftime("%m/%d/%Y")
            sim_weight += (avg_deficit / 3500)
            projected_date += timedelta(days=1)
            
        return "Indefinite (>5yrs)"
