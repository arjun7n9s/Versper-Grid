from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ─── Isolation Forest — fit once at import time on synthetic "normal" data ──
_iso_forest = None

def _get_iso_forest():
    global _iso_forest
    if _iso_forest is not None:
        return _iso_forest
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        rng = np.random.default_rng(42)
        # Synthetic normal: ppm 2-8, rise rate -0.5 to 0.5, wind 1-4 m/s
        normal = np.column_stack([
            rng.uniform(2.0, 8.0, 400),    # gas_ppm
            rng.uniform(-0.5, 0.5, 400),   # rise_rate
            rng.uniform(1.0, 4.0, 400),    # wind_speed
        ])
        _iso_forest = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        _iso_forest.fit(normal)
        logger.info("IsolationForest fitted on 400 synthetic normal sensor samples.")
    except ImportError:
        logger.warning("scikit-learn not installed — anomaly detection disabled.")
        _iso_forest = None
    return _iso_forest


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
    anomaly_score: float = 0.0   # IsolationForest score; negative = more anomalous
    is_anomalous: bool = False


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_exclusion_zone(
    source_x: float,
    source_y: float,
    wind_speed_mps: float,
    wind_direction_deg: float,
    peak_ppm: float,
    threshold_ppm: float = 15.0,
) -> dict:
    """Compute a simplified PAC-style downwind exclusion cone.

    Returns a dict with:
      - radius: initial exclusion radius around source (0-100 grid units)
      - cone_points: list of [x,y] defining the downwind polygon
      - severity: 'critical' | 'elevated' | 'watch'
    """
    import math

    # Exclusion radius scales with peak ppm above threshold
    ratio = max(0, (peak_ppm - threshold_ppm) / threshold_ppm)
    radius = min(30.0, 8.0 + ratio * 14.0)

    severity = "critical" if peak_ppm >= 25 else "elevated" if peak_ppm >= threshold_ppm else "watch"

    # Wind direction: meteorological convention — direction wind is coming FROM
    # Convert to math angle (direction wind blows TOWARD)
    wind_rad = math.radians((270 - wind_direction_deg) % 360)
    dx = math.cos(wind_rad)
    dy = math.sin(wind_rad)  # y increases downward in SVG

    # Cone length scales with wind speed
    cone_length = min(45.0, 12.0 + wind_speed_mps * 3.5)
    half_angle = math.radians(30)  # 60° total spread

    tip_x = source_x
    tip_y = source_y
    left_x  = source_x + cone_length * math.cos(wind_rad + half_angle)
    left_y  = source_y - cone_length * math.sin(wind_rad + half_angle)
    right_x = source_x + cone_length * math.cos(wind_rad - half_angle)
    right_y = source_y - cone_length * math.sin(wind_rad - half_angle)

    return {
        "radius": round(radius, 1),
        "severity": severity,
        "wind_direction_deg": wind_direction_deg,
        "wind_speed_mps": wind_speed_mps,
        "cone_points": [
            [round(tip_x, 1),   round(tip_y, 1)],
            [round(left_x, 1),  round(left_y, 1)],
            [round(right_x, 1), round(right_y, 1)],
        ],
    }


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

    # ── Isolation Forest anomaly detection ──
    anomaly_score = 0.0
    is_anomalous = False
    clf = _get_iso_forest()
    if clf is not None:
        try:
            import numpy as np
            feat = np.array([[latest_ppm, rise_rate, avg_wind_speed or 2.0]])
            anomaly_score = float(clf.score_samples(feat)[0])  # negative = anomalous
            is_anomalous = bool(clf.predict(feat)[0] == -1)
            if is_anomalous:
                # Boost confidence — model has flagged an out-of-distribution reading
                confidence = min(0.97, confidence + 0.08)
                logger.info("Anomaly detected: score=%.3f ppm=%.1f rise=%.2f",
                            anomaly_score, latest_ppm, rise_rate)
        except Exception as exc:
            logger.warning("IsolationForest inference failed: %s", exc)

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
        anomaly_score=round(anomaly_score, 4),
        is_anomalous=is_anomalous,
    )
