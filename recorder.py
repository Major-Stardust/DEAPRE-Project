import argparse
import os
import time
from datetime import datetime

import sounddevice as sd
import soundfile as sf

from config import MIC_DEVICE

# ===== 配置 =====
DATA_DIR = "data"              # 录音保存文件夹
SEGMENT_SECONDS = 60           # 每段录音时长（秒）
SAMPLE_RATE = 48000            # 采样率，BirdNET 推荐 48kHz
CHANNELS = 1                   # 单声道，野外监测够用


def record_forever(start_hour=None, end_hour=None, max_segments=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f" 使用麦克风：{sd.query_devices(MIC_DEVICE)['name']}")
    print(f"  每段录音：{SEGMENT_SECONDS} 秒")
    print(f" 保存位置：{os.path.abspath(DATA_DIR)}")
    if start_hour is not None and end_hour is not None:
        print(f" 录制时段：{start_hour}:00 - {end_hour}:00")
    print("  按 Ctrl + C 停止录音\n")

    count = 0
    while True:
        if start_hour is not None and end_hour is not None:
            now_hour = datetime.now().hour
            if start_hour <= end_hour:
                in_window = start_hour <= now_hour < end_hour
            else:
                in_window = now_hour >= start_hour or now_hour < end_hour
            if not in_window:
                print(f"  当前 {now_hour} 点不在录制时段，等待 60 秒...")
                time.sleep(60)
                continue

        if max_segments is not None and count >= max_segments:
            print(f"\n  已录满 {max_segments} 段，自动停止。")
            break

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(DATA_DIR, f"rec_{timestamp}.wav")

        print(f"  正在录制：{os.path.basename(filename)} ...", end="", flush=True)
        audio = sd.rec(
            int(SEGMENT_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=MIC_DEVICE,
        )
        sd.wait()
        sf.write(filename, audio, SAMPLE_RATE)
        print(" right")
        count += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DEAPRE 录音脚本")
    parser.add_argument("--start-hour", type=int, default=None, help="开始小时（0-23）")
    parser.add_argument("--end-hour", type=int, default=None, help="结束小时（0-23）")
    parser.add_argument("--max-segments", type=int, default=None, help="最多录几段")
    args = parser.parse_args()

    try:
        record_forever(
            start_hour=args.start_hour,
            end_hour=args.end_hour,
            max_segments=args.max_segments,
        )
    except KeyboardInterrupt:
        print("\n  录音已停止。")