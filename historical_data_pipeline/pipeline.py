#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import math
import time
import argparse
import requests
import pandas as pd
import holidays

from datetime import datetime, timedelta
from tqdm import tqdm

# CONFIG
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH"
# Disaster is considered relevant if it occurs within this distance (km)
DISASTER_RADIUS_KM = 150
# Also check disasters a few days around target date
DISASTER_DATE_WINDOW = 3


# 1. CITY -> LATITUDE / LONGITUDE
def geocode_city(city, country=None):
    """Convert city name into coordinates."""
    search_name = city
    if country:
        search_name = f"{city}, {country}"

    params = {
        "name": search_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    response = requests.get(GEOCODING_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data.get("results"):
        raise ValueError(f"City not found: {search_name}")

    place = data["results"][0]

    return {
        "city": place.get("name"),
        "country": place.get("country"),
        "country_code": place.get("country_code"),
        "admin1": place.get("admin1"),
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "timezone": place.get("timezone")
    }


# 2. SEASON
def get_season(date, latitude):
    """Basic meteorological season (handles Northern and Southern hemispheres)."""
    month = date.month

    # Northern hemisphere
    if latitude >= 0:
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Autumn"
    # Southern hemisphere
    else:
        if month in [12, 1, 2]:
            return "Summer"
        elif month in [3, 4, 5]:
            return "Autumn"
        elif month in [6, 7, 8]:
            return "Winter"
        else:
            return "Spring"


# 3. HISTORICAL WEATHER
def get_weather(latitude, longitude, date):
    date_string = date.strftime("%Y-%m-%d")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date_string,
        "end_date": date_string,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "apparent_temperature_max",
            "precipitation_sum",
            "rain_sum",
            "snowfall_sum",
            "wind_speed_10m_max"
        ]),
        "timezone": "auto"
    }

    response = requests.get(WEATHER_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    daily = data.get("daily", {})

    def value(name):
        values = daily.get(name)
        if not values:
            return None
        return values[0]

    return {
        "temperature_max_c": value("temperature_2m_max"),
        "temperature_min_c": value("temperature_2m_min"),
        "temperature_mean_c": value("temperature_2m_mean"),
        "apparent_temperature_max_c": value("apparent_temperature_max"),
        "precipitation_mm": value("precipitation_sum"),
        "rain_mm": value("rain_sum"),
        "snowfall_cm": value("snowfall_sum"),
        "wind_speed_max_kmh": value("wind_speed_10m_max")
    }


# 4. HOLIDAYS / OCCASIONS
def get_holiday(date, country_code):
    try:
        country_holidays = holidays.country_holidays(country_code, years=[date.year])
    except Exception:
        return {"is_holiday": 0, "holiday_name": None}

    if date in country_holidays:
        return {"is_holiday": 1, "holiday_name": str(country_holidays[date])}

    return {"is_holiday": 0, "holiday_name": None}


# 5. DISTANCE CALCULATION
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# 6. DISASTER DATA
def get_disasters(latitude, longitude, date, radius_km=150, date_window=3):
    start_date = (date - timedelta(days=date_window)).strftime("%Y-%m-%d")
    end_date = (date + timedelta(days=date_window)).strftime("%Y-%m-%d")

    params = {
        "eventlist": "EQ;TC;FL;VO;WF;DR",
        "fromdate": start_date,
        "todate": end_date,
        "alertlevel": "green;orange;red"
    }

    try:
        response = requests.get(GDACS_URL, params=params, timeout=40)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("GDACS error:", e)
        return {
            "has_disaster": 0,
            "disaster_count": 0,
            "disaster_type": None,
            "disaster_alert": None,
            "nearest_disaster_km": None
        }

    nearby_events = []
    features = data.get("features", [])

    for feature in features:
        geometry = feature.get("geometry")
        if not geometry or geometry.get("type") != "Point":
            continue

        coordinates = geometry.get("coordinates")
        if not coordinates or len(coordinates) < 2:
            continue

        disaster_lon, disaster_lat = coordinates[0], coordinates[1]
        distance = haversine_distance(latitude, longitude, disaster_lat, disaster_lon)

        if distance <= radius_km:
            properties = feature.get("properties", {})
            nearby_events.append({
                "distance_km": round(distance, 2),
                "type": properties.get("eventtype"),
                "name": properties.get("name"),
                "alert": properties.get("alertlevel")
            })

    if not nearby_events:
        return {
            "has_disaster": 0,
            "disaster_count": 0,
            "disaster_type": None,
            "disaster_alert": None,
            "nearest_disaster_km": None
        }

    nearby_events.sort(key=lambda x: x["distance_km"])
    nearest = nearby_events[0]
    disaster_types = sorted(set(event["type"] for event in nearby_events if event["type"]))

    return {
        "has_disaster": 1,
        "disaster_count": len(nearby_events),
        "disaster_type": "|".join(disaster_types),
        "disaster_alert": nearest["alert"],
        "nearest_disaster_km": nearest["distance_km"]
    }


# 7. DATE FEATURES
def get_date_features(date):
    return {
        "year": date.year,
        "month": date.month,
        "day": date.day,
        "day_of_week": date.weekday(),
        "day_name": date.strftime("%A"),
        "week_of_year": int(date.strftime("%V")),
        "is_weekend": int(date.weekday() >= 5)
    }


# 8. BUILD ONE TRAINING ROW
def build_training_row(city, country, date):
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")

    location = geocode_city(city, country)
    latitude = location["latitude"]
    longitude = location["longitude"]

    weather = get_weather(latitude, longitude, date)
    holiday = get_holiday(date, location["country_code"])
    disaster = get_disasters(latitude, longitude, date, radius_km=DISASTER_RADIUS_KM)

    row = {
        "city": location["city"],
        "country": location["country"],
        "region": location["admin1"],
        "latitude": latitude,
        "longitude": longitude,
        "date": date.strftime("%Y-%m-%d"),
        "season": get_season(date, latitude)
    }

    row.update(get_date_features(date))
    row.update(weather)
    row.update(holiday)
    row.update(disaster)

    return row


# 9. CREATE DATASET FOR DATE RANGE
def create_dataset(city, country, start_date, end_date=None):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    
    if not end_date:
        end_date = start_date
        
    end = datetime.strptime(end_date, "%Y-%m-%d")

    rows = []
    current_date = start

    while current_date <= end:
        print(f"Collecting {city} for {current_date.date()}")
        try:
            row = build_training_row(city, country, current_date)
            rows.append(row)
        except Exception as e:
            print(f"Error on {current_date.date()}: {e}")

        time.sleep(0.15)
        current_date += timedelta(days=1)

    return pd.DataFrame(rows)


# 10. MAIN RUNNER
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect historical weather, holiday, and disaster data.")
    parser.add_argument("--city", type=str, required=True, help="City name (e.g., Multan)")
    parser.add_argument("--country", type=str, default=None, help="Country name (e.g., Pakistan)")
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default="dataset.csv", help="Output CSV file path")

    args = parser.parse_args()

    df = create_dataset(
        city=args.city,
        country=args.country,
        start_date=args.start,
        end_date=args.end
    )

    print("\nDataset Preview:")
    print(df.head())

    df.to_csv(args.output, index=False)
    print(f"\nSuccessfully saved dataset to {args.output}")

