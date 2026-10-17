import os
import glob
import re
import pandas as pd
import librosa
import numpy as np
from datetime import datetime
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer

from config import MIN_CONFIDENCE as MIN_CONF
from location_config import get_target_location

# ===== 核心配置 =====
SENTINEL_SPECIES = "Eurasian Tree Sparrow" 
SENTINEL_CONFIDENCE = 0.8 

#  新增：树麻雀在安静环境下的最低频率基线（Hz）。请查阅当地文献调整。
BASELINE_FMIN = 2500.0 

NOISE_LABELS = [
    "Vehicle", "Car", "Truck", "Motorcycle", 
    "Human vocal", "Human non-vocal", 
    "Engine", "Machinery", "Siren"
]

DATA_DIR = "data"              
OUTPUT_DIR = "results"         
OUTPUT_DATE = datetime.now().strftime("%Y%m%d")
DETECTIONS_FILENAME = f"detections_{OUTPUT_DATE}.csv"
SPARROW_SCORE_FILENAME = f"sparrow_score_{OUTPUT_DATE}.csv"
DETECTIONS_COLUMNS = [
    "audio_file", "common_name", "scientific_name",
    "start_time", "end_time", "confidence",
]
SPARROW_SCORE_COLUMNS = [
    "time", "audio_file", "sparrow_total_calls", "sparrow_high_conf_calls",
    "SANE_noise_level", "sparrow_score", "avg_fmin_hz", "fmin_shift_percent",
]
LAT, LON, LOCATION_NAME, LOCATION_SOURCE = get_target_location()

def parse_audio_date(audio_path: str):
    match = re.search(r"rec_(\d{8})_(\d{6})", os.path.basename(audio_path))
    if match:
        return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    return datetime.now()

#  新增：提取一段音频最低频率(Fmin)的函数
def extract_fmin(y, sr):
    """使用短时傅里叶变换提取能量最高的频段的最低频率"""
    if len(y) == 0:
        return None
    # 计算频谱
    D = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    
    # 计算每个频率的平均能量(dB)
    power_db = librosa.amplitude_to_db(np.mean(D, axis=1), ref=np.max)
    
    # 设定能量阈值（比如高于最大值 30dB 的频段才算有效鸟鸣，滤除底噪）
    valid_indices = np.where(power_db > (power_db.max() - 30))[0]
    if len(valid_indices) == 0:
        return None
        
    fmin = freqs[valid_indices].min()
    return fmin

print(f" BirdNET 使用位置：{LOCATION_NAME} -> ({LAT}, {LON})")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(" 正在加载模型...")
analyzer = Analyzer()
print(" 模型加载成功！\n")

audio_files = sorted(
    glob.glob(os.path.join(DATA_DIR, "*.mp3")) +
    glob.glob(os.path.join(DATA_DIR, "*.wav"))
)
print(f" 找到 {len(audio_files)} 个音频文件\n")

if not audio_files:
    print(" data 文件夹里没有音频。")

all_detailed_results = []  
sparrow_scores = []        

for i, audio_path in enumerate(audio_files, 1):
    file_name = os.path.basename(audio_path)
    file_time = parse_audio_date(audio_path)
    print(f"[{i}/{len(audio_files)}] 分析：{file_name}")
    
    try:
        rec = Recording(
            analyzer, audio_path, lat=LAT, lon=LON,
            date=file_time, min_conf=MIN_CONF
        )
        rec.analyze()

        if not rec.detections:
            print(f"    — 静音或无匹配声源")
            continue

        # 指标计算
        noise_duration = 0.0       
        sparrow_total_calls = 0    
        sparrow_high_conf = 0      
        
        #  新增：用来存本段音频中高置信度麻雀的频率
        sparrow_fmins = [] 
        
        # 如果发现了高置信度麻雀，需要重新加载一次音频数据来算频率
        # 为了避免重复加载，我们只在需要时加载
        need_audio_load = False
        for d in rec.detections:
            if d["common_name"] == SENTINEL_SPECIES and d["confidence"] >= SENTINEL_CONFIDENCE:
                need_audio_load = True
                break
                
        if need_audio_load:
            y, sr = librosa.load(audio_path, sr=None)

        for d in rec.detections:
            all_detailed_results.append({
                "audio_file": file_name,
                "common_name": d["common_name"],
                "scientific_name": d["scientific_name"],
                "start_time": round(d["start_time"], 2),
                "end_time": round(d["end_time"], 2),
                "confidence": round(d["confidence"], 4),
            })
            
            if d["common_name"] in NOISE_LABELS:
                noise_duration += (d["end_time"] - d["start_time"])
                
            if d["common_name"] == SENTINEL_SPECIES:
                sparrow_total_calls += 1
                if d["confidence"] >= SENTINEL_CONFIDENCE:
                    sparrow_high_conf += 1
                    
                    #  提取这一声麻雀叫的频率
                    if need_audio_load:
                        start_sample = int(d["start_time"] * sr)
                        end_sample = int(d["end_time"] * sr)
                        # 截取这段音频
                        chunk = y[start_sample:end_sample]
                        if len(chunk) > 0:
                            fmin_val = extract_fmin(chunk, sr)
                            if fmin_val:
                                sparrow_fmins.append(fmin_val)

        # 计算总时长
        try:
            total_duration = librosa.get_duration(path=audio_path)
            if total_duration <= 0:
                raise ValueError("音频时长必须大于零")
        except Exception as exc:
            print(f"     无法读取音频时长，按 60 秒计算：{exc}")
            total_duration = 60.0
        sane_proxy = round(noise_duration / total_duration, 4)
        
        #  计算麻雀主指标与辅指标
        if sparrow_total_calls > 0:
            base_score = (sparrow_high_conf / sparrow_total_calls) * 100
            noise_penalty = 1.0 - min(sane_proxy, 0.5) 
            sparrow_score = round(base_score * noise_penalty, 1)
            
            # 计算平均Fmin和偏音率
            avg_fmin = np.mean(sparrow_fmins) if sparrow_fmins else None
            fmin_shift = None
            if avg_fmin:
                # 偏音率 = (实测 - 基线) / 基线 * 100%
                fmin_shift = round(((avg_fmin - BASELINE_FMIN) / BASELINE_FMIN) * 100, 2)
            
            sparrow_scores.append({
                "time": file_time.strftime("%Y-%m-%d %H:%M:%S"),
                "audio_file": file_name,
                "sparrow_total_calls": sparrow_total_calls,
                "sparrow_high_conf_calls": sparrow_high_conf,
                "SANE_noise_level": sane_proxy,
                "sparrow_score": sparrow_score,
                #  新增两列辅证据
                "avg_fmin_hz": round(avg_fmin, 1) if avg_fmin else None,
                "fmin_shift_percent": fmin_shift
            })
            fmin_display = f"{avg_fmin:.1f}Hz" if avg_fmin is not None else "不可用"
            print(
                f"     麻雀: 高清晰度{sparrow_high_conf}次, "
                f"评分:{sparrow_score}, Fmin:{fmin_display}, 偏移:{fmin_shift}%"
            )

    except Exception as e:
        print(f"     错误：{e}")

# ===== 保存表格 =====
detections_path = os.path.join(OUTPUT_DIR, DETECTIONS_FILENAME)
pd.DataFrame(all_detailed_results, columns=DETECTIONS_COLUMNS).to_csv(
    detections_path, index=False, encoding="utf-8-sig")
print(f" 鸟类识别表已保存到：{os.path.abspath(detections_path)}")

df_sparrow = pd.DataFrame(sparrow_scores, columns=SPARROW_SCORE_COLUMNS)
if not df_sparrow.empty:
    df_sparrow = df_sparrow.sort_values(by="time")
sparrow_path = os.path.join(OUTPUT_DIR, SPARROW_SCORE_FILENAME)
df_sparrow.to_csv(sparrow_path, index=False, encoding="utf-8-sig")
print(f" 麻雀通讯双证据表已保存到：{os.path.abspath(sparrow_path)}")

print("\n 全部处理完成！")