# Synthetic Asset Creation Plan

## Goal

VesperGrid needs to look like a polished critical infrastructure product, not a toy dashboard. The assets should make the demo feel real, cinematic, and trustworthy while staying fully synthetic, safe, and competition-ready.

See also: [`asset_research_selection.md`](asset_research_selection.md) for the strict decision on which researched third-party resources are acceptable. The short version: use almost no raw open dataset imagery in the final UI. Create the core demo assets synthetically/procedurally so the product stays coherent and legally clean.

We will create a complete fictional industrial safety scenario:

**Scenario:** Sector 4 Solvent Containment
**Location:** Synthetic port logistics corridor
**Core event:** A solvent container breach creates heat/vapor risk near a blocked service lane.
**AI task:** Fuse visual, text, sensor, and map evidence into a source-linked operational twin.

No real facilities, real emergencies, real people, license plates, company logos, or sensitive infrastructure should appear.

## Asset Principles

1. **Synthetic but believable**
   The assets should look like operational evidence, not fantasy art.

2. **Source-linked**
   Every asset should map to a source ID used in the UI:
   - `SRC-IMG-1042`
   - `SRC-VID-2217`
   - `SRC-TXT-7781`
   - `SRC-SEN-0924`
   - `SRC-LIVE-9001`

3. **Legible in the UI**
   The assets must work as thumbnails and full previews.

4. **Consistent visual world**
   Same fictional site, same labels, same lighting logic, same incident.

5. **No legal risk**
   Use generated images, custom diagrams, and written text. Avoid copyrighted footage or real maps.

## Target Folder Structure

```text
demo/
  sector4/
    evidence_pack.json
    drone_keyframe_src_img_1042.png
    cctv_gate4_src_vid_2217.png
    wind_sensor_src_sen_0924.png
    operator_transcript_src_txt_7781.txt
    vlm_output_sample.json
    audit_log_sample.json

submission/
  hero_screenshot.png
  architecture_diagram.png
  amd_runtime_diagram.png
  demo_script.md
  fallback_demo_video.mp4
```

## Required Demo Assets

The latest expert feedback recommends keeping the core live demo to three evidence categories:

1. sampled drone/keyframe evidence
2. synthetic operator or radio transcript
3. schematic/map plus sensor context

We can still make the product visually rich, but the live reasoning story should stay tight. Too many modalities will look staged and will increase failure risk.

### 1. Operational Twin Map

**File:** `apps/console/public/assets/vesper-field-map.png`

**Purpose:**
This is the main background of the product. It should look like a top-down synthetic industrial yard map.

**How to create synthetically:**

- Use procedural generation with Python/Pillow or canvas-style drawing.
- Draw:
  - container rows
  - service roads
  - gate area
  - junction labels
  - hazard-adjacent lane
  - subtle grid overlay
  - industrial texture
- Avoid making it look like Google Maps or a real satellite image.

**Style direction:**

- Top-down industrial map
- Dark slate base
- Clean roads and lanes
- Container blocks
- Subtle safety-orange hazard glow
- Crisp enough for UI overlays

**Quality bar:**

- Must look good at full-screen dashboard size.
- Must not be overly blurry.
- Must leave enough visual room for UI risk zones.

**Improvement plan:**

The current map already exists. Next polish pass should:

- add clearer lane geometry
- add Gate 4 and Junction E areas
- improve container spacing
- reduce noisy texture
- make the blocked route visually readable

---

### 2. Drone Keyframe

**File:** `demo/sector4/drone_keyframe_src_img_1042.png`

**Source ID:** `SRC-IMG-1042`

**Purpose:**
This is the main visual evidence image. It should suggest a heat/vapor issue near containers.

**How to create synthetically:**

Use image generation or a procedural/composited image.

**Image generation prompt:**

```text
Synthetic drone surveillance keyframe of a large industrial port logistics yard, top-down oblique view, stacked shipping containers, service road, subtle white vapor plume near one container row, faint orange thermal glow overlay, hazy industrial lighting, no people, no readable logos, no license plates, realistic but clearly fictional, high-detail operational evidence image, 16:9
```

**Negative constraints:**

```text
no real company logos, no text, no faces, no emergency vehicles, no dramatic explosion, no cinematic fireball, no gore, no identifiable location
```

**Post-processing plan:**

- Add a small timestamp overlay:
  - `DRONE / SECTOR 4 / FRAME 03`
  - `SRC-IMG-1042`
- Add faint bounding highlight around the suspected leak zone.
- Keep the overlay subtle so it feels like evidence, not a poster.

**Quality bar:**

- Looks like a plausible drone keyframe.
- Shows a visible hazard clue.
- Does not look like fantasy disaster art.

---

### 2B. Short Drone Clip

**File:** `demo/sector4/drone_clip_sector4_5s.mp4`

**Source ID:** `SRC-VID-3005`

**Purpose:**
The expert specifically recommends a short, noisy drone video clip. The product should not stream full video into Qwen-VL. It should sample five keyframes and submit those frames as one multimodal request.

**How to create synthetically:**

- Create 5-6 generated frames with subtle camera drift, or animate the procedural map with a moving crop and vapor overlay.
- Duration: 5 seconds.
- Resolution: 1280x720 or lower.
- Add mild compression/noise.

**Frame sampling plan:**

```text
1 frame per second -> 5 keyframes -> single Qwen-VL multimodal request
```

**Quality bar:**

- It should feel like operational drone evidence.
- It should not look like cinematic disaster footage.
- It should be small enough to avoid demo latency and memory issues.

---

### 3. CCTV Gate 4 Keyframe

**File:** `demo/sector4/cctv_gate4_src_vid_2217.png`

**Source ID:** `SRC-VID-2217`

**Purpose:**
This creates the main contradiction: the radio/operator note suggests the route may be clear, but CCTV shows the service lane is blocked.

**How to create synthetically:**

Use image generation or a 2D composited scene.

**Image generation prompt:**

```text
Synthetic CCTV security camera frame from an industrial port gate, fixed overhead camera angle, service vehicles queued in a narrow lane, shipping containers and security barrier visible, low contrast surveillance footage, timestamp overlay style, no readable logos, no license plates, no identifiable people, realistic operational evidence, slightly compressed camera image, 16:9
```

**Negative constraints:**

```text
no faces, no readable plates, no real brands, no police, no weapons, no explosion, no dramatic cinematic lighting
```

**Post-processing plan:**

- Add overlay:
  - `GATE 4 CCTV`
  - `SRC-VID-2217`
  - fake timestamp
- Add faint rectangle around blocked lane.
- Slight desaturation and mild compression artifacts.

**Quality bar:**

- Clearly shows route blockage.
- Looks like surveillance evidence.
- Thumbnail must communicate â€œblocked routeâ€ quickly.

---

### 4. Wind Sensor Strip

**File:** `demo/sector4/wind_sensor_src_sen_0924.png`

**Source ID:** `SRC-SEN-0924`

**Purpose:**
This supports the vapor drift risk. It should look like a compact sensor readout or time-series strip.

**How to create synthetically:**

Use Python/Pillow, SVG, or HTML canvas. This does not need image generation.

**Visual contents:**

- Mini line chart for wind speed.
- Arrow showing direction toward fuel-adjacent lane.
- Readout:
  - `21 km/h NE`
  - `Pressure variance: +14%`
  - `SRC-SEN-0924`

**Style direction:**

- Dark background
- Thin blue/amber data lines
- Monospaced labels
- Looks like an industrial telemetry panel

**Quality bar:**

- Must be very legible.
- Must match the appâ€™s dark industrial visual style.

---

### 5. Operator Transcript

**File:** `demo/sector4/operator_transcript_src_txt_7781.txt`

**Source ID:** `SRC-TXT-7781`

**Purpose:**
This gives human context and creates uncertainty.

**Synthetic transcript draft:**

```text
[SRC-TXT-7781]
[00:18:06] Yard Ops: Sector 4 team reports solvent smell near polymer stack. Visual confirmation unclear.
[00:18:21] Safety Lead: Hydrant pressure on west line is unstable. Request tanker relay confirmation.
[00:18:39] Gate Control: Gate 4 route may be clear, but camera feed has not been checked.
[00:18:52] Yard Ops: Hold dispatch until route status is verified.
```

**Important narrative function:**

This transcript intentionally says â€œGate 4 route may be clear,â€ while the CCTV image shows blockage. That contradiction lets VesperGrid demonstrate intelligence:

> It does not blindly trust text. It compares evidence.

**Quality bar:**

- Short enough to read during demo.
- Realistic enough for judges.
- Not too dramatic.

---

### 6. Evidence Pack JSON

**File:** `demo/sector4/evidence_pack.json`

**Purpose:**
This lets the app and backend load a complete scenario from structured assets.

**Suggested structure:**

```json
{
  "scenario_id": "sector4-solvent-containment",
  "title": "Sector 4 Solvent Containment",
  "location": "Synthetic Port Logistics Corridor",
  "sources": [
    {
      "source_uuid": "SRC-IMG-1042",
      "kind": "image",
      "path": "drone_keyframe_src_img_1042.png",
      "claim": "Thermal/vapor anomaly near container stack",
      "confidence": 0.89
    },
    {
      "source_uuid": "SRC-VID-2217",
      "kind": "video_keyframe",
      "path": "cctv_gate4_src_vid_2217.png",
      "claim": "Gate 4 service lane appears blocked",
      "confidence": 0.81
    },
    {
      "source_uuid": "SRC-TXT-7781",
      "kind": "transcript",
      "path": "operator_transcript_src_txt_7781.txt",
      "claim": "Hydrant pressure unstable; Gate 4 route uncertain",
      "confidence": 0.74
    },
    {
      "source_uuid": "SRC-SEN-0924",
      "kind": "sensor",
      "path": "wind_sensor_src_sen_0924.png",
      "claim": "Wind pushes vapor toward fuel-adjacent lane",
      "confidence": 0.93
    }
  ]
}
```

---

### 7. VLM Output Sample

**File:** `demo/sector4/vlm_output_sample.json`

**Purpose:**
This is the deterministic fallback for model output. Later, live Qwen-VL output should match this schema.

**Suggested structure:**

```json
{
  "model": "qwen-vl-demo-schema",
  "source_uuid": "SRC-IMG-1042",
  "observations": [
    {
      "entity": "container_stack_sector_4",
      "type": "Hazard",
      "observation": "Visible vapor/thermal anomaly beside stacked containers",
      "confidence": 0.89,
      "location_hint": "Sector 4 / polymer stack"
    }
  ],
  "uncertainties": [
    {
      "kind": "missing_data",
      "detail": "Cannot confirm container contents from visual evidence alone"
    }
  ]
}
```

**Quality bar:**

- Must be schema-valid.
- Must cite `source_uuid`.
- Must include confidence and uncertainty.

---

### 8. Audit Log Sample

**File:** `demo/sector4/audit_log_sample.json`

**Purpose:**
This proves the system is auditable.

**Should include:**

- source UUID
- prompt used
- model name
- model output
- normalized graph entity
- candidate action
- caveat

**Important:**
Judges may ask: â€œHow do you know the AI did not hallucinate this?â€
The audit log answers that.

---

### 9. Simulation Replay Asset

**File:** `demo/sector4/simulation_replay_sample.json`

**Purpose:**
The expert is right that the simulation layer must feel credible and visible. Even if the MVP simulation is vectorized/CPU-bound, the UI should show risk changing in response to evidence.

**Suggested structure:**

```json
{
  "scenario_id": "sector4-solvent-containment",
  "simulation_kind": "bounded_route_hazard_scoring",
  "steps": [
    {
      "t": 0,
      "blocked_route_risk": 0.44,
      "junction_e_risk": 0.21,
      "vapor_drift_radius_m": 80
    },
    {
      "t": 60,
      "blocked_route_risk": 0.71,
      "junction_e_risk": 0.25,
      "vapor_drift_radius_m": 115
    },
    {
      "t": 120,
      "blocked_route_risk": 0.82,
      "junction_e_risk": 0.29,
      "vapor_drift_radius_m": 150
    }
  ],
  "recommended_route": "Junction E",
  "caveat": "Vapor drift is sensitive to wind direction updates."
}
```

**Quality bar:**

- Must not pretend to be advanced fluid physics.
- Should be credible as route/hazard scoring.
- Should visually move or update in the UI during the demo.

---

## Submission Assets

### 1. Hero Screenshot

**File:** `submission/hero_screenshot.png`

**How to create:**

- Run the app locally.
- Select the strongest source-linked state.
- Capture full dashboard at desktop size.

**Ideal screen state:**

- map visible
- selected source highlighted
- uncertainty ledger visible
- candidate plan visible
- MI300X runtime visible

---

### 2. Architecture Diagram

**File:** `submission/architecture_diagram.png`

**Create with:**
Figma, Canva, Excalidraw, Mermaid, or custom SVG.

**Diagram flow:**

```text
Evidence Pack
  -> Qwen-VL Keyframe Parser
  -> Schema Validator
  -> Evidence Graph
  -> Operational Twin
  -> Decision Support Synthesizer
  -> Source-Linked Candidate Plan
```

**Style:**

- clean
- dark or white variant
- AMD MI300X lane called out
- no buzzword clutter

---

### 3. AMD Runtime Diagram

**File:** `submission/amd_runtime_diagram.png`

**Purpose:**
Show why AMD hardware matters.

**Diagram content:**

```text
GPU 0: Qwen-VL TP=1, five-keyframe multimodal parsing
CPU/RAM: embeddings, entity normalization, graph scoring, and route/hazard simulation
Fallback: deterministic synthesis when the model endpoint is unavailable
```

**Key message:**

The 192 GB VRAM on one MI300X lets VesperGrid keep the multimodal model warm with bounded five-keyframe context.

---

### 4. Fallback Demo Video

**File:** `submission/fallback_demo_video.mp4`

**Length:**
2.5 to 3 minutes.

**Script:**

1. Start with messy evidence.
2. Ingest sampled evidence.
3. Show operational twin update.
4. Click candidate plan.
5. Show exact source lineage.
6. Show uncertainty contradiction.
7. Show AMD runtime panel.
8. End with the thesis.

**Why mandatory:**

If live GPU provisioning fails, the project still presents beautifully.

---

## Creation Methods

## Option A: AI Image Generation

Use for:

- drone keyframe
- CCTV keyframe
- possibly hero visual

Best when we need realistic evidence-like visuals quickly.

Rules:

- Always specify synthetic/fictional.
- Avoid logos, faces, plates, real locations.
- Keep scenes realistic, not cinematic disaster art.
- Generate at 16:9.
- Post-process with overlays and source IDs.

## Option B: Procedural Drawing

Use for:

- operational map
- wind sensor strip
- architecture diagram
- AMD runtime diagram

Best when we need control, clarity, and repeatability.

Tools:

- Python + Pillow
- SVG
- HTML canvas
- Mermaid/Excalidraw

## Option C: Manual Text Writing

Use for:

- operator transcript
- demo script
- audit log
- VLM fallback output

Best because these need narrative precision.

## Option D: UI-Generated Assets

Use for:

- risk zones
- route vectors
- source highlights
- processing states
- selected evidence cards

These should be rendered by the app, not baked into images.

## Implementation Order

### Step 1: Create Asset Directories

```bash
mkdir -p demo/sector4 submission
```

### Step 2: Generate Core Evidence

Create:

1. drone keyframe
2. short drone clip or five sampled keyframes
3. CCTV keyframe
4. wind sensor strip
5. operator transcript

### Step 3: Create Structured Files

Create:

1. `evidence_pack.json`
2. `vlm_output_sample.json`
3. `audit_log_sample.json`
4. `simulation_replay_sample.json`

### Step 4: Wire Assets Into UI

Add source previews:

- selected source panel
- evidence thumbnail
- click action -> highlight source preview and map zone

### Step 5: Polish Map

Improve:

- Gate 4
- Junction E
- Sector 4 labels
- blocked route clarity
- recommended route clarity

### Step 6: Create Submission Assets

After UI polish:

- screenshot
- architecture diagram
- AMD runtime diagram
- fallback video

## Visual Quality Bar

The final demo should feel like:

> Bloomberg Terminal + industrial control room + AI evidence lab.

It should not feel like:

- a chatbot
- a SaaS landing page
- a generic dashboard
- a disaster movie
- a ComfyUI gallery

## Final Asset Checklist

Required for minimum strong demo:

- [ ] polished operational twin map
- [ ] synthetic drone keyframe
- [ ] short synthetic drone clip or five sampled keyframes
- [ ] synthetic CCTV keyframe
- [ ] synthetic wind sensor strip
- [ ] operator transcript
- [ ] evidence pack JSON
- [ ] VLM output sample JSON
- [ ] audit log sample JSON
- [ ] simulation replay sample JSON
- [ ] source preview UI
- [ ] hero screenshot
- [ ] fallback demo video

Stretch assets:

- [ ] second unseen industrial test image
- [ ] short animated processing sequence
- [ ] architecture diagram
- [ ] AMD runtime diagram
- [ ] downloadable audit report

## Recommendation

Create the assets synthetically and openly label the scenario as synthetic. This is the safest and strongest path. It avoids copyright/security issues while letting us control every clue needed for the demo narrative.

The key asset is not just one beautiful image. The key asset is the **evidence chain**:

```text
Synthetic evidence -> source UUID -> parsed observation -> uncertainty -> candidate plan -> clickable lineage
```

That chain is what makes VesperGrid feel real.
