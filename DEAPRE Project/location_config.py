import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DEFAULT_LAT = 31.23
DEFAULT_LON = 121.47
DEFAULT_LOCATION = "上海市浦东新区"

ENV_LAT_KEY = "DEAPRE_LAT"
ENV_LON_KEY = "DEAPRE_LON"
ENV_LOCATION_KEY = "DEAPRE_LOCATION"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
IP_LOCATION_URL = "http://ip-api.com/json/"

_session = requests.Session()
_session.proxies = {"http": None, "https": None}

_LOCATION_CACHE = {}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_ip_location():
    """Resolve the current machine's approximate public-IP location."""
    try:
        resp = _session.get(IP_LOCATION_URL, timeout=8, proxies={"http": None, "https": None})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            lat = _safe_float(data.get("lat"), DEFAULT_LAT)
            lon = _safe_float(data.get("lon"), DEFAULT_LON)
            return lat, lon, data.get("city") or data.get("regionName") or "当前机器位置", "ip"
    except Exception:
        pass
    return None


def resolve_location_name(location_name):
    """Resolve a place name using the geocoding API."""
    if not location_name:
        return None

    try:
        params = {
            "name": location_name,
            "count": 1,
            "language": "zh",
            "format": "json",
        }
        resp = _session.get(GEOCODING_URL, params=params, timeout=10, proxies={"http": None, "https": None})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if results:
            place = results[0]
            return (
                _safe_float(place.get("latitude", DEFAULT_LAT), DEFAULT_LAT),
                _safe_float(place.get("longitude", DEFAULT_LON), DEFAULT_LON),
                place.get("name", location_name),
                "geocode",
            )
    except Exception:
        pass

    return None


def resolve_location(location_name=None):
    """Use IP geolocation first, then a named place, then the Shanghai default."""
    ip_location = resolve_ip_location()
    if ip_location is not None:
        return ip_location

    named_location = resolve_location_name(location_name)
    if named_location is not None:
        return named_location

    return DEFAULT_LAT, DEFAULT_LON, DEFAULT_LOCATION, "default"


def get_manual_coordinates_from_env():
    """读取环境变量中的坐标配置。"""
    lat_str = os.getenv(ENV_LAT_KEY)
    lon_str = os.getenv(ENV_LON_KEY)
    if lat_str is None and lon_str is None:
        return None, None

    lat = _safe_float(lat_str, DEFAULT_LAT) if lat_str is not None else DEFAULT_LAT
    lon = _safe_float(lon_str, DEFAULT_LON) if lon_str is not None else DEFAULT_LON
    return lat, lon


def get_target_location(location_name=None, latitude=None, longitude=None):
    """Use environment coordinates, explicit coordinates, IP location, then the default."""
    cache_key = (location_name, latitude, longitude)
    if cache_key in _LOCATION_CACHE:
        return _LOCATION_CACHE[cache_key]

    env_lat, env_lon = get_manual_coordinates_from_env()
    if env_lat is not None and env_lon is not None:
        result = (env_lat, env_lon, "environment", "manual")
        _LOCATION_CACHE[cache_key] = result
        return result

    if latitude is not None or longitude is not None:
        lat = _safe_float(latitude, DEFAULT_LAT) if latitude is not None else DEFAULT_LAT
        lon = _safe_float(longitude, DEFAULT_LON) if longitude is not None else DEFAULT_LON
        result = (lat, lon, "manual", "manual")
        _LOCATION_CACHE[cache_key] = result
        return result

    ip_location = resolve_ip_location()
    if ip_location is not None:
        result = ip_location
        _LOCATION_CACHE[cache_key] = result
        return result

    result = (DEFAULT_LAT, DEFAULT_LON, DEFAULT_LOCATION, "default")
    _LOCATION_CACHE[cache_key] = result
    return result
