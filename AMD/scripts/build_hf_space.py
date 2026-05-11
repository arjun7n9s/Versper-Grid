"""Build the Hugging Face Space static bundle into submission/spaces/.

Usage (deterministic / local demo):
    python scripts/build_hf_space.py

Usage (pointing at cloud API):
    set VITE_API_BASE=http://<CLOUD_IP>
    python scripts/build_hf_space.py

Steps:
  1. Run `npm --prefix apps/console run build` (uses VITE_API_BASE if set).
  2. Copy the Vite dist/ output to submission/spaces/.
  3. Write submission/spaces/README.md (HF Spaces frontmatter).

To deploy to Hugging Face after this script:
    cd submission/spaces
    git init && git remote add space https://huggingface.co/spaces/<user>/<repo>
    git add . && git commit -m "deploy: VesperGrid static console"
    git push space main
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "apps" / "console" / "dist"
SPACES = ROOT / "submission" / "spaces"

HF_README = """\
---
title: VesperGrid
emoji: 🛢️
colorFrom: gray
colorTo: gray
sdk: static
pinned: true
short_description: Critical-infrastructure operational twin on AMD MI300X
---

# VesperGrid

**Track 3 — Vision & Multimodal AI · AMD Developer Hackathon 2026**

An evidence-grounded operational twin for industrial-safety incidents.
Upload a multimodal evidence pack (drone frame, gate camera clip, wind telemetry,
operator note) and get a source-linked candidate response plan with an Uncertainty
Ledger that names every contradiction.

## How it works

The console here runs **fully deterministic** (no GPU required to view the demo).
When connected to the AMD MI300X cloud backend, `Qwen2.5-VL-7B-Instruct` via
vLLM ROCm performs the multimodal reasoning; the deterministic synthesizer is the
fallback.

- **Code:** [GitHub](<GITHUB_URL>)
- **Demo video:** [YouTube/Drive](<VIDEO_URL>)
- **Slide deck:** See repo `submission/deck.pdf`
- **AMD Cloud bootstrap:** `scripts/bootstrap_amd_cloud.sh` (1× MI300X, TP=1)
"""

def main() -> None:
    api_base = os.environ.get("VITE_API_BASE", "")
    print(f"[build_hf_space] VITE_API_BASE = {repr(api_base) if api_base else '(empty — deterministic mode)'}")

    print("[build_hf_space] building console...")
    env = {**os.environ, "VITE_API_BASE": api_base}
    result = subprocess.run(
        "npm --prefix apps/console run build",
        cwd=ROOT,
        env=env,
        shell=True,
    )
    if result.returncode != 0:
        sys.exit(f"[build_hf_space] build failed with exit code {result.returncode}")

    if not DIST.exists():
        sys.exit(f"[build_hf_space] dist not found at {DIST}")

    print(f"[build_hf_space] copying dist → {SPACES.relative_to(ROOT)}")
    if SPACES.exists():
        shutil.rmtree(SPACES)
    shutil.copytree(DIST, SPACES)

    readme_path = SPACES / "README.md"
    readme_path.write_text(HF_README, encoding="utf-8")
    print(f"[build_hf_space] wrote {readme_path.relative_to(ROOT)}")

    total = sum(f.stat().st_size for f in SPACES.rglob("*") if f.is_file())
    print(f"[build_hf_space] done — {len(list(SPACES.rglob('*')))} files, "
          f"{total / 1024 / 1024:.1f} MB total")
    print()
    print("Next steps:")
    print("  1. Set VITE_API_BASE=http://<CLOUD_IP> and re-run to point at GPU backend.")
    print("  2. Push submission/spaces/ to your HF Space repo.")
    print("  3. Update submission/spaces/README.md placeholders (<GITHUB_URL>, <VIDEO_URL>).")


if __name__ == "__main__":
    main()
