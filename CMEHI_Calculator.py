from __future__ import annotations

import math
import glob
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import (
    BIRD_COMPONENT_WEIGHTS,
    CMEHI_WEIGHTS,
    MIN_CONFIDENCE,
    MIN_RECORDS_FOR_BIRD_SCORE,
    R_BASELINE,
    F_BASELINE,
)
from location_config import get_target_location
import location_config

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def get_latest_file(pattern: str) -> Path | None:
    """Return the matching results file with the lexicographically latest name."""
    matches = glob.glob(str(RESULTS_DIR / pattern))
    if not matches:
        return None
    latest_path = sorted(matches, key=lambda path: Path(path).name)[-1]
    return Path(latest_path)


def clip(value, lower=0.0, upper=100.0):
    return max(lower, min(upper, value))


def read_soundscape_score(score_path: Path):
    if not score_path.exists():
        return 50.0
    try:
        df = pd.read_csv(score_path)
        if df.empty:
            return 50.0
        score = pd.to_numeric(df["S_声景"], errors="coerce").dropna()
        if score.empty:
            return 50.0
        return float(score.iloc[-1])
    except Exception:
        return 50.0


def read_air_quality_score(air_path: Path, weather_api_module=None):
    if not air_path.exists():
        return 50.0
    try:
        df = pd.read_csv(air_path)
        if df.empty:
            return 50.0
        pm25_values = pd.to_numeric(df.get("pm2_5_atm", pd.Series(dtype=float)), errors="coerce").dropna()
        if pm25_values.empty:
            return 50.0
        pm25_sensor = float(pm25_values.iloc[-1])
    except Exception:
        return 50.0

    pm25_official = 0.0
    if weather_api_module is not None:
        try:
            official = weather_api_module.fetch_air_quality()
            if official:
                pm25_official = float(official.get("pm2_5", 0.0) or 0.0)
        except Exception:
            pm25_official = 0.0

    if pm25_official <= 0:
        pm25_official = pm25_sensor

    pm25_fused = 0.6 * pm25_sensor + 0.4 * pm25_official
    return compute_air_score(pm25_fused)


def compute_air_score(pm25_value):
    try:
        pm25 = float(pm25_value)
    except (TypeError, ValueError):
        return 50.0

    if pm25 <= 35:
        aqi = pm25 * (50 / 35)
    elif pm25 <= 75:
        aqi = 50 + (pm25 - 35) * (50 / 40)
    else:
        aqi = 100 + (pm25 - 75) * (100 / 115)

    score = 100 - ((aqi - 50) / 150) * 100
    return clip(score, 0.0, 100.0)


def get_weather_correction_factor():
    try:
        import weather_api
        lat, lon, location_name, source = location_config.get_target_location()
        weather = weather_api.fetch_weather(latitude=lat, longitude=lon)
        if not weather:
            return 1.0
        return weather_api.get_weather_correction_factor(weather.get("text", "晴"))
    except Exception:
        return 1.0


def compute_bird_score(detections_path: Path, c_weather: float, dawn_score: float | None = None):
    if not detections_path.exists():
        return 50.0
    try:
        df = pd.read_csv(detections_path)
    except Exception:
        return 50.0

    if df.empty:
        return 50.0

    if "confidence" in df.columns:
        df = df[pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0) >= MIN_CONFIDENCE].copy()
    if df.empty:
        return 50.0

    if len(df) < MIN_RECORDS_FOR_BIRD_SCORE:
        print(f"⚠️ 鸟类识别记录不足 {MIN_RECORDS_FOR_BIRD_SCORE} 条，得分置信度低。")

    species_count = df["common_name"].nunique(dropna=True)
    total_calls = len(df)
    species_counts = df["common_name"].value_counts()
    total = species_counts.sum()

    if total > 0:
        probs = species_counts / total
        shannon = -float((probs * probs.map(math.log)).sum())
    else:
        shannon = 0.0

    if c_weather <= 0:
        c_weather = 1.0

    r_debiased = species_count / c_weather
    f_debiased = total_calls / c_weather
    r_norm = min((r_debiased / R_BASELINE) * 100, 100.0)
    f_norm = min((f_debiased / F_BASELINE) * 100, 100.0)

    if species_count > 1:
        h_norm = min((shannon / math.log(species_count)) * 100, 100.0)
    else:
        h_norm = 0.0

    bird_score = (
        BIRD_COMPONENT_WEIGHTS["r"] * r_norm
        + BIRD_COMPONENT_WEIGHTS["f"] * f_norm
        + BIRD_COMPONENT_WEIGHTS["h"] * h_norm
    )
    return clip(bird_score, 0.0, 100.0)


# 👇 新增：读取麻雀通讯抑制评分函数
def read_communication_score(sparrow_path: Path):
    """读取麻雀通讯抑制评分，取全天平均值"""
    if not sparrow_path.exists():
        print(f"⚠️ 未找到麻雀通讯评分表 ({sparrow_path.name})，使用默认中性分 50。")
        return 50.0
    try:
        df = pd.read_csv(sparrow_path)
        if df.empty:
            return 50.0
        
        scores = pd.to_numeric(df["sparrow_score"], errors="coerce").dropna()
        if scores.empty:
            return 50.0
            
        return float(scores.mean())
    except Exception as e:
        print(f"读取麻雀数据失败: {e}")
        return 50.0


def calculate_cmehi():
    weather_factor = get_weather_correction_factor()
    detections_path = get_latest_file(
        "detections_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].csv"
    )
    sparrow_path = get_latest_file(
        "sparrow_score_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].csv"
    )
    
    # 1. 声景维度
    soundscape_path = RESULTS_DIR / "soundscape_scores.csv"
    soundscape_score = read_soundscape_score(soundscape_path)
    if soundscape_path.exists():
        age_hours = (datetime.now() - datetime.fromtimestamp(soundscape_path.stat().st_mtime)).total_seconds() / 3600.0
        if age_hours > 24:
            print("⚠️ 声景数据已过期，请重新运行 soundscape.py。")

    # 2. 空气维度
    try:
        import weather_api
        air_score = read_air_quality_score(RESULTS_DIR / "air_quality.csv", weather_api_module=weather_api)
    except Exception:
        air_score = read_air_quality_score(RESULTS_DIR / "air_quality.csv")

    # 3. 鸟类多样性维度
    if detections_path is None:
        print("⚠️ 未找到日期格式的 detections 文件，鸟类多样性得分使用默认中性分 50。")
        bird_score = 50.0
    else:
        bird_score = compute_bird_score(detections_path, weather_factor)
    
    # 4. 新增：麻雀通讯干扰维度
    if sparrow_path is None:
        print("⚠️ 未找到日期格式的 sparrow_score 文件，通讯干扰得分使用默认中性分 50。")
        comm_score = 50.0
    else:
        comm_score = read_communication_score(sparrow_path)

    # 5. 光污染维度
    if detections_path is None:
        chorus = {"S_晨鸣": 50.0, "S_夜鸣": 50.0, "S_光污染": 50.0, "样本天数": 0}
    else:
        try:
            from chorus_analysis import calculate_chorus_scores
            chorus = calculate_chorus_scores(detections_path)
        except Exception:
            chorus = {"S_晨鸣": 50.0, "S_夜鸣": 50.0, "S_光污染": 50.0, "样本天数": 0}

    s_light = chorus.get("S_光污染", 50.0)

    # 👇 智能权重分配（如果没有在 config 里配置新权重，自动适应 5 维体系）
    if "communication" in CMEHI_WEIGHTS:
        w_sound = CMEHI_WEIGHTS.get("soundscape", 0.25)
        w_bird = CMEHI_WEIGHTS.get("bird", 0.25)
        w_comm = CMEHI_WEIGHTS.get("communication", 0.20)
        w_air = CMEHI_WEIGHTS.get("air", 0.15)
        w_light = CMEHI_WEIGHTS.get("light", 0.15)
    else:
        # 如果没改 config.py，按以下最优比例计算：
        # 声景25% + 多样性25% + 通讯20% + 空气15% + 光污染15%
        w_sound, w_bird, w_comm, w_air, w_light = 0.25, 0.25, 0.20, 0.15, 0.15

    cmehi = (
        w_sound * soundscape_score
        + w_bird * bird_score
        + w_comm * comm_score
        + w_air * air_score
        + w_light * s_light
    )
    
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "S_声景": round(soundscape_score, 2),
        "S_鸟类多样性": round(bird_score, 2),
        "S_通讯干扰": round(comm_score, 2),  # 新增维度
        "S_空气": round(air_score, 2),
        "S_晨鸣": chorus.get("S_晨鸣", 50.0),
        "S_夜鸣": chorus.get("S_夜鸣", 50.0),
        "S_光污染": round(s_light, 2),
        "CMEHI": round(cmehi, 2),
        "weather_factor": round(weather_factor, 2),
    }


def append_report(report_path: Path, metric: dict):
    report_path.parent.mkdir(exist_ok=True)
    # 👇 更新表头，加入新维度
    columns = [
        "timestamp", "S_声景", "S_鸟类多样性", "S_通讯干扰", 
        "S_空气", "S_晨鸣", "S_夜鸣", "S_光污染", "CMEHI", "weather_factor"
    ]

    if report_path.exists() and report_path.stat().st_size > 0:
        df = pd.read_csv(report_path)
        # 如果旧表格没有新列，补齐空列防止报错
        for col in columns:
            if col not in df.columns:
                df[col] = None
    else:
        df = pd.DataFrame(columns=columns)

    row = pd.DataFrame([metric], columns=columns)
    df = pd.concat([df, row], ignore_index=True)
    df.to_csv(report_path, index=False, encoding="utf-8-sig")
    return report_path


def main():
    metric = calculate_cmehi()
    output_path = RESULTS_DIR / "CMEHI_Report.csv"
    append_report(output_path, metric)

    print("========================================")
    print("  CMEHI 综合生态评分结果")
    print("========================================")
    print(f"  时间: {metric['timestamp']}")
    print(f"   声景得分: {metric['S_声景']}")
    print(f"   鸟类多样性得分: {metric['S_鸟类多样性']}")
    print(f"   麻雀通讯干扰得分: {metric['S_通讯干扰']}  <-- 新增核心指标")
    print(f"   空气质量得分: {metric['S_空气']}")
    print(f"   光污染得分: {metric['S_光污染']} (晨鸣:{metric['S_晨鸣']}, 夜鸣:{metric['S_夜鸣']})")
    print("----------------------------------------")
    print(f"   最终 CMEHI 得分: {metric['CMEHI']}")
    print(f"   今日天气修正系数: {metric['weather_factor']}")
    print("========================================")
    print(f"   报告已追加保存至: {output_path.resolve()}")


if __name__ == "__main__":
    main()