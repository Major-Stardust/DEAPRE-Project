# DEAPRE Project

DEAPRE 是一个基于环境声学、鸟类识别、空气质量和天气信息的综合生态健康评估项目，用于联合计算 CMEHI 指标。

## 1. 项目简介

本项目整合了以下模块：

- BirdNET 鸟类识别：识别音频中的鸟类并生成按日期命名的 detections_YYYYMMDD.csv
- 音景分析：对音频计算声景分值并生成 soundscape_scores.csv
- 空气质量采集：读取 PMS7003 传感器数据并保存 air_quality.csv
- 天气获取：调用 Open-Meteo 获取实时天气与空气状态
- CMEHI 计算：汇总声景、鸟类、空气和晨鸣修正，计算综合指数

## 2. 环境准备

在项目根目录执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

也可以复制一份环境变量模板：

```bash
copy .env.example .env
```

可用的关键变量包括：

- DEAPRE_AIR_PORT
- DEAPRE_MIC_DEVICE
- DEAPRE_LAT / DEAPRE_LON

## 3. 运行顺序

推荐直接运行：

```bash
python run_all.py
```

默认模式会依次运行 `birdnet.py`、声景分析、天气获取、CMEHI 计算和绘图。要在设备上持续采集并每天 20:30 分析，可运行：

```bash
python run_all.py --record --air
```

`--record` 在后台持续录音，`--air` 每小时启动一次空气传感器采样（预热 30 秒、采集 60 秒）；启动后先执行一次分析流水线，此后每天在 `20:30` 执行。可用 `--analysis-time HH:MM` 修改每日分析时间，按 Ctrl+C 会停止录音进程。后台输出保存在 `results/logs/`。仅需持续录音时使用 `python run_all.py --record`。

或者按模块顺序执行：

```bash
python recorder.py
python birdnet.py
python soundscape.py
python weather_api.py
python CMEHI_Calculator.py
python plot_report.py
```

## 4. 硬件依赖

- 麦克风：用于录制环境音频
- PMS7003 空气传感器：通过串口读取 PM2.5 等数据
- CH340 串口转换器：用于连接 PMS7003

## 5. 光污染双指标说明

为了提高晨鸣和夜鸣的生物学解释力，项目新增了双指标方案：

1. 晨鸣提前量：比较最早鸟鸣时间与天文晨光始，衡量光污染是否让鸟类提前醒来。
2. 夜鸣延迟量：比较最晚鸟鸣时间与民用暮光终，衡量光污染是否让鸟类延迟入睡。

这两个指标均通过 `astral` 天文库精确计算，避免传统经验公式带来的 1 小时误差。最终融合成 `S_光污染`，并按 20% 权重纳入 CMEHI。

示例录音方式：

```bash
python recorder.py --start-hour 4 --end-hour 8 --max-segments 240
python recorder.py --start-hour 18 --end-hour 23 --max-segments 300
```

## 6. 数据源说明

- 天气和空气条件来自 Open-Meteo API
- 位置解析优先级：IP 定位 > 手动坐标 > 地名解析 > 默认上海
- 相关环境变量：
  - DEAPRE_LOCATION
  - DEAPRE_LAT
  - DEAPRE_LON

## 7. 常见问题

- 若天气接口无法访问，请确认网络代理已关闭
- 若串口设备无法开启，请检查 COM 口和波特率
- 若定位异常，可设置环境变量或手动指定地名

## 8. 输出说明

- results/detections_YYYYMMDD.csv：按运行日期保存的鸟类识别结果
- results/sparrow_score_YYYYMMDD.csv：按运行日期保存的麻雀通讯干扰评分
- results/soundscape_scores.csv：声景分数
- results/air_quality.csv：空气质量数据
- results/CMEHI_Report.csv：综合指数结果
- results/figures/：可视化图表

## 9. 说明

项目中使用统一位置配置，避免各模块硬编码坐标造成结果不一致。
