"""Generate all VesperGrid demo assets procedurally.

Run: `python scripts/generate_assets.py`

Outputs:
- apps/console/public/assets/vesper-field-map.png (operational twin background)
- apps/console/public/assets/drone_keyframe_src_img_1042.png
- apps/console/public/assets/cctv_gate4_src_vid_2217.png
- apps/console/public/assets/wind_sensor_src_sen_0924.png
- demo/sector4/<same images> (mirrored for the evidence pack)
- demo/sector4/operator_transcript_src_txt_7781.txt
- demo/sector4/evidence_pack.json
- demo/sector4/vlm_output_sample.json
- demo/sector4/audit_log_sample.json
- demo/sector4/simulation_replay_sample.json

All assets are synthetic and license-clean. The script is deterministic
(seeded RNG) so re-runs produce byte-stable images for git diffs.
"""
from __future__ import annotations

import json
import math
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CONSOLE_ASSETS = ROOT / "apps" / "console" / "public" / "assets"
DEMO_DIR = ROOT / "demo" / "sector4"

# ---- Palette ---------------------------------------------------------------
BG_DEEP = (12, 15, 13)
BG_SLATE = (24, 30, 34)
GRID = (60, 90, 110)
ROAD = (52, 60, 65)
LANE = (78, 88, 92)
CONTAINER_A = (54, 70, 80)
CONTAINER_B = (40, 56, 66)
CONTAINER_C = (70, 50, 42)
TEXT_DIM = (140, 156, 168)
TEXT_BRIGHT = (220, 230, 238)
SIGNAL_BLUE = (134, 215, 255)
HEAT_ORANGE = (255, 112, 72)
WARN_AMBER = (255, 193, 95)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Pillow can usually find a monospaced system font; fall back to default."""
    candidates = [
        "consola.ttf",  # Windows Consolas
        "DejaVuSansMono.ttf",
        "Menlo.ttc",
        "Arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _ensure_dirs() -> None:
    CONSOLE_ASSETS.mkdir(parents=True, exist_ok=True)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)


# ---- Field map -------------------------------------------------------------
def make_field_map(out: Path, w: int = 1600, h: int = 900) -> None:
    rng = random.Random(20260508)
    img = Image.new("RGB", (w, h), BG_DEEP)
    d = ImageDraw.Draw(img, "RGBA")

    # Subtle noise texture
    for _ in range(2400):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        a = rng.randint(8, 22)
        d.point((x, y), fill=(180, 200, 215, a))

    # Faint grid (every 80 px)
    for x in range(0, w, 80):
        d.line([(x, 0), (x, h)], fill=GRID + (90,), width=1)
    for y in range(0, h, 80):
        d.line([(0, y), (w, y)], fill=GRID + (90,), width=1)

    # Perimeter fence
    d.rectangle([(40, 40), (w - 40, h - 40)], outline=(80, 110, 130, 180), width=2)

    # Roads (horizontal + vertical service roads)
    for y in (210, 470, 720):
        d.rectangle([(60, y - 18), (w - 60, y + 18)], fill=ROAD)
    for x in (320, 760, 1200):
        d.rectangle([(x - 14, 60), (x + 14, h - 60)], fill=ROAD)

    # Container blocks (sectors)
    sectors = [
        ("SECTOR 1", 90, 250, 280, 440, CONTAINER_B),
        ("SECTOR 2", 370, 250, 700, 440, CONTAINER_A),
        ("SECTOR 3", 810, 250, 1140, 440, CONTAINER_B),
        ("SECTOR 4", 1240, 250, 1530, 440, CONTAINER_C),  # the incident
        ("STAGING",  90, 510, 700, 700, CONTAINER_A),
        ("FUEL ADJ", 810, 510, 1140, 700, CONTAINER_B),
        ("WAREHOUSE", 1240, 510, 1530, 700, CONTAINER_A),
    ]
    for label, x0, y0, x1, y1, color in sectors:
        # individual containers (rows of slim rectangles)
        rows = 5
        cols = max(4, (x1 - x0) // 50)
        cw = (x1 - x0) / cols
        rh = (y1 - y0) / rows
        for r in range(rows):
            for c in range(cols):
                cx0 = int(x0 + c * cw + 4)
                cy0 = int(y0 + r * rh + 4)
                cx1 = int(x0 + (c + 1) * cw - 4)
                cy1 = int(y0 + (r + 1) * rh - 4)
                shade = tuple(max(0, min(255, ch + rng.randint(-12, 12))) for ch in color)
                d.rectangle([(cx0, cy0), (cx1, cy1)], fill=shade)
        # sector label
        d.text((x0 + 6, y0 - 22), label, fill=TEXT_DIM, font=_font(14))

    # Gate 4 (left edge of Sector 4) and Junction E (right side)
    gate4 = (1240, 380)
    junction_e = (1500, 220)
    d.rectangle([(gate4[0] - 18, gate4[1] - 28), (gate4[0] + 18, gate4[1] + 28)],
                outline=WARN_AMBER + (220,), width=2)
    d.text((gate4[0] - 24, gate4[1] - 50), "GATE 4", fill=WARN_AMBER, font=_font(13))

    d.ellipse([(junction_e[0] - 10, junction_e[1] - 10),
               (junction_e[0] + 10, junction_e[1] + 10)],
              outline=SIGNAL_BLUE + (220,), width=2)
    d.text((junction_e[0] - 30, junction_e[1] - 30), "JUNCTION E",
           fill=SIGNAL_BLUE, font=_font(13))

    # Blocked lane (red dashed) near Gate 4
    for i in range(0, 200, 14):
        d.line([(1230 - i, 720 + i // 4), (1230 - i - 8, 720 + (i + 8) // 4)],
               fill=HEAT_ORANGE + (200,), width=3)
    d.text((1040, 740), "BLOCKED SERVICE LANE", fill=HEAT_ORANGE, font=_font(12))

    # Recommended route (blue dashed) toward Junction E
    pts = [(1240, 380), (1320, 320), (1420, 260), (1500, 220)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = 8
        for s in range(0, steps, 2):
            ax = x0 + (x1 - x0) * s / steps
            ay = y0 + (y1 - y0) * s / steps
            bx = x0 + (x1 - x0) * (s + 1) / steps
            by = y0 + (y1 - y0) * (s + 1) / steps
            d.line([(ax, ay), (bx, by)], fill=SIGNAL_BLUE + (220,), width=3)

    # Vapor drift glow near Sector 4
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = 1380, 320
    for r, a in [(220, 30), (170, 50), (120, 75), (80, 110)]:
        gd.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                   fill=HEAT_ORANGE + (a,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=22))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # Compass + scale bar
    d.rectangle([(60, h - 100), (260, h - 60)], fill=(0, 0, 0, 160),
                outline=(120, 140, 150, 200))
    d.text((72, h - 92), "N \u2191  100 m  \u25A1\u25A1\u25A1\u25A1",
           fill=TEXT_DIM, font=_font(13))

    # Title overlay
    d.text((60, 56), "VESPERGRID  /  OPERATIONAL TWIN",
           fill=TEXT_BRIGHT, font=_font(20))
    d.text((60, 86), "SECTOR 4  /  FICTIONAL PORT LOGISTICS CORRIDOR",
           fill=TEXT_DIM, font=_font(13))

    img.save(out, "PNG", optimize=True)


# ---- Drone keyframe --------------------------------------------------------
def make_drone_keyframe(out: Path, w: int = 1280, h: int = 720) -> None:
    rng = random.Random(1042)
    img = Image.new("RGB", (w, h), (16, 18, 20))
    d = ImageDraw.Draw(img, "RGBA")

    # Stylized aerial container yard (top-down with slight oblique)
    for _ in range(1800):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        d.point((x, y), fill=(140, 160, 175, rng.randint(8, 18)))

    # Service road
    d.polygon([(0, 540), (w, 460), (w, 520), (0, 600)], fill=(46, 52, 56))

    # Container stacks (perspective)
    rng2 = random.Random(2026)
    for i in range(7):
        x0 = 80 + i * 160
        for j in range(4):
            top_w = 110
            x = x0 + j * 4
            y = 200 + j * 28
            color = rng2.choice([(58, 72, 80), (84, 60, 50), (52, 64, 70), (96, 70, 56)])
            d.rectangle([(x, y), (x + top_w, y + 80)], fill=color, outline=(20, 24, 28))

    # Suspect stack with thermal/vapor anomaly (right-of-center)
    anomaly_x, anomaly_y = 880, 280
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r, a in [(180, 30), (130, 55), (80, 90), (40, 130)]:
        gd.ellipse([(anomaly_x - r, anomaly_y - r),
                    (anomaly_x + r, anomaly_y + r)],
                   fill=HEAT_ORANGE + (a,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")

    # Vapor wisps (light streaks)
    for k in range(6):
        sx = anomaly_x - 40 + k * 14
        sy = anomaly_y - 60 - k * 6
        d.line([(sx, sy), (sx + 80, sy - 30)],
               fill=(220, 230, 240, 80), width=2)

    # Bounding hint
    d.rectangle([(anomaly_x - 95, anomaly_y - 70),
                 (anomaly_x + 95, anomaly_y + 70)],
                outline=HEAT_ORANGE + (220,), width=2)

    # HUD overlays
    d.rectangle([(20, 20), (320, 70)], fill=(0, 0, 0, 160))
    d.text((30, 28), "DRONE / SECTOR 4 / FRAME 03",
           fill=TEXT_BRIGHT, font=_font(15))
    d.text((30, 50), "SRC-IMG-1042  T+18:06",
           fill=SIGNAL_BLUE, font=_font(13))

    d.rectangle([(w - 220, h - 50), (w - 20, h - 20)], fill=(0, 0, 0, 160))
    d.text((w - 210, h - 44), "ALT 38 m  / GIMBAL 32\u00b0",
           fill=TEXT_DIM, font=_font(12))

    img.save(out, "PNG", optimize=True)


# ---- CCTV gate 4 -----------------------------------------------------------
def make_cctv_gate4(out: Path, w: int = 1280, h: int = 720) -> None:
    rng = random.Random(2217)
    img = Image.new("RGB", (w, h), (18, 20, 22))
    d = ImageDraw.Draw(img, "RGBA")

    # Asphalt with perspective vanishing toward top-right
    d.polygon([(0, h), (w, h), (w * 0.78, 280), (w * 0.18, 280)],
              fill=(38, 42, 46))

    # Lane lines (perspective)
    for offset in (-0.32, -0.1, 0.12, 0.34):
        x_top = w * (0.5 + offset * 0.6)
        x_bot = w * (0.5 + offset * 1.6)
        d.line([(x_bot, h), (x_top, 290)],
               fill=(120, 130, 135, 180), width=2)

    # Containers/walls flanking the lane
    d.polygon([(0, 280), (w * 0.18, 280), (w * 0.05, h), (0, h)],
              fill=(48, 56, 62))
    d.polygon([(w, 280), (w * 0.78, 280), (w * 0.92, h), (w, h)],
              fill=(48, 56, 62))

    # Security gantry overhead
    d.rectangle([(180, 160), (w - 180, 200)], fill=(60, 68, 74))
    d.text((220, 168), "GATE 4 / EAST APPROACH",
           fill=TEXT_BRIGHT, font=_font(15))

    # Queued vehicles (silhouettes) blocking the lane
    truck_positions = [(620, 420, 180, 110), (560, 540, 220, 130), (700, 360, 140, 90)]
    for x, y, vw, vh in truck_positions:
        d.rectangle([(x, y), (x + vw, y + vh)], fill=(28, 32, 36),
                    outline=(70, 80, 86), width=2)
        d.rectangle([(x + 12, y + 8), (x + vw - 12, y + 22)],
                    fill=(80, 60, 40))  # cab tint

    # Red highlight rectangle around blocked area
    d.rectangle([(520, 340), (900, 690)],
                outline=HEAT_ORANGE + (220,), width=3)

    # Compression-noise + scanlines
    for y in range(0, h, 3):
        d.line([(0, y), (w, y)], fill=(0, 0, 0, 22), width=1)
    for _ in range(2000):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        d.point((x, y), fill=(200, 210, 220, rng.randint(8, 24)))

    # CCTV HUD
    d.rectangle([(20, 20), (360, 84)], fill=(0, 0, 0, 170))
    d.text((30, 28), "GATE 4 CCTV / CAM-04",
           fill=TEXT_BRIGHT, font=_font(15))
    d.text((30, 50), "SRC-VID-2217  00:18:21",
           fill=SIGNAL_BLUE, font=_font(13))

    d.rectangle([(w - 200, 20), (w - 20, 60)], fill=(0, 0, 0, 170))
    d.text((w - 192, 30), "REC \u25CF  720p",
           fill=HEAT_ORANGE, font=_font(13))

    img.save(out, "PNG", optimize=True)


# ---- Wind sensor strip -----------------------------------------------------
def make_wind_sensor(out: Path, w: int = 900, h: int = 280) -> None:
    rng = random.Random(924)
    img = Image.new("RGB", (w, h), (10, 12, 13))
    d = ImageDraw.Draw(img, "RGBA")

    # Border + title strip
    d.rectangle([(0, 0), (w - 1, h - 1)], outline=(70, 100, 120), width=2)
    d.rectangle([(0, 0), (w, 38)], fill=(20, 28, 34))
    d.text((14, 10), "WIND TELEMETRY  /  SRC-SEN-0924",
           fill=TEXT_BRIGHT, font=_font(14))
    d.text((w - 160, 12), "SECTOR 4 PERIMETER",
           fill=TEXT_DIM, font=_font(12))

    # Sparkline (simulated wind speed time-series)
    points = []
    base = 18
    for i in range(60):
        v = base + 3 * math.sin(i / 4.5) + rng.uniform(-1.2, 1.4) + (i / 30)
        points.append(v)
    # Plot in lower 60% of the strip
    plot_top = 80
    plot_bot = h - 50
    plot_left = 30
    plot_right = w - 220
    span = plot_right - plot_left
    vmin, vmax = min(points), max(points)
    norm = lambda v: plot_bot - (v - vmin) / (vmax - vmin + 1e-6) * (plot_bot - plot_top)
    coords = [(plot_left + i * span / (len(points) - 1), norm(v))
              for i, v in enumerate(points)]
    # axis
    d.line([(plot_left, plot_bot), (plot_right, plot_bot)],
           fill=(80, 100, 110), width=1)
    # filled area
    poly = [(plot_left, plot_bot)] + coords + [(plot_right, plot_bot)]
    d.polygon(poly, fill=SIGNAL_BLUE + (60,))
    # line
    for a, b in zip(coords, coords[1:]):
        d.line([a, b], fill=SIGNAL_BLUE, width=2)

    # Right-side readout panel
    panel_x = w - 200
    d.rectangle([(panel_x, 60), (w - 20, h - 30)],
                fill=(16, 22, 26), outline=(70, 100, 120))
    d.text((panel_x + 14, 72),  "SPEED",        fill=TEXT_DIM,    font=_font(11))
    d.text((panel_x + 14, 88),  "21 km/h",      fill=TEXT_BRIGHT, font=_font(22))
    d.text((panel_x + 14, 124), "DIRECTION",    fill=TEXT_DIM,    font=_font(11))
    d.text((panel_x + 14, 140), "NE  \u2197",   fill=WARN_AMBER,  font=_font(20))
    d.text((panel_x + 14, 174), "PRESSURE",     fill=TEXT_DIM,    font=_font(11))
    d.text((panel_x + 14, 190), "+14%",         fill=HEAT_ORANGE, font=_font(20))

    img.save(out, "PNG", optimize=True)


# ---- Static text + JSON assets --------------------------------------------
TRANSCRIPT = """[SRC-TXT-7781]
[00:18:06] Yard Ops: Sector 4 team reports solvent smell near polymer stack.
            Visual confirmation unclear.
[00:18:21] Safety Lead: Hydrant pressure on west line is unstable.
            Request tanker relay confirmation.
[00:18:39] Gate Control: Gate 4 route may be clear, but camera feed has not
            been checked.
[00:18:52] Yard Ops: Hold dispatch until route status is verified.
[00:19:08] Safety Lead: Wind has shifted NE, vapor drift now toward fuel-
            adjacent lane. Recommend extended perimeter.
"""

EVIDENCE_PACK = {
    "scenario_id": "sector4-solvent-containment",
    "title": "Sector 4 Solvent Containment",
    "location": "Synthetic Port Logistics Corridor (Chennai North reference)",
    "fictional": True,
    "sources": [
        {"source_uuid": "SRC-IMG-1042", "kind": "image",
         "path": "drone_keyframe_src_img_1042.png",
         "claim": "Thermal/vapor anomaly near container stack",
         "confidence": 0.89},
        {"source_uuid": "SRC-VID-2217", "kind": "video_keyframe",
         "path": "cctv_gate4_src_vid_2217.png",
         "claim": "Gate 4 service lane appears blocked",
         "confidence": 0.81},
        {"source_uuid": "SRC-TXT-7781", "kind": "transcript",
         "path": "operator_transcript_src_txt_7781.txt",
         "claim": "Hydrant pressure unstable; Gate 4 route uncertain",
         "confidence": 0.74},
        {"source_uuid": "SRC-SEN-0924", "kind": "sensor",
         "path": "wind_sensor_src_sen_0924.png",
         "claim": "Wind pushes vapor toward fuel-adjacent lane",
         "confidence": 0.93},
    ],
}

VLM_OUTPUT_SAMPLE = {
    "model": "Qwen/Qwen2.5-VL-7B-Instruct",
    "served_via": "vLLM 0.17.1 / ROCm 7.2.0 / TP=1 on a single MI300X (192 GB VRAM)",
    "source_uuid": "SRC-IMG-1042",
    "observations": [
        {"entity": "container_stack_sector_4", "type": "Hazard",
         "observation": "Visible vapor/thermal anomaly beside stacked containers",
         "confidence": 0.89, "location_hint": "Sector 4 / polymer stack"},
        {"entity": "service_road_north", "type": "Constraint",
         "observation": "Service road appears clear from drone perspective",
         "confidence": 0.62, "location_hint": "North service corridor"},
    ],
    "uncertainties": [
        {"kind": "missing_data",
         "detail": "Cannot confirm container contents from visual evidence alone"},
    ],
}

AUDIT_LOG_SAMPLE = {
    "scenario_id": "sector4-solvent-containment",
    "decision_id": "a1",
    "candidate_action": "Route containment team through Junction E instead of Gate 4",
    "trace": [
        {"step": "ingest", "source_uuid": "SRC-VID-2217",
         "asset": "cctv_gate4_src_vid_2217.png"},
        {"step": "vlm_call", "model": "Qwen/Qwen2.5-VL-7B-Instruct",
         "prompt": "VesperGrid evidence parser system prompt v1",
         "frames_submitted": 1, "tokens_in": 1284, "tokens_out": 312,
         "latency_ms": 6420, "served_via": "vLLM ROCm TP=1 on a single MI300X"},
        {"step": "schema_validate", "schema": "VLMObservationsBundle",
         "ok": True},
        {"step": "graph_normalize",
         "entities": ["service_lane_gate_4", "vehicle_queue"]},
        {"step": "synthesis", "model": "qwen-reasoning-7b",
         "prompt_template": "candidate_plan_v2",
         "human_review_required": True},
    ],
    "caveat": "Candidate plan only: verify obstruction at Gate 4 before dispatch.",
}

SIMULATION_REPLAY_SAMPLE = {
    "scenario_id": "sector4-solvent-containment",
    "simulation_kind": "bounded_route_hazard_scoring",
    "steps": [
        {"t": 0,   "blocked_route_risk": 0.44, "junction_e_risk": 0.21,
         "vapor_drift_radius_m": 80},
        {"t": 60,  "blocked_route_risk": 0.71, "junction_e_risk": 0.25,
         "vapor_drift_radius_m": 115},
        {"t": 120, "blocked_route_risk": 0.82, "junction_e_risk": 0.29,
         "vapor_drift_radius_m": 150},
        {"t": 180, "blocked_route_risk": 0.88, "junction_e_risk": 0.32,
         "vapor_drift_radius_m": 180},
    ],
    "recommended_route": "Junction E",
    "caveat": "Vapor drift sensitive to wind direction; rerun on next sensor update.",
}


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _mirror(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main() -> None:
    _ensure_dirs()

    field_map = CONSOLE_ASSETS / "vesper-field-map.png"
    drone     = CONSOLE_ASSETS / "drone_keyframe_src_img_1042.png"
    cctv      = CONSOLE_ASSETS / "cctv_gate4_src_vid_2217.png"
    sensor    = CONSOLE_ASSETS / "wind_sensor_src_sen_0924.png"

    print("Generating field map...");      make_field_map(field_map)
    print("Generating drone keyframe...");  make_drone_keyframe(drone)
    print("Generating CCTV keyframe...");   make_cctv_gate4(cctv)
    print("Generating wind sensor strip..."); make_wind_sensor(sensor)

    # Mirror images into demo/sector4/ so the evidence pack is self-contained
    for src in (drone, cctv, sensor):
        _mirror(src, DEMO_DIR / src.name)

    # Static text + JSON
    (DEMO_DIR / "operator_transcript_src_txt_7781.txt").write_text(
        TRANSCRIPT, encoding="utf-8"
    )
    _write_json(DEMO_DIR / "evidence_pack.json", EVIDENCE_PACK)
    _write_json(DEMO_DIR / "vlm_output_sample.json", VLM_OUTPUT_SAMPLE)
    _write_json(DEMO_DIR / "audit_log_sample.json", AUDIT_LOG_SAMPLE)
    _write_json(DEMO_DIR / "simulation_replay_sample.json", SIMULATION_REPLAY_SAMPLE)

    print("\nDone. Wrote:")
    for p in [field_map, drone, cctv, sensor]:
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size:,} bytes)")
    for p in sorted(DEMO_DIR.iterdir()):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
