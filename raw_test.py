import serial
import time

PORT = "COM3"      # 已确诊是 COM3
BAUD = 9600

print("正在打开串口 COM3 ...", flush=True)
ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(0.5)
print("串口已打开！开始读取数据 (Ctrl+C 停止)...\n", flush=True)

try:
    while True:
        data = ser.read(32)
        if data:
            print(data.hex(" "), flush=True)
except KeyboardInterrupt:
    ser.close()
    print("\n已停止", flush=True)