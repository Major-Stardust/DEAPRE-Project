import sys
print(">> 脚本启动", flush=True)
print(">> Python 路径:", sys.executable, flush=True)

try:
    import serial
    print(">> pyserial 版本:", serial.__version__, flush=True)
except Exception as e:
    print(">>  导入 serial 失败:", repr(e), flush=True)
    sys.exit(1)

try:
    from serial.tools import list_ports
    print(">> list_ports 导入成功", flush=True)
    ports = list(list_ports.comports())
    print(f">> 找到 {len(ports)} 个串口", flush=True)

    if not ports:
        print(">>  一个串口都没找到！", flush=True)
    for p in ports:
        print(f"     {p.device} | {p.description} | HWID={p.hwid}", flush=True)

except Exception as e:
    import traceback
    print(">>  枚举串口时出错:", repr(e), flush=True)
    traceback.print_exc()