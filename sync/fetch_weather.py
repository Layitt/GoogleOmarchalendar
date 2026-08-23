#!/usr/bin/env python3
"""Fetch weather forecast from Open-Meteo API.

Supports dynamic geocoding for any city, auto-detection, and multi-language (ES/EN).
Writes clean JSON to ~/.local/state/omarchy/calendar-weather.json.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

STATE_DIR = os.path.expanduser("~/.local/state/omarchy")
OUTPUT_FILE = os.path.join(STATE_DIR, "calendar-weather.json")
LEGACY_OUTPUT_FILE = os.path.join(STATE_DIR, "weather-morelia.json")

WMO_MAP_ES = {
    0: ("Despejado", "󰖙"),
    1: ("Mayormente soleado", "󰖕"),
    2: ("Parcialmente nublado", "󰖕"),
    3: ("Nublado", "󰖐"),
    45: ("Niebla", "󰖑"),
    48: ("Niebla con escarcha", "󰖑"),
    51: ("Llovizna ligera", "󰖗"),
    53: ("Llovizna moderada", "󰖗"),
    55: ("Llovizna densa", "󰖗"),
    56: ("Llovizna helada", "󰖗"),
    57: ("Llovizna helada densa", "󰖗"),
    61: ("Lluvia ligera", "󰖖"),
    63: ("Lluvia moderada", "󰖖"),
    65: ("Lluvia fuerte", "󰖖"),
    66: ("Lluvia helada", "󰖖"),
    67: ("Lluvia helada fuerte", "󰖖"),
    71: ("Nieve ligera", "󰖘"),
    73: ("Nieve moderada", "󰖘"),
    75: ("Nieve fuerte", "󰖘"),
    77: ("Granizo", "󰖘"),
    80: ("Chubascos ligeros", "󰖖"),
    81: ("Chubascos moderados", "󰖖"),
    82: ("Chubascos violentos", "󰖖"),
    85: ("Chubascos de nieve", "󰖘"),
    86: ("Chubascos de nieve fuertes", "󰖘"),
    95: ("Tormenta eléctrica", "󰙾"),
    96: ("Tormenta con granizo", "󰙾"),
    99: ("Tormenta fuerte con granizo", "󰙾")
}

WMO_MAP_EN = {
    0: ("Clear sky", "󰖙"),
    1: ("Mainly clear", "󰖕"),
    2: ("Partly cloudy", "󰖕"),
    3: ("Overcast", "󰖐"),
    45: ("Fog", "󰖑"),
    48: ("Depositing rime fog", "󰖑"),
    51: ("Light drizzle", "󰖗"),
    53: ("Moderate drizzle", "󰖗"),
    55: ("Dense drizzle", "󰖗"),
    56: ("Freezing drizzle", "󰖗"),
    57: ("Dense freezing drizzle", "󰖗"),
    61: ("Slight rain", "󰖖"),
    63: ("Moderate rain", "󰖖"),
    65: ("Heavy rain", "󰖖"),
    66: ("Freezing rain", "󰖖"),
    67: ("Heavy freezing rain", "󰖖"),
    71: ("Slight snow", "󰖘"),
    73: ("Moderate snow", "󰖘"),
    75: ("Heavy snow", "󰖘"),
    77: ("Snow grains", "󰖘"),
    80: ("Slight rain showers", "󰖖"),
    81: ("Moderate rain showers", "󰖖"),
    82: ("Violent rain showers", "󰖖"),
    85: ("Slight snow showers", "󰖘"),
    86: ("Heavy snow showers", "󰖘"),
    95: ("Thunderstorm", "󰙾"),
    96: ("Thunderstorm with slight hail", "󰙾"),
    99: ("Thunderstorm with heavy hail", "󰙾")
}

def geocode_city(query, lang="es"):
    if not query or query.lower() in ("auto", "detect", ""):
        return None
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(query.strip())}&count=1&language={lang}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "OmarchyCalendar/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                r = results[0]
                name = r.get("name", query)
                admin = r.get("admin1", "")
                country = r.get("country", "")
                display = f"{name}, {admin}" if admin else (f"{name}, {country}" if country else name)
                return float(r["latitude"]), float(r["longitude"]), display, r.get("timezone", "auto")
    except Exception as e:
        print(f"Geocoding error: {e}", file=sys.stderr)
    return None

def detect_location(custom_query=None, lang="es"):
    # 1. Check custom configured location
    if custom_query and custom_query.strip() and custom_query.lower() not in ("auto", ""):
        geo = geocode_city(custom_query, lang)
        if geo:
            return geo

    # 2. Check user-configured omarchy weather.json
    cfg = os.path.expanduser("~/.config/omarchy/weather.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("latitude") and d.get("longitude"):
                    return float(d["latitude"]), float(d["longitude"]), d.get("name", "Local"), "auto"
        except Exception:
            pass

    # 3. Try IP auto-detection
    try:
        req = urllib.request.Request("https://ipapi.co/json/", headers={"User-Agent": "OmarchyCalendar/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("latitude") and data.get("longitude"):
                city = data.get("city", "")
                region = data.get("region", "")
                name = f"{city}, {region}" if region else city
                tz = data.get("timezone", "auto")
                return float(data["latitude"]), float(data["longitude"]), name, tz
    except Exception:
        pass

    # 4. Fallback coordinates (Morelia, MX)
    return 19.7060, -101.1950, "Morelia, Michoacán", "America/Mexico_City"

def fetch_weather(location_query=None, lang="es"):
    lat, lon, location_name, tz = detect_location(location_query, lang)
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
        f"hourly=temperature_2m,precipitation_probability,weather_code&"
        f"timezone={tz}&forecast_days=16"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OmarchyCalendar/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching weather: {e}", file=sys.stderr)
        return False

    daily = data.get("daily", {})
    hourly = data.get("hourly", {})

    dates = daily.get("time", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    daily_codes = daily.get("weather_code", [])
    daily_rain_probs = daily.get("precipitation_probability_max", [])

    hourly_times = hourly.get("time", [])
    hourly_probs = hourly.get("precipitation_probability", [])
    hourly_temps = hourly.get("temperature_2m", [])
    hourly_codes = hourly.get("weather_code", [])

    # Group hourly entries by date
    hourly_by_date = {}
    for t, p, temp, code in zip(hourly_times, hourly_probs, hourly_temps, hourly_codes):
        if "T" in t:
            d_str, h_str = t.split("T")
            if d_str not in hourly_by_date:
                hourly_by_date[d_str] = []
            hourly_by_date[d_str].append((h_str, p, temp, code))

    wmo_table = WMO_MAP_EN if lang == "en" else WMO_MAP_ES
    forecast = {}
    for i, d_str in enumerate(dates):
        t_max = round(temp_max[i]) if (i < len(temp_max) and temp_max[i] is not None) else None
        t_min = round(temp_min[i]) if (i < len(temp_min) and temp_min[i] is not None) else None
        code = daily_codes[i] if (i < len(daily_codes) and daily_codes[i] is not None) else 0
        desc, icon = wmo_table.get(code, ("Despejado" if lang == "es" else "Clear sky", "󰖙"))
        max_prob = daily_rain_probs[i] if (i < len(daily_rain_probs) and daily_rain_probs[i] is not None) else 0

        h_list = hourly_by_date.get(d_str, [])
        peak_hour = None
        peak_prob = 0
        for h_str, p, temp, c in h_list:
            if p is not None and p > peak_prob:
                peak_prob = p
                peak_hour = h_str

        if max_prob >= 25 and peak_hour:
            rain_summary = f"{max_prob}% (máx. {peak_hour})" if lang == "es" else f"{max_prob}% (peak {peak_hour})"
        elif max_prob >= 15:
            rain_summary = f"{max_prob}% baja" if lang == "es" else f"{max_prob}% low"
        else:
            rain_summary = f"{max_prob}% (sin lluvia)" if lang == "es" else f"{max_prob}% (no rain)"

        forecast[d_str] = {
            "tempMax": t_max,
            "tempMin": t_min,
            "weatherCode": code,
            "weatherDesc": desc,
            "icon": icon,
            "rainProb": max_prob,
            "peakHour": peak_hour,
            "rainSummary": rain_summary
        }

    output = {
        "city": location_name,
        "updatedAt": datetime.now().isoformat(),
        "forecast": forecast
    }

    os.makedirs(STATE_DIR, exist_ok=True)
    temp_file = OUTPUT_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, OUTPUT_FILE)

    try:
        with open(LEGACY_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return True

def main():
    parser = argparse.ArgumentParser(description="Fetch weather for Omarchy calendar")
    parser.add_argument("--location", default=None, help="City name or coordinates")
    parser.add_argument("--lang", default="es", choices=["es", "en"], help="Language code (es/en)")
    args = parser.parse_args()

    ok = fetch_weather(args.location, args.lang)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
