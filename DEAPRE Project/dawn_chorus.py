from __future__ import annotations

from chorus_analysis import (
    CHORUS_FUSION,
    DAWN_ADVANCE_PENALTY,
    DEFAULT_CHORUS_SCORE,
    NIGHT_DELAY_PENALTY,
    calculate_chorus_scores,
    get_sun_times,
    parse_audio_time,
)


def calculate_dawn_correction(detections_path):
    result = calculate_chorus_scores(detections_path)
    return {
        "earliest_bird_time": None,
        "dawn_gap_hours": None,
        "S_晨鸣": result.get("S_晨鸣", DEFAULT_CHORUS_SCORE),
        "S_夜鸣": result.get("S_夜鸣", DEFAULT_CHORUS_SCORE),
        "S_光污染": result.get("S_光污染", DEFAULT_CHORUS_SCORE),
    }


__all__ = [
    "calculate_dawn_correction",
    "calculate_chorus_scores",
    "get_sun_times",
    "parse_audio_time",
    "CHORUS_FUSION",
    "DAWN_ADVANCE_PENALTY",
    "NIGHT_DELAY_PENALTY",
    "DEFAULT_CHORUS_SCORE",
]
