from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Weighted contributions
CMEHI_WEIGHTS = {
    "soundscape": 0.25,
    "bird": 0.25,
    "communication": 0.20,
    "air": 0.15,
    "light": 0.15,
}

BIRD_COMPONENT_WEIGHTS = {
    "r": 0.4,
    "f": 0.3,
    "h": 0.3,
}

# 光污染融合（晨鸣 + 夜鸣）
CHORUS_FUSION = {"dawn": 0.5, "night": 0.5}
DAWN_ADVANCE_PENALTY = 1.5
NIGHT_DELAY_PENALTY = 1.5
DEFAULT_CHORUS_SCORE = 50.0

# Bird score normalization
R_BASELINE = 10.0
F_BASELINE = 50.0
MIN_CONFIDENCE = 0.4
MIN_RECORDS_FOR_BIRD_SCORE = 5

# Soundscape defaults
ACI_BASELINE = 100.0
NDSI_NORM_BASE = 1.0
SOUNDSCAPE_WEIGHTS = {
    "ndsi": 0.5,
    "aci": 0.3,
    "noise": -0.2,
}

# Hardware / environment defaults
AIR_SENSOR_PORT = os.getenv("DEAPRE_AIR_PORT", "COM3")
MIC_DEVICE = int(os.getenv("DEAPRE_MIC_DEVICE", "1"))

# File / output settings
RESULTS_DIR = "results"
DATA_DIR = "data"
