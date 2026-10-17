import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from location_config import (
    DEFAULT_LAT,
    DEFAULT_LON,
    get_target_location,
    _safe_float,
)

# ===== 配置 =====
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# WMO 天气代码 → 中文描述映射
WMO_CODE_MAP = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小雨", 53: "中雨", 55: "大雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "阵雨", 81: "阵雨", 82: "暴雨",
    95: "雷雨", 96: "雷雨", 99: "雷雨",
}

_session = requests.Session()
_session.proxies = {"http": None, "https": None}

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

LAT = DEFAULT_LAT
LON = DEFAULT_LON


def save_weather_snapshot(weather_data=None, air_data=None):
    """保存天气和空气质量快照，便于后续复盘和答辩展示。"""
    log_path = RESULTS_DIR / "weather_log.csv"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "timestamp": timestamp,
        "latitude": None,
        "longitude": None,
        "weather_text": None,
        "weather_code": None,
        "temperature_2m": None,
        "humidity": None,
        "wind_speed_10m": None,
        "pressure_msl": None,
        "aqi": None,
        "pm2_5": None,
        "pm10": None,
        "air_category": None,
    }

    if weather_data:
        row["latitude"] = weather_data.get("latitude")
        row["longitude"] = weather_data.get("longitude")
        row["weather_text"] = weather_data.get("text")
        row["weather_code"] = weather_data.get("weather_code")
        row["temperature_2m"] = weather_data.get("temp")
        row["humidity"] = weather_data.get("humidity")
        row["wind_speed_10m"] = weather_data.get("windSpeed")
        row["pressure_msl"] = weather_data.get("pressure")

    if air_data:
        row["latitude"] = air_data.get("latitude", row["latitude"])
        row["longitude"] = air_data.get("longitude", row["longitude"])
        row["aqi"] = air_data.get("aqi")
        row["pm2_5"] = air_data.get("pm2_5")
        row["pm10"] = air_data.get("pm10")
        row["air_category"] = air_data.get("category")

    columns = list(row.keys())
    if log_path.exists() and log_path.stat().st_size > 0:
        df = pd.read_csv(log_path)
    else:
        df = pd.DataFrame(columns=columns)

    df = pd.concat([df, pd.DataFrame([row], columns=columns)], ignore_index=True)
    df.to_csv(log_path, index=False, encoding="utf-8-sig")
    return log_path


def fetch_weather(location_name=None, latitude=None, longitude=None):
    """拉取实时天气，优先使用机器附近位置。"""
    lat, lon, _, _ = get_target_location(location_name=location_name, latitude=latitude, longitude=longitude)

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl,weather_code",
        "timezone": "Asia/Shanghai",
    }
    try:
        resp = _session.get(WEATHER_URL, params=params, timeout=10, proxies={"http": None, "https": None})
        resp.raise_for_status()
        data = resp.json()
        current = (data.get("current") or {})
        code = current.get("weather_code")
        text = WMO_CODE_MAP.get(code, f"未知({code})")
        weather = {
            "temp": current.get("temperature_2m", 0),
            "humidity": current.get("relative_humidity_2m", 0),
            "windSpeed": current.get("wind_speed_10m", 0),
            "pressure": current.get("pressure_msl", 0),
            "text": text,
            "weather_code": code,
            "latitude": lat,
            "longitude": lon,
        }
        save_weather_snapshot(weather_data=weather)
        return weather
    except Exception as e:
        print(f" 天气获取失败: {e}")
        return None


def fetch_air_quality(location_name=None, latitude=None, longitude=None):
    """拉取实时空气质量，优先使用机器附近位置。"""
    lat, lon, _, _ = get_target_location(location_name=location_name, latitude=latitude, longitude=longitude)

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm2_5,pm10,us_aqi",
        "timezone": "Asia/Shanghai",
    }
    try:
        resp = _session.get(AIR_URL, params=params, timeout=10, proxies={"http": None, "https": None})
        resp.raise_for_status()
        data = resp.json()
        current = (data.get("current") or {})
        aqi = _safe_float(current.get("us_aqi", 0), 0)
        if aqi <= 50:
            category = "优"
        elif aqi <= 100:
            category = "良"
        elif aqi <= 150:
            category = "轻度污染"
        elif aqi <= 200:
            category = "中度污染"
        else:
            category = "重度污染"
        air = {
            "aqi": aqi,
            "pm2_5": _safe_float(current.get("pm2_5", 0), 0),
            "pm10": _safe_float(current.get("pm10", 0), 0),
            "category": category,
            "latitude": lat,
            "longitude": lon,
        }
        save_weather_snapshot(air_data=air)
        return air
    except Exception as e:
        print(f" 空气质量获取失败: {e}")
        return None


def get_weather_correction_factor(weather_text):
    """根据天气状况返回天气修正系数（用于鸟类去偏）。"""
    text = str(weather_text or "")
    if "晴" in text:
        return 1.0
    elif "阴" in text or "云" in text:
        return 0.85
    elif "雨" in text or "雪" in text:
        return 0.7
    elif "风" in text:
        return 0.5
    else:
        return 1.0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DEAPRE weather API helper")
    parser.add_argument("--location", type=str, help="手动指定地名，如 上海市浦东新区")
    parser.add_argument("--lat", type=float, help="IP 定位不可用时使用的纬度")
    parser.add_argument("--lon", type=float, help="IP 定位不可用时使用的经度")
    args = parser.parse_args()

    print(" 正在拉取天气数据（Open-Meteo，已关闭代理）...\n")
    lat, lon, resolved_name, source = get_target_location(
        location_name=args.location,
        latitude=args.lat,
        longitude=args.lon,
    )
    print(f" 目标位置：{resolved_name} ({source}) -> ({lat}, {lon})")

    weather = fetch_weather(location_name=args.location, latitude=args.lat, longitude=args.lon)
    if weather:
        print("【天气数据】")
        print(f"  温度: {weather['temp']}°C")
        print(f"  湿度: {weather['humidity']}%")
        print(f"  风速: {weather['windSpeed']} km/h")
        print(f"  天气: {weather['text']}")
        print(f"  气压: {weather['pressure']} hPa")
        c = get_weather_correction_factor(weather["text"])
        print(f"   天气修正系数 C_天气: {c}\n")

    air = fetch_air_quality(location_name=args.location, latitude=args.lat, longitude=args.lon)
    if air:
        print("【空气质量】")
        print(f"  AQI: {air['aqi']} ({air['category']})")
        print(f"  PM2.5: {air['pm2_5']} μg/m³")
        print(f"  PM10: {air['pm10']} μg/m³")