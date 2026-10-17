import glob
import os

import librosa
import numpy as np

from config import ACI_BASELINE, NDSI_NORM_BASE, SOUNDSCAPE_WEIGHTS

# ===== 配置 =====
DATA_DIR = "data"

def analyze_soundscape(audio_path):
    """计算单段音频的声景指数"""
    # 1. 加载音频
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    
    # 2. 计算能量谱图
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    
    # 3. 提取不同频段的能量
    # 人为噪声频段（1-2kHz）
    idx_noise = (freqs >= 1000) & (freqs < 2000)
    # 生物声频段（2-9kHz，鸟叫一般在这个范围）
    idx_bio = (freqs >= 2000) & (freqs < 9000)
    
    E_noise = np.sum(S[idx_noise, :])
    E_bio = np.sum(S[idx_bio, :])
    
    # 4. 计算 P_noise (人为噪声占比)
    total_energy = E_noise + E_bio
    P_noise = (E_noise / total_energy * 100) if total_energy > 0 else 50.0
    
    # 5. 计算 NDSI (归一化声景指数)
    # NDSI = (生物声 - 噪声) / (生物声 + 噪声)
    NDSI = (E_bio - E_noise) / (E_bio + E_noise) if (E_bio + E_noise) > 0 else 0
    NDSI_norm = (NDSI + 1) * 50 * NDSI_NORM_BASE
    
    # 6. 计算 ACI (声学复杂度指数) - 简化版
    # 使用频谱图的熵来衡量复杂度
    S_norm = S / (np.sum(S) + 1e-6)
    entropy = -np.sum(S_norm * np.log(S_norm + 1e-6))
    ACI_raw = np.exp(entropy)  # 转换为线性值
    ACI_norm = min(ACI_raw / ACI_BASELINE * 100, 100)
    
    # 7. 计算 S_声景
    s_soundscape = (
        SOUNDSCAPE_WEIGHTS["ndsi"] * NDSI_norm
        + SOUNDSCAPE_WEIGHTS["aci"] * ACI_norm
        + SOUNDSCAPE_WEIGHTS["noise"] * P_noise
    )
    s_soundscape = max(0, min(100, s_soundscape))
    
    return {
        "file": os.path.basename(audio_path),
        "NDSI": round(NDSI, 4),
        "NDSI_norm": round(NDSI_norm, 2),
        "ACI_raw": round(ACI_raw, 2),
        "ACI_norm": round(ACI_norm, 2),
        "P_noise": round(P_noise, 2),
        "S_声景": round(s_soundscape, 2)
    }

def main():
    audio_files = sorted(
        glob.glob(os.path.join(DATA_DIR, "*.wav")) +
        glob.glob(os.path.join(DATA_DIR, "*.mp3"))
    )
    
    if not audio_files:
        print(" data 文件夹里没有音频文件！")
        return
    
    print(f" 找到 {len(audio_files)} 个音频，开始声景分析...\n")
    results = []
    for f in audio_files:
        try:
            res = analyze_soundscape(f)
            results.append(res)
            print(f"[{res['file']}]")
            print(f"  NDSI={res['NDSI']} (归一化={res['NDSI_norm']})")
            print(f"  ACI={res['ACI_raw']} (归一化={res['ACI_norm']})")
            print(f"  人为噪声占比={res['P_noise']}%")
            print(f"   S_声景 得分: {res['S_声景']}/100\n")
        except Exception as e:
            print(f"   {os.path.basename(f)} 分析失败: {e}\n")
    
    if results:
        import pandas as pd
        os.makedirs("results", exist_ok=True)
        df = pd.DataFrame(results)
        out_path = "results/soundscape_scores.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f" 声景得分已保存至: {os.path.abspath(out_path)}")

if __name__ == "__main__":
    main()