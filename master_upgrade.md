# VesperGrid Master Upgrade

## Product Understanding

VesperGrid is an incident-command console for a synthetic LNG terminal leakage event. Gazebo is the source of truth for the incident: Tank B-4 develops a visible gas leak, Drone D-1 orbits the incident area, two CCTV cameras provide fixed visual coverage, ambient drones keep the scene alive, and gas/wind sensors publish the changing hazard state.

The intended demo flow is:

1. Gazebo renders the leak and camera views.
2. ROS2 bridges camera frames plus gas/wind readings into the VesperGrid API.
3. Qwen-VL analyzes camera evidence from the drone and CCTV feeds.
4. A deterministic signal model analyzes gas toxicity and wind drift from sensor traces.
5. The operator opens the mic and asks supervisors around Sector 4 for status.
6. Worker/supervisor voice reports are transcribed through STT and become source-linked evidence.
7. VesperGrid synthesizes all modalities into an incident state, uncertainty ledger, and response options.

The core promise is not an autonomous decision maker. It is a source-linked operational twin that shows which evidence supports each response recommendation.

## Current Repo Truth

### Gazebo and ROS2

- `ros2/lng_terminal_world/worlds/lng_terminal.sdf` is the richer canonical world. It contains the large LNG terminal, D-1/D-2/D-3 drone models, CCTV South, CCTV Gate, visual leak effects, and a gas sensor model.
- `DroneAnimator.cc` animates D-1 with lively hover motion, D-2 with a patrol cycle, and D-3 with a random-walk patrol.
- `lng_terminal.launch.py` bridges three camera topics into ROS2:
  - `/cctv_south/image_raw`
  - `/drone_d1/image_raw`
  - `/cctv_gate/image_raw`
- `gas_leak_publisher.py` publishes a deterministic gas ppm ramp and wind state.
- `frame_sampler.py` posts keyframe bundles to `/api/ingest/upload`.
- `evidence_bridge/bridge_node.py` buffers drone/CCTV frames and gas/wind readings, then triggers API ingest when gas crosses threshold.

### API and Model Layer

- FastAPI exposes health, scenario, ingest upload, job status, SSE events, feed discovery, and latest-frame endpoints.
- Ingest supports image uploads and routes image frames through Qwen-VL via vLLM when configured, local Qwen-VL when CUDA is available, and deterministic fallback otherwise.
- Scenario synthesis is still mostly shaped around the old `sector4.json` schema and simple media/sensor counts.
- Visual evidence is partially real, but sensor traces and audio reports were not first-class inputs before this upgrade.

### Dashboard

- The React app already polls `/api/feeds`, `/api/jobs`, and ingest SSE streams.
- It still reads `sector4.json` as the main fallback and contains several fixed source asset mappings.
- The UI reads more like a polished AI demo than a practical incident console. The next design direction is a dense operations surface: feeds, timeline, gas trend, voice reports, evidence, map, and response options.

### Demo Data

- `demo/sector4/` contains deterministic image, transcript, sensor, VLM, and simulation samples.
- The voice channel now has a demo manifest and replaceable audio placeholders under `demo/sector4/audio/`.

## Gap Analysis

- Audio needs to be a real evidence type, not just a text note.
- Sensor readings need structured ingestion and deterministic analysis, not just `sensor_count`.
- The ROS bridge and synthetic frame generator need to send recent gas/wind traces with each incident bundle.
- The dashboard needs a central operator mic flow and visible worker voice reports.
- Recommendations need to cite camera, sensor, and voice source IDs.
- The fallback path must remain reliable when MI300X, local VLM, or STT dependencies are unavailable.

## Implementation Roadmap

### 1. Multimodal Ingest

- Accept images, audio files, `sensor_trace`, and `voice_manifest` in `/api/ingest/upload`.
- Preserve uploaded evidence under the temp evidence directory by job ID.
- Stream modality-aware progress: sampling, parsing vision, transcribing voice, analyzing sensors, synthesizing.
- Keep `/api/ingest` deterministic for JSON-only demos.

### 2. Voice Channel

- Add STT through `faster-whisper` when installed.
- Use manifest transcript fallback explicitly when STT is unavailable.
- Treat each voice report as source-linked evidence with speaker, role, location, transcript, confidence, and optional audio URL.
- Let the dashboard record operator audio through `MediaRecorder` and upload it to the same evidence pipeline.

### 3. Sensor Analysis

- Analyze gas ppm and wind samples deterministically.
- Compute peak ppm, latest ppm, ppm rise rate, threshold crossings, toxicity band, wind direction, and confidence.
- Convert the analysis into sensor evidence, a vapor drift zone, uncertainties, and response actions.
- Avoid LLMs for numeric sensor math.

### 4. Dashboard Remake

- Make the first screen an operations console, not a landing page.
- Prioritize:
  - live feed grid
  - incident state
  - gas trend
  - voice channel
  - evidence timeline
  - risk map
  - response options
- Keep `sector4.json` only as offline fallback.
- Remove judge-facing language from primary panels.

### 5. Validation

- Import the FastAPI app with `PYTHONPATH=apps/api/src`.
- Exercise uploads with images only, audio only, sensor trace only, and mixed bundles.
- Build the console when `npm` is available.
- Verify source lineage for image, audio, and sensor evidence.
