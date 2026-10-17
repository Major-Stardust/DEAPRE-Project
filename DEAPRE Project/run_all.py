from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
ANALYSIS_SCRIPTS = [
    "birdnet.py",
    "soundscape.py",
    "weather_api.py",
    "CMEHI_Calculator.py",
    "plot_report.py",
]


def run_script(script_name: str) -> int:
    script_path = BASE_DIR / script_name
    if not script_path.is_file():
        print(f"找不到脚本：{script_path}", flush=True)
        return 1

    print(f"\n=== 运行 {script_name} ===", flush=True)
    return subprocess.run([PYTHON, str(script_path)], cwd=BASE_DIR).returncode


def run_analysis_pipeline() -> int:
    print("\n========== 开始执行分析流水线 ==========", flush=True)
    for script_name in ANALYSIS_SCRIPTS:
        code = run_script(script_name)
        if code != 0:
            print(f" {script_name} 执行失败，退出码：{code}", flush=True)
            return code
    print("========== 分析流水线执行完毕 ==========", flush=True)
    return 0


def start_background_script(script_name: str) -> subprocess.Popen:
    script_path = BASE_DIR / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"找不到脚本：{script_path}")

    log_dir = BASE_DIR / "results" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{script_name}.log"

    print(f"后台启动 {script_name}", flush=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        return subprocess.Popen(
            [PYTHON, str(script_path)],
            cwd=BASE_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )


def collect_pm_data() -> int:
    script_path = BASE_DIR / "air_sensor.py"
    if not script_path.is_file():
        print(f"找不到脚本：{script_path}", flush=True)
        return 1

    log_dir = BASE_DIR / "results" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "air_sensor.py.log"

    print("\n=== 开始每小时 PM 传感器采集 ===", flush=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        result = subprocess.run(
            [
                PYTHON,
                str(script_path),
                "--duration",
                "60",
                "--warmup",
                "30",
            ],
            cwd=BASE_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    if result.returncode != 0:
        print(
            f" air_sensor.py 采集失败，退出码：{result.returncode}；"
            f"详见 {log_path}",
            flush=True,
        )
    else:
        print(f" PM 传感器采集完成，日志：{log_path}", flush=True)
    return result.returncode


def stop_background_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def next_analysis_time(now: datetime, analysis_time: datetime_time) -> datetime:
    next_run = datetime.combine(now.date(), analysis_time)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


def run_edge_node(analysis_time: datetime_time, record: bool, air: bool) -> int:
    processes: list[tuple[str, subprocess.Popen]] = []
    last_pm_collection = datetime.min
    try:
        if record:
            processes.append(("recorder.py", start_background_script("recorder.py")))

        code = run_analysis_pipeline()
        if code != 0:
            return code

        next_run = next_analysis_time(datetime.now(), analysis_time)
        print(
            f"边缘节点已启动，后台服务运行中；下次分析时间："
            f"{next_run:%Y-%m-%d %H:%M}",
            flush=True,
        )
        while True:
            now = datetime.now()
            for script_name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(
                        f"后台服务 {script_name} 意外退出，退出码：{return_code}",
                        flush=True,
                    )
                    return return_code or 1

            if air and (now - last_pm_collection).total_seconds() > 3600:
                last_pm_collection = now
                collection_code = collect_pm_data()
                if collection_code != 0:
                    print(
                        "⚠️ 本次 PM 采集失败；系统将在一小时后重试。",
                        flush=True,
                    )

            if now >= next_run:
                code = run_analysis_pipeline()
                if code != 0:
                    return code
                next_run = next_analysis_time(datetime.now(), analysis_time)
                print(
                    f"下次分析时间：{next_run:%Y-%m-%d %H:%M}",
                    flush=True,
                )
            else:
                time.sleep(min((next_run - now).total_seconds(), 1.0))
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭后台服务...", flush=True)
        return 0
    except OSError as exc:
        print(f"无法启动或管理后台服务：{exc}", flush=True)
        return 1
    finally:
        for _, process in reversed(processes):
            stop_background_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(description="DEAPRE 一键执行与边缘节点调度")
    parser.add_argument(
        "--record",
        action="store_true",
        help="后台持续录音，并启动每日分析调度",
    )
    parser.add_argument(
        "--air",
        action="store_true",
        help="启动每小时一次的空气传感器采样，并启用每日分析调度",
    )
    parser.add_argument(
        "--weather-only",
        action="store_true",
        help="仅执行天气模块",
    )
    parser.add_argument(
        "--analysis-time",
        default="20:30",
        help="边缘节点每日分析时间（HH:MM，默认 20:30）",
    )
    args = parser.parse_args()

    if args.weather_only:
        if args.record or args.air:
            parser.error("--weather-only 不能与 --record 或 --air 同时使用")
        return run_script("weather_api.py")

    if not args.record and not args.air:
        return run_analysis_pipeline()

    try:
        analysis_time = datetime.strptime(args.analysis_time, "%H:%M").time()
    except ValueError:
        parser.error("--analysis-time 必须使用 24 小时制 HH:MM 格式")

    return run_edge_node(analysis_time, record=args.record, air=args.air)


if __name__ == "__main__":
    raise SystemExit(main())
