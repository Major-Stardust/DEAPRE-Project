import serial
import time
import os
import csv
from datetime import datetime

# ===== 配置 =====
PORT = "COM3"                  # 刚确诊的端口
BAUD = 9600
OUTPUT_FILE = "results/air_quality.csv"

os.makedirs("results", exist_ok=True)

def read_frame(ser):
    """阻塞读取一帧完整的 32 字节数据（自动寻找 42 4d 帧头）"""
    while True:
        b = ser.read(1)
        if not b:
            continue
        if b == b"\x42":
            b2 = ser.read(1)
            if b2 == b"\x4d":
                rest = ser.read(30)
                if len(rest) == 30:
                    return b"\x42\x4d" + rest

def parse_frame(frame):
    """解析 32 字节数据帧，并校验和检查"""
    if len(frame) != 32:
        return None
    # 校验和 = 前 30 字节之和
    expected = sum(frame[:30]) & 0xFFFF
    actual = (frame[30] << 8) | frame[31]
    if expected != actual:
        return None

    def u16(i):
        return (frame[i] << 8) | frame[i + 1]

    return {
        "pm1_0_atm":  u16(10),  # 大气环境值（推荐）
        "pm2_5_atm":  u16(12),
        "pm10_atm":   u16(14),
        "pm1_0_std":  u16(4),   # 标准颗粒物值
        "pm2_5_std":  u16(6),
        "pm10_std":   u16(8),
        "cnt_0_3um":  u16(16),
        "cnt_0_5um":  u16(18),
        "cnt_1_0um":  u16(20),
        "cnt_2_5um":  u16(22),
        "cnt_5_0um":  u16(24),
        "cnt_10um":   u16(26),
    }

def main():
    print(f"🔌 正在打开串口 {PORT} @ {BAUD} ...", flush=True)
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(0.5)

    file_exists = os.path.exists(OUTPUT_FILE)
    f = open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig")
    fieldnames = ["timestamp", "pm1_0_atm", "pm2_5_atm", "pm10_atm",
                  "pm1_0_std", "pm2_5_std", "pm10_std",
                  "cnt_0_3um", "cnt_0_5um", "cnt_1_0um",
                  "cnt_2_5um", "cnt_5_0um", "cnt_10um"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if not file_exists:
        writer.writeheader()

    print(f" 结果将保存到：{os.path.abspath(OUTPUT_FILE)}")
    print("  按 Ctrl+C 停止\n")

    bad_frames = 0
    try:
        while True:
            frame = read_frame(ser)
            data = parse_frame(frame)
            if data is None:
                bad_frames += 1
                continue

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow({"timestamp": ts, **data})
            f.flush()  # 立即写入硬盘

            print(f"[{ts}]  PM1.0={data['pm1_0_atm']:>4}  "
                  f"PM2.5={data['pm2_5_atm']:>4}  "
                  f"PM10={data['pm10_atm']:>4}  μg/m³", flush=True)

    except KeyboardInterrupt:
        print(f"\n  已停止。共丢弃 {bad_frames} 个校验失败帧", flush=True)
    finally:
        f.close()
        ser.close()

if __name__ == "__main__":
    main()