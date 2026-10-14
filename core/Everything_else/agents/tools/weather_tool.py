# [weather_tool.py]

import json
import urllib.request
import urllib.parse
from typing import Dict, Any

TOOL_SPEC = {
    "name": "weather_tool",
    "description": "Retrieves real-time weather conditions and a 3-day forecast for any city, zipcode, or location globally.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name, zip code, or location (e.g. 'Chicago', '90210', or 'London, UK')."
            },
            "unit": {
                "type": "string",
                "enum": ["USCS", "metric"],
                "description": "Temperature and speed unit preference ('USCS' for Fahrenheit/mph, 'metric' for Celsius/kmh)."
            }
        },
        "required": ["location"]
    }
}

def execute(**kwargs) -> str:
    """Standard entrypoint called by tool_runner.py."""
    # Check location or common alias parameters passed by LLMs
    location = (
        kwargs.get("location") or 
        kwargs.get("query") or 
        kwargs.get("query_1") or 
        kwargs.get("city") or 
        ""
    ).strip()
    
    unit = kwargs.get("unit", "USCS").strip().upper()

    if not location:
        return "Error: 'location' parameter is required."

    # Format URL for wttr.in JSON API
    encoded_loc = urllib.parse.quote(location)
    
    # Force USCS (Fahrenheit) or Metric (Celsius) via query parameters
    unit_param = "?u&format=j1" if unit == "USCS" else "?m&format=j1"
    url = f"https://wttr.in/{encoded_loc}{unit_param}"

    headers = {
        "User-Agent": "GhostDrive-Agent/1.0"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)

        # 1. Parse Current Conditions
        current = data.get("current_condition", [{}])[0]
        nearest_area = data.get("nearest_area", [{}])[0]
        
        city = nearest_area.get("areaName", [{}])[0].get("value", location)
        region = nearest_area.get("region", [{}])[0].get("value", "")
        country = nearest_area.get("country", [{}])[0].get("value", "")
        
        location_str = f"{city}, {region}, {country}".strip(", ")

        temp_key = "temp_F" if unit == "USCS" else "temp_C"
        feels_key = "FeelsLikeF" if unit == "USCS" else "FeelsLikeC"
        speed_key = "windspeedMiles" if unit == "USCS" else "windspeedKmph"
        speed_unit = "mph" if unit == "USCS" else "km/h"
        temp_unit = "°F" if unit == "USCS" else "°C"

        temp = current.get(temp_key, "N/A")
        feels = current.get(feels_key, "N/A")
        desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
        humidity = current.get("humidity", "N/A")
        wind_speed = current.get(speed_key, "N/A")
        wind_dir = current.get("winddir16Point", "N/A")

        report = [
            f"=== CURRENT WEATHER REPORT: {location_str.upper()} ===",
            f"Condition: {desc}",
            f"Temperature: {temp}{temp_unit} (Feels like {feels}{temp_unit})",
            f"Humidity: {humidity}%",
            f"Wind: {wind_speed} {speed_unit} ({wind_dir})",
            "\n--- 3-DAY FORECAST ---"
        ]

        # 2. Parse Forecast Days
        weather_days = data.get("weather", [])
        for day in weather_days[:3]:
            date = day.get("date", "N/A")
            max_temp = day.get(f"maxtemp{temp_unit[-1]}", "N/A")
            min_temp = day.get(f"mintemp{temp_unit[-1]}", "N/A")
            
            # Grab midday weather description from hourly array
            hourly = day.get("hourly", [])
            midday_desc = hourly[len(hourly)//2].get("weatherDesc", [{}])[0].get("value", "N/A") if hourly else "N/A"

            report.append(f"• {date}: {midday_desc} | High: {max_temp}{temp_unit} / Low: {min_temp}{temp_unit}")

        report.append("=========================================")
        return "\n".join(report)

    except Exception as e:
        return f"Weather Retrieval Error for '{location}': {str(e)}"