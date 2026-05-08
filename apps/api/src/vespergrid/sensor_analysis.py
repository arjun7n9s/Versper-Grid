from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SensorAnalysis:
    source_uuid: str
    latest_ppm: float
    peak_ppm: float
    rise_rate_ppm_per_min: float
    threshold_crossings: int
    toxicity_band: str
    wind_speed_mps: float | None
    wind_direction_deg: float | None
    confidence: float
    summary: str
    recommendation: str


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_sensor_trace(samples: list[dict[str, Any]], threshold_ppm: float = 15.0) -> SensorAnalysis | None:
    readings: list[tuple[float, float]] = []
    wind_speeds: list[float] = []
    wind_dirs: list[float] = []

    for idx, sample in enumerate(samples):
        ppm = _num(sample.get("gas_ppm", sample.get("ppm", sample.get("value"))))
        if ppm is None:
            continue
        ts = _num(sample.get("ts", sample.get("timestamp", idx)))
        readings.append((float(ts if ts is not None else idx), ppm))
        speed = _num(sample.get("wind_speed_mps", sample.get("speed_mps")))
        direction = _num(sample.get("wind_direction_deg", sample.get("direction_deg")))
        if speed is not None:
            wind_speeds.append(speed)
        if direction is not None:
            wind_dirs.append(direction)

    if not readings:
        return None

    readings.sort(key=lambda x: x[0])
    latest_ppm = readings[-1][1]
    peak_ppm = max(ppm for _, ppm in readings)
    threshold_crossings = sum(1 for _, ppm in readings if ppm >= threshold_ppm)

    start_ts, start_ppm = readings[0]
    end_ts, end_ppm = readings[-1]
    elapsed_min = max((end_ts - start_ts) / 60.0, 1 / 60)
    rise_rate = (end_ppm - start_ppm) / elapsed_min

    if peak_ppm >= 25:
        band = "critical"
    elif peak_ppm >= threshold_ppm:
        band = "elevated"
    elif peak_ppm >= 8:
        band = "watch"
    else:
        band = "nominal"

    avg_wind_speed = sum(wind_speeds) / len(wind_speeds) if wind_speeds else None
    avg_wind_dir = sum(wind_dirs) / len(wind_dirs) if wind_dirs else None
    confidence = min(0.94, 0.58 + min(len(readings), 30) * 0.012 + threshold_crossings * 0.015)

    if band == "critical":
        recommendation = "Evacuate downwind workspace and isolate ignition sources near the leak perimeter."
    elif band == "elevated":
        recommendation = "Dispatch supervisors for confirmation and hold non-essential movement through the drift corridor."
    elif band == "watch":
        recommendation = "Keep the sensor under watch and rerun response synthesis on the next trace update."
    else:
        recommendation = "No gas threshold breach detected; continue monitoring."

    wind_text = ""
    if avg_wind_speed is not None and avg_wind_dir is not None:
        wind_text = f" Wind averages {avg_wind_speed:.1f} m/s at {avg_wind_dir:.0f} degrees."

    summary = (
        f"Gas trace peak {peak_ppm:.1f} ppm, latest {latest_ppm:.1f} ppm, "
        f"rise rate {rise_rate:.1f} ppm/min, band {band}."
        f"{wind_text}"
    )

    return SensorAnalysis(
        source_uuid="SRC-SEN-LIVE",
        latest_ppm=round(latest_ppm, 2),
        peak_ppm=round(peak_ppm, 2),
        rise_rate_ppm_per_min=round(rise_rate, 2),
        threshold_crossings=threshold_crossings,
        toxicity_band=band,
        wind_speed_mps=round(avg_wind_speed, 2) if avg_wind_speed is not None else None,
        wind_direction_deg=round(avg_wind_dir, 1) if avg_wind_dir is not None else None,
        confidence=round(confidence, 3),
        summary=summary,
        recommendation=recommendation,
    )
