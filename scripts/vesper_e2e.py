#!/usr/bin/env python3
"""VesperGrid end-to-end smoke test + screenshot capture.

Runs the full pipeline automatically:
  1. Health checks  (API, vLLM, nginx)
  2. Deterministic ingest  (no images)
  3. VLM ingest  (synthetic Gazebo frames generated on the fly)
  4. /api/jobs list endpoint
  5. Browser screenshot of dashboard  (via Playwright)
  6. Prints a summary report with pass/fail for each step

Usage:
  python3 scripts/vesper_e2e.py [--api http://165.245.143.11] [--screenshots]

Deps (cloud): pip install playwright httpx Pillow && playwright install chromium
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

SCREENSHOTS_DIR = Path(__file__).parent.parent / "e2e_screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

results: list[dict] = []


def _log(symbol: str, color: str, label: str, detail: str = "") -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"  {color}{symbol}{RESET} [{ts}] {BOLD}{label}{RESET}  {detail}")


def ok(label: str, detail: str = "") -> None:
    _log("✓", GREEN, label, detail)
    results.append({"step": label, "status": "PASS", "detail": detail})


def fail(label: str, detail: str = "") -> None:
    _log("✗", RED, label, detail)
    results.append({"step": label, "status": "FAIL", "detail": detail})


def skip(label: str, detail: str = "") -> None:
    _log("~", YELLOW, label, detail)
    results.append({"step": label, "status": "SKIP", "detail": detail})


def _synth_frame(text: str = "SECTOR 4 — TANK B-4 FLANGE") -> bytes:
    """Generate a synthetic 640×360 test frame with visible text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (640, 360), color=(18, 22, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 639, 359], outline=(60, 120, 80), width=3)
        draw.rectangle([160, 100, 480, 260], fill=(30, 60, 35))
        draw.ellipse([280, 120, 380, 180], fill=(220, 140, 20))
        for r in range(4):
            draw.ellipse(
                [300 - r*15, 110 - r*12, 360 + r*15, 170 + r*12],
                outline=(180 - r*30, 200 - r*40, 20),
                width=1,
            )
        draw.text((20, 16), "VesperGrid · Gazebo Synthetic Frame", fill=(134, 215, 255))
        draw.text((20, 320), text, fill=(255, 177, 129))
        draw.text((480, 320), time.strftime("%H:%M:%S"), fill=(130, 130, 130))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except ImportError:
        # Minimal valid JPEG fallback (1×1 grey pixel)
        return bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD2,
            0x8A, 0x28, 0x03, 0xFF, 0xD9,
        ])


async def step_health(client: httpx.AsyncClient, api: str) -> None:
    print(f"\n{CYAN}{BOLD}── Step 1: Health Checks ──────────────────────────────{RESET}")
    try:
        r = await client.get(f"{api}/api/health", timeout=10)
        r.raise_for_status()
        data = r.json()
        backend = data.get("vlm_backend", "?")
        ok("API health", f"vlm_backend={backend}")
    except Exception as e:
        fail("API health", str(e))
        return

    try:
        r = await client.get(f"{api.rstrip('/').replace('/api', '')}/api/health", timeout=10)
        data = r.json()
        ok("Nginx proxy", f"HTTP {r.status_code}")
    except Exception as e:
        fail("Nginx proxy", str(e))

    try:
        r = await client.get(f"{api}/api/jobs", timeout=10)
        r.raise_for_status()
        jobs = r.json()
        ok("/api/jobs endpoint", f"{len(jobs)} job(s) in registry")
    except Exception as e:
        fail("/api/jobs endpoint", str(e))


async def step_deterministic(client: httpx.AsyncClient, api: str) -> str | None:
    print(f"\n{CYAN}{BOLD}── Step 2: Deterministic Ingest (no images) ───────────{RESET}")
    try:
        r = await client.post(
            f"{api}/api/ingest",
            json={
                "location": "Tank B-4 Flange · Northgate LNG Terminal",
                "field_notes": "E2E smoke test — deterministic path",
                "media_count": 0,
                "sensor_count": 1,
            },
            timeout=15,
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        backend = r.json()["backend"]
        ok("POST /api/ingest", f"job_id={job_id} backend={backend}")
    except Exception as e:
        fail("POST /api/ingest", str(e))
        return None

    # await completion
    for _ in range(20):
        await asyncio.sleep(0.5)
        snap = (await client.get(f"{api}/api/ingest/{job_id}", timeout=10)).json()
        if snap["status"] in ("complete", "failed"):
            break

    if snap["status"] == "complete":
        n = len(snap.get("result", {}).get("evidence", []))
        ok("Deterministic scenario", f"evidence={n}")
    else:
        fail("Deterministic scenario", snap.get("error", "unknown"))
    return job_id


async def step_vlm_ingest(client: httpx.AsyncClient, api: str) -> str | None:
    print(f"\n{CYAN}{BOLD}── Step 3: VLM Ingest (3 synthetic Gazebo frames) ─────{RESET}")
    sources = [
        ("cctv_south_frame.jpg", "CCTV South — B-4 Plume"),
        ("drone_d1_frame.jpg",   "Drone D-1 — Overhead View"),
        ("cctv_gate_frame.jpg",  "Gate CCTV — Context"),
    ]
    files_payload = []
    for fname, label in sources:
        jpeg = _synth_frame(label)
        files_payload.append(("images", (fname, jpeg, "image/jpeg")))
        ok(f"Synthesised frame", f"{fname}  {len(jpeg)} bytes")

    try:
        r = await client.post(
            f"{api}/api/ingest/upload",
            files=files_payload,
            data={
                "location": "Tank B-4 Flange · Northgate LNG Terminal",
                "field_notes": (
                    "Active LNG flange failure. Gas plume visible at south cluster. "
                    "Drone D-1 orbiting at 30m. Worker evacuation in progress."
                ),
                "sensor_count": "3",
            },
            timeout=30,
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        backend = r.json()["backend"]
        ok("POST /api/ingest/upload", f"job_id={job_id} backend={backend}")
    except Exception as e:
        fail("POST /api/ingest/upload", str(e))
        return None

    print(f"         Waiting for Qwen-VL on MI300X…")
    t0 = time.time()
    last_stage = ""
    for _ in range(240):   # up to 120s
        await asyncio.sleep(0.5)
        try:
            snap = (await client.get(f"{api}/api/ingest/{job_id}", timeout=10)).json()
        except Exception:
            continue
        events = snap.get("events", [])
        if events:
            stage = events[-1].get("stage", "")
            msg   = events[-1].get("message", "")
            pct   = int(events[-1].get("progress", 0) * 100)
            if stage != last_stage:
                _log("→", CYAN, f"  {stage.upper():14s}", f"{pct:3d}%  {msg[:80]}")
                last_stage = stage
        if snap["status"] in ("complete", "failed"):
            break

    elapsed = round(time.time() - t0, 1)
    if snap["status"] == "complete":
        result = snap.get("result") or {}
        n_ev   = len(result.get("evidence", []))
        n_hz   = len([e for e in result.get("evidence", []) if e.get("type") == "Hazard"])
        be     = snap.get("backend", "?")
        ok("VLM scenario complete", f"backend={be} evidence={n_ev} hazards={n_hz} t={elapsed}s")
        return job_id
    else:
        fail("VLM scenario", f"status={snap['status']} err={snap.get('error','?')} t={elapsed}s")
        return None


async def step_screenshot(api_root: str, out_dir: Path) -> None:
    print(f"\n{CYAN}{BOLD}── Step 4: Dashboard Screenshot ────────────────────────{RESET}")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        skip("Dashboard screenshot", "playwright not installed — run: pip install playwright && playwright install chromium")
        return

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
            page    = await browser.new_page(viewport={"width": 1600, "height": 900})
            await page.goto(api_root, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(2)
            path = out_dir / f"dashboard_{time.strftime('%Y%m%dT%H%M%S')}.png"
            await page.screenshot(path=str(path), full_page=True)
            await browser.close()
        ok("Dashboard screenshot", str(path))
    except Exception as e:
        fail("Dashboard screenshot", str(e))


async def step_jobs_list(client: httpx.AsyncClient, api: str) -> None:
    print(f"\n{CYAN}{BOLD}── Step 5: /api/jobs Registry Verification ────────────{RESET}")
    try:
        r = await client.get(f"{api}/api/jobs?limit=20", timeout=10)
        r.raise_for_status()
        jobs = r.json()
        ok("/api/jobs response", f"{len(jobs)} job(s) visible to ticker")
        for j in jobs[:5]:
            status  = j.get("status", "?")
            backend = j.get("backend", "?")
            stage   = j.get("stage", "?")
            jid     = j.get("job_id", "?")
            color   = GREEN if status == "complete" else (RED if status == "failed" else YELLOW)
            _log("·", color, f"  {jid}", f"{status:8s} {backend:14s} {stage}")
    except Exception as e:
        fail("/api/jobs", str(e))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api",         default="http://165.245.143.11")
    parser.add_argument("--screenshots", action="store_true", default=True)
    parser.add_argument("--skip-vlm",    action="store_true")
    args = parser.parse_args()

    api_root = args.api.rstrip("/")
    api      = api_root   # nginx proxies /api → uvicorn

    print(f"\n{BOLD}{'═'*58}{RESET}")
    print(f" VesperGrid End-to-End Test  ·  {api}")
    print(f"{BOLD}{'═'*58}{RESET}")

    async with httpx.AsyncClient(timeout=120) as client:
        await step_health(client, api)
        await step_deterministic(client, api)
        if not args.skip_vlm:
            await step_vlm_ingest(client, api)
        await step_jobs_list(client, api)

    if args.screenshots:
        await step_screenshot(api_root, SCREENSHOTS_DIR)

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*58}{RESET}")
    print(f" Results\n")
    passed = failed = skipped = 0
    for r in results:
        st = r["status"]
        if   st == "PASS": color = GREEN;  passed  += 1
        elif st == "FAIL": color = RED;    failed  += 1
        else:              color = YELLOW; skipped += 1
        print(f"  {color}{st:4s}{RESET}  {r['step']:<40s} {r['detail'][:60]}")
    print(f"\n  {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  {YELLOW}{skipped} skipped{RESET}")
    print(f"\n  Screenshots → {SCREENSHOTS_DIR}/")
    print(f"{BOLD}{'═'*58}{RESET}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
