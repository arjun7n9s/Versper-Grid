# VesperGrid — Last-Minute Feature Plans

Ideas to implement if time permits before demo. Ordered by impact.

---

## 1. Emergency Broadcast Loop (High Impact — Demo Wow Factor)

### Concept
Full closed-loop: Gazebo simulation has a speaker entity → operator approves an action
on the dashboard → LLM generates a site-specific evacuation announcement → TTS converts
it to audio → audio plays through the Gazebo world speaker (and optionally the browser).

### User Flow
1. Incident detected → VLM generates scenario + suggested actions
2. Dashboard shows an **[APPROVE BROADCAST]** button on the ActionStack panel
3. Operator clicks it
4. API calls Qwen2.5-VL again with a prompt:
   > "You are the site PA system. Gas leak at Tank B-4. Wind direction NW at 4.2 m/s.
   >  Generate a 3-sentence emergency PA announcement telling workers which exits are safe
   >  and which zones to avoid."
5. LLM response → TTS (kokoro-onnx or pyttsx3) → `.wav` file saved
6. Gazebo world plays the audio via a `gz::sim::AudioSource` component on the speaker model
7. Dashboard also plays the audio in-browser via `<audio>` tag (stream from `/api/broadcast/latest`)

### Implementation Plan
- **Backend**: New `/api/broadcast/approve` POST endpoint
  - Accepts `job_id`, calls VLM for PA script, runs TTS, saves wav to evidence dir
  - Returns audio URL
- **TTS options**:
  - `kokoro-onnx` — higher quality, ONNX runtime, no GPU needed
  - `pyttsx3` — zero deps, lower quality, guaranteed to work
  - Recommend: try kokoro first, fall back to pyttsx3
- **Gazebo**: Add `<audio_source>` plugin to the SDF world at the speaker pole position
  - Speaker model already visually present in the world (the pole with orange light)
  - Trigger audio play via gz transport topic: `/world/lng_terminal/speaker/play`
- **Dashboard**: Add `[APPROVE BROADCAST]` button in `ActionStack` component
  - Button disabled until a complete scenario exists
  - On click → POST → receive audio URL → `new Audio(url).play()`
  - Show waveform animation while playing

### Files to touch
- `apps/api/src/vespergrid/main.py` — add `/api/broadcast/approve`
- `apps/api/src/vespergrid/broadcast.py` — new: TTS + VLM PA script generation
- `apps/console/src/App.tsx` — add approve button + audio playback to ActionStack
- `ros2_temp/.../worlds/lng_terminal.sdf` — add AudioSource plugin to speaker model

---

## 2. Cross-Camera Reasoning Prompt Upgrade (Medium Impact — Easy Win)

### Concept
Currently the VLM receives all 3 Gazebo frames in one call but the system prompt
doesn't instruct it to correlate across cameras. Upgrading the prompt to explicitly
ask for cross-camera reasoning produces richer, more defensible evidence items.

### Change
In `vlm_client.py`, update the system prompt to include:
> "You are reviewing footage from 3 simultaneous cameras at an LNG terminal.
>  Camera 1 (CCTV South) watches Tank B-4 from ground level.
>  Camera 2 (Drone D1) orbits Tank B-4 at 22m altitude.
>  Camera 3 (Gate CCTV) watches the main entry/exit.
>  Correlate observations across all three views. Note if the plume visible on
>  Camera 1 matches the drift direction visible on Camera 2. Note if Camera 3
>  shows personnel still present in the danger zone."

### Files to touch
- `apps/api/src/vespergrid/vlm_client.py` — update `SYSTEM_PROMPT`

---

## 3. Sensor Anomaly Detection (Medium Impact — New AI Modality)

### Concept
Replace the threshold-only rule engine with an Isolation Forest trained on normal
operating ranges. Catches subtle sensor drift before LEL threshold breach.

### Implementation
- `scikit-learn` `IsolationForest` fit on synthetic "normal" sensor data at startup
- Run on each incoming 30-point sensor trace
- Output: anomaly score + flagged timestamps → fed into scenario as extra evidence item
- Adds a 4th distinct AI modality (vision + audio + rules + unsupervised anomaly)

### Files to touch
- `apps/api/src/vespergrid/sensor_analysis.py` — add `IsolationForest` path
- `apps/api/src/vespergrid/ingest.py` — call anomaly detector in pipeline

---

## 4. RAG — Incident Memory (High Impact, Higher Effort ~4hrs)

### Concept
Embed past scenario JSON objects with `sentence-transformers` into ChromaDB.
On each new ingest, retrieve the 2 most similar past incidents and inject them
into the VLM context as "historical precedent".

### Stack
- `chromadb` + `sentence-transformers` (`all-MiniLM-L6-v2`) — fully local, no GPU
- Seed DB with 5-10 synthetic historical incidents at startup

### Files to touch
- New `apps/api/src/vespergrid/memory.py`
- `apps/api/src/vespergrid/vlm_client.py` — inject retrieved context into prompt
- `apps/api/src/vespergrid/ingest.py` — store completed scenarios in ChromaDB

---

## 5. Evacuation Zone Geometry on Orbital Map (Medium Impact)

### Concept
Given gas source coords + wind vector from sensor trace, compute ISO 15926 PAC
exclusion radius and render it as a dynamic polygon on the orbital map SVG.
Pure geometry — no new model needed.

### Files to touch
- `apps/console/src/App.tsx` — update `OrbitalMap` to render computed zone
- `apps/api/src/vespergrid/sensor_analysis.py` — add `compute_exclusion_zone()`
- API: expose zone in scenario `risk_zones` field

---

## Priority Order (if time allows)
1. Cross-camera prompt upgrade (~30 min, zero risk)
2. Emergency broadcast loop (~3 hrs, highest demo impact)
3. Sensor anomaly detection (~2 hrs, adds AI modality)
4. Evacuation zone geometry (~2 hrs, visual impact)
5. RAG incident memory (~4 hrs, most complex)
