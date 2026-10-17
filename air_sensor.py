from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import serial

from config import AIR_SENSOR_PORT

BASE_DIR = Path(__file__).resolve().parent
PORT = AIR_SENSOR_PORT
BAUD = 9600
OUTPUT_FILE = BASE_DIR / "results" / "air_quality.csv"


def read_frame(ser):
    """阻塞读取一帧完整的 32 字节数据（自动寻找 42 4d 帧头）"""
    while True:
        b = ser.read(1)
        if not b:
            return None
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
    expected = sum(frame[:30]) & 0xFFFF
    actual = (frame[30] << 8) | frame[31]
    if expected != actual:
        return None

    def u16(i):
        return (frame[i] << 8) | frame[i + 1]

    return {
        "pm1_0_atm": u16(10),
        "pm2_5_atm": u16(12),
        "pm10_atm": u16(14),
        "pm1_0_std": u16(4),
        "pm2_5_std": u16(6),
        "pm10_std": u16(8),
        "cnt_0_3um": u16(16),
        "cnt_0_5um": u16(18),
        "cnt_1_0um": u16(20),
        "cnt_2_5um": u16(22),
        "cnt_5_0um": u16(24),
        "cnt_10um": u16(26),
    }


def main():
    parser = argparse.ArgumentParser(description="PMS7003 空气质量采样脚本")
    parser.add_argument("--duration", type=float, default=None, help="采样持续时间（秒），默认无限循环")
    parser.add_argument("--port", default=PORT, help=f"串口号，默认 {PORT}")
    parser.add_argument("--baud", type=int, default=BAUD, help="串口波特率，默认 9600")
    parser.add_argument("--warmup", type=float, default=0, help="传感器预热等待时间（秒）")
    args = parser.parse_args()

    output_dir = OUTPUT_FILE.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_FILE.exists()

    print(f"正在打开串口 {args.port} @ {args.baud} ...", flush=True)
    ser = serial.Serial(args.port, args.baud, timeout=2)
    time.sleep(0.5)
    if args.warmup > 0:
        print(f"正在预热传感器，等待 {args.warmup:g} 秒...", flush=True)
        time.sleep(args.warmup)
    start_time = time.time()

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "timestamp", "pm1_0_atm", "pm2_5_atm", "pm10_atm",
            "pm1_0_std", "pm2_5_std", "pm10_std",
            "cnt_0_3um", "cnt_0_5um", "cnt_1_0um",
            "cnt_2_5um", "cnt_5_0um", "cnt_10um",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        print(f" 结果将保存到：{OUTPUT_FILE.resolve()}")
        print("  按 Ctrl+C 停止\n")
        bad_frames = 0
        try:
            while True:
                if args.duration is not None and time.time() - start_time >= args.duration:
                    print(f"\n已达到采样时长 {args.duration} 秒，自动停止。", flush=True)
                    break

                frame = read_frame(ser)
                if frame is None:
                    continue
                data = parse_frame(frame)
                if data is None:
                    bad_frames += 1
                    continue

                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow({"timestamp": ts, **data})
                f.flush()

                print(
                    f"[{ts}]  PM1.0={data['pm1_0_atm']:>4}  "
                    f"PM2.5={data['pm2_5_atm']:>4}  "
                    f"PM10={data['pm10_atm']:>4}  ug/m3",
                    flush=True,
                )
        except KeyboardInterrupt:
            print(f"\n  已停止。共丢弃 {bad_frames} 个校验失败帧", flush=True)
        finally:
            try:
                sleep_cmd = bytes([0x42, 0x4D, 0xE4, 0x00, 0x00, 0x01, 0x73])
                ser.write(sleep_cmd)
                time.sleep(0.5)
                print("  已发送休眠指令，传感器已停止工作。", flush=True)
            except Exception as e:
                print(f"  发送传感器休眠指令失败：{e}", flush=True)
            finally:
                ser.close()


if __name__ == "__main__":
    main()