from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from location_config import get_target_location

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
OUTPUT_DATE = datetime.now().strftime("%Y%m%d")

DAWN_ADVANCE_PENALTY = 1.5
NIGHT_DELAY_PENALTY = 1.5
CHORUS_FUSION = {"dawn": 0.5, "night": 0.5}
DEFAULT_CHORUS_SCORE = 50.0
CIVIL_TWILIGHT_OFFSET_MIN = 30.0


def parse_audio_time(file_name: str):
    """从 rec_20261011_163134.wav 解析出 datetime。"""
    stem = Path(file_name).stem
    if not stem.startswith("rec_"):
        return None
    try:
        raw = stem.split("_", 1)[1]
        return datetime.strptime(raw, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def get_sun_times(day, latitude: float, longitude: float):
    """用 astral 精确计算当天日出、日落。"""
    try:
        from astral import LocationInfo
        from astral.sun import sun

        loc = LocationInfo(
            name="monitor",
            region="CN",
            timezone="Asia/Shanghai",
            latitude=latitude,
            longitude=longitude,
        )
        s = sun(loc.observer, date=day, tzinfo="Asia/Shanghai")
        return {
            "sunrise": s["sunrise"].replace(tzinfo=None),
            "sunset": s["sunset"].replace(tzinfo=None),
            "dawn": s["dawn"].replace(tzinfo=None),
            "dusk": s["dusk"].replace(tzinfo=None),
            "source": "astral",
        }
    except Exception:
        from datetime import timedelta

        base = datetime.combine(day, datetime.min.time())
        month = day.month
        if month in (5, 6, 7):
            sr, ss = 5.5, 19.0
        elif month in (11, 12, 1):
            sr, ss = 6.8, 17.3
        else:
            sr, ss = 6.0, 18.3
        return {
            "sunrise": base + timedelta(hours=sr),
            "sunset": base + timedelta(hours=ss),
            "dawn": base + timedelta(hours=sr - 0.5),
            "dusk": base + timedelta(hours=ss + 0.5),
            "source": "fallback",
        }


def calculate_chorus_scores(detections_path: Path):
    """
    同时计算晨鸣提前量和夜鸣延迟量，融合成 S_光污染。
    返回：S_晨鸣、S_夜鸣、S_光污染、样本天数
    """
    empty = {
        "S_晨鸣": DEFAULT_CHORUS_SCORE,
        "S_夜鸣": DEFAULT_CHORUS_SCORE,
        "S_光污染": DEFAULT_CHORUS_SCORE,
        "样本天数": 0,
    }
    if not detections_path.exists():
        return empty

    try:
        df = pd.read_csv(detections_path)
    except Exception:
        return empty
    if df.empty or "audio_file" not in df.columns:
        return empty

    daily_times = {}
    for file_name in df["audio_file"].dropna().unique():
        t = parse_audio_time(str(file_name))
        if t is None:
            continue
        daily_times.setdefault(t.date(), []).append(t)

    if not daily_times:
        return empty

    lat, lon, _, _ = get_target_location()
    dawn_scores = []
    night_scores = []

    for day, times in daily_times.items():
        first_bird = min(times)
        last_bird = max(times)
        sun = get_sun_times(day, lat, lon)

        dawn_ref = sun["dawn"] - pd.Timedelta(minutes=CIVIL_TWILIGHT_OFFSET_MIN).to_pytimedelta()
        advance_min = max((dawn_ref - first_bird).total_seconds() / 60.0, 0.0)
        s_dawn = max(100 - DAWN_ADVANCE_PENALTY * advance_min, 0.0)
        dawn_scores.append(s_dawn)

        night_ref = sun["dusk"]
        delay_min = max((last_bird - night_ref).total_seconds() / 60.0, 0.0)
        s_night = max(100 - NIGHT_DELAY_PENALTY * delay_min, 0.0)
        night_scores.append(s_night)

    s_dawn_avg = sum(dawn_scores) / len(dawn_scores) if dawn_scores else DEFAULT_CHORUS_SCORE
    s_night_avg = sum(night_scores) / len(night_scores) if night_scores else DEFAULT_CHORUS_SCORE

    s_light = CHORUS_FUSION["dawn"] * s_dawn_avg + CHORUS_FUSION["night"] * s_night_avg

    return {
        "S_晨鸣": round(s_dawn_avg, 2),
        "S_夜鸣": round(s_night_avg, 2),
        "S_光污染": round(s_light, 2),
        "样本天数": len(daily_times),
    }


def main():
    result = calculate_chorus_scores(RESULTS_DIR / f"detections_{OUTPUT_DATE}.csv")
    print(" 晨鸣 + 夜鸣分析")
    print(f"  S_晨鸣（越高越好）: {result['S_晨鸣']}")
    print(f"  S_夜鸣（越高越好）: {result['S_夜鸣']}")
    print(f"  S_光污染（融合）: {result['S_光污染']}")
    print(f"  样本天数: {result['样本天数']}")


if __name__ == "__main__":
    main()
