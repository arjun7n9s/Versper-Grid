# Asset Research Selection Memo

## Selection Lock

VesperGrid should use **almost no third-party visual assets in the final app**.

The research reports contain many valid resources, but most are wrong for this demo. The final product needs to feel like one coherent industrial incident with auditable source lineage. A mixed set of stock images, public CCTV frames, real maps, and research datasets would make the demo look patched together and would invite licensing/privacy questions at exactly the wrong moment.

Strict decision:

> Build the core evidence pack synthetically and procedurally. Use third-party resources only when they improve production quality without becoming visible raw evidence.

That means the final VesperGrid demo should show:

- a fictional Sector 4 industrial site map created by us
- synthetic drone/keyframe evidence created for this exact incident
- synthetic CCTV evidence created for this exact route contradiction
- synthetic telemetry/sensor strips
- synthetic operator transcript
- synthetic VLM/audit/simulation JSON
- open-source UI libraries only where they serve the product surface

## Acceptance Rules

A resource is allowed only if it passes all five tests:

1. **Scenario fit:** It directly supports Sector 4 Solvent Containment.
2. **Visual coherence:** It can match the dark industrial command-center world.
3. **Source-lineage fit:** It can be tied to a clear source UUID and narrative role.
4. **License clarity:** It is permissive or stays outside the distributed product.
5. **Demo polish:** It makes the product more beautiful, not just more populated.

If a resource is merely available, interesting, or realistic, reject it.

## Reviewed Sources

Reviewed from `Research/`:

- `deep-research-report-agent1.md`
- `deep-research-rport-agent2.md`
- `deep-research-report-agent4.md`
- `agent4-report-part2.md`
- `VesperGrid Asset & Tooling Strategy for an Industrial Multimodal Operational Twin Research by Agent 2.zip`
- extracted `vespergrid-assets-strategy-report.md`
- bundled `images/image_1.png`

Notes:

- `deep-research-rport-agent2.md`, `deep-research-report-agent4.md`, and `agent4-report-part2.md` are empty.
- The useful research content is `deep-research-report-agent1.md` and the extracted Agent 2 strategy report.
- The bundled `image_1.png` is an OSM building LOD explanatory image. It is not a VesperGrid demo asset.

## Approved For Final Demo

### 1. Synthetic / Procedural Core Asset Creation

**Decision:** Strong Use.

**License:** Owned by us if generated/authored cleanly.

**Use for:**

- operational twin map
- drone keyframes or 5-second sampled clip
- CCTV Gate 4 keyframe
- wind/sensor strip
- operator transcript
- evidence pack JSON
- VLM fallback output
- audit log sample
- simulation replay JSON
- submission screenshots and video sequence

**Why it fits:** This is the only route that gives us full control over visual language, incident clues, source IDs, contradictions, and public-demo safety.

**Risk:** Low.

**Implementation rule:** All core evidence must be synthetic, fictional, and explicitly source-linked.

### 2. Existing Lucide Icons

**Decision:** Strong Use.

**License:** ISC.

**Use for:**

- evidence type icons
- warning and uncertainty states
- route/action controls
- GPU/runtime indicators
- audit/source lineage controls

**Why it fits:** Lucide is already installed in the console, visually clean, and enough for our current UI. Adding Tabler, Heroicons, Font Awesome, or IconScout now would create icon-style drift.

**Risk:** Low.

**Implementation rule:** Use Lucide first. Add no new icon set unless a required operational symbol truly does not exist.

### 3. Apache ECharts Or Lightweight Custom SVG/Canvas

**Decision:** Use if chart polish becomes necessary.

**License:** Apache 2.0 for ECharts.

**Use for:**

- wind strip
- route risk over time
- blocked-route vs Junction E simulation replay
- GPU utilization and latency charts

**Why it fits:** It can make telemetry feel serious and precise without importing a whole dashboard template.

**Risk:** Low.

**Implementation rule:** Prefer custom CSS/SVG for small strips. Use ECharts only if the simulation/replay panel needs richer chart behavior.

### 4. ambientCG CC0 Textures

**Decision:** Use only if we create 3D or composited synthetic renders.

**License:** CC0 1.0.

**Use for:**

- asphalt
- concrete
- metal/rust
- industrial ground texture
- container surface texture

**Why it fits:** If we need more realism in generated/composited visuals, CC0 textures are clean and do not pull in real facility imagery.

**Risk:** Low.

**Implementation rule:** Do not build a 3D asset pipeline just because textures exist. Use only if it materially improves the drone/CCTV assets.

### 5. Mermaid / Diagrams.net / Custom SVG

**Decision:** Use for docs and submission diagrams.

**License:** Mermaid is MIT; diagrams.net is Apache 2.0.

**Use for:**

- architecture diagram
- evidence-to-simulation chain
- AMD runtime topology
- submission visuals

**Why it fits:** These help explain the system without adding risky media assets.

**Risk:** Low.

**Implementation rule:** Raw Mermaid is acceptable in docs. Final submission diagrams should be visually polished, either custom SVG or designed from Mermaid output.

### 6. OBS / Standard Screen Recording Tools

**Decision:** Use for final demo capture.

**Use for:**

- fallback demo video
- short presentation clips
- hero screenshot capture workflow

**Why it fits:** A polished backup video is mandatory for judging reliability.

**Risk:** Low.

**Implementation rule:** Capture the real app state, not a fake cinematic mockup.

## Conditionally Useful, But Not For MVP

### Babylon.js / Three.js Digital Twin Examples

**Decision:** Maybe later.

**Why:** Good alignment with digital twin visualization, but adding 3D now risks spending time on spectacle before the 2D evidence chain is excellent.

**Allowed use:** Inspiration or future 3D miniature after source previews, simulation replay, and audit viewer are complete.

### Reagraph / React Flow / Cytoscape

**Decision:** Maybe later.

**Why:** Evidence graphs sound impressive, but a graph canvas can clutter the MVP. The current stronger pattern is clickable source cards, map highlights, audit drawer, and uncertainty ledger.

**Allowed use:** Dedicated Evidence Graph view only after the core demo is already polished.

### QGIS / OpenMapTiles / MapTiler / OSM Workflows

**Decision:** Do not use for the core demo map.

**Why:** They create real-map attribution and derived-data questions, and the demo scenario is fictional. A custom procedural map is cleaner and more controllable.

**Allowed use:** Internal inspiration, future real deployment notes, or architecture discussion.

### Industrial Hazards Detection / Fire-Smoke / MBDD / Mendeley Datasets

**Decision:** Training/benchmark only, not final UI evidence.

**Why:** They may be useful if we need to test detectors, but raw frames will not match the Sector 4 story and may contain visual/privacy/license distractions.

**Allowed use:** Private experimentation, model validation, or non-bundled benchmarks with attribution.

## Rejected For Final App

### Unsplash / Pexels / Pixabay

**Decision:** Reject.

**Reason:** Stock imagery will make VesperGrid feel like a dressed-up pitch deck rather than a source-linked operational twin. Even when the license is usable, the images are not incident-specific.

**Allowed use:** Moodboard only.

### OpenAerialMap / Real Satellite Or Drone Basemaps

**Decision:** Reject.

**Reason:** Real aerial imagery creates attribution, location, and critical-infrastructure implications. It also fights the fictional site strategy.

**Allowed use:** None for MVP visuals.

### Raw CCTV / Surveillance / Drone Datasets

**Decision:** Reject.

**Reason:** High privacy risk, inconsistent camera styles, possible people/faces/plates, varying licenses, and poor fit with the exact Gate 4 contradiction.

**Allowed use:** Private model testing only if license is clear.

### Real Emergency / Police / 911 Transcripts

**Decision:** Reject as copied content.

**Reason:** Wrong domain tone and privacy risk. VesperGrid is industrial safety decision support, not public emergency dispatch.

**Allowed use:** Very limited reference for cadence only. Final transcript must be synthetic industrial operator language.

### Dashboard Templates: Airframe, Volt, Vision UI, TailAdmin, AdminLTE

**Decision:** Reject.

**Reason:** They would pull the product toward generic admin-dashboard aesthetics. VesperGrid needs a custom command-center/evidence-lab interface.

**Allowed use:** Brief visual reference only.

### SCADA UI Kits: react-scada / QSimpleScada

**Decision:** Reject for implementation.

**Reason:** They are directionally relevant but too HMI-generic. We need modern industrial intelligence, not a borrowed SCADA shell.

**Allowed use:** Inspiration for density, states, and panel terminology.

### Unreal Marketplace / Fab Industrial Packs

**Decision:** Reject for now.

**Reason:** They can look beautiful, but the pipeline is heavy and marketplace licenses complicate redistribution/reproducibility.

**Allowed use:** Future rendered-only cinematic clips if time remains and licensing is reviewed.

### Bundled `image_1.png`

**Decision:** Reject.

**Reason:** It is an explanatory OSM building LOD image, not a demo visual.

## Final Asset Set To Create

Minimum display-ready evidence pack:

1. `apps/console/public/assets/vesper-field-map.png`
   - Procedural fictional operational map.
   - Must clearly show Sector 4, Gate 4, Junction E, blocked service lane, vapor drift area.

2. `demo/sector4/drone_keyframe_src_img_1042.png`
   - Synthetic drone keyframe.
   - Shows subtle vapor/thermal anomaly near container stack.

3. `demo/sector4/drone_clip_sector4_5s.mp4` or five sampled frames
   - Synthetic short clip or keyframe sequence.
   - Used to explain Qwen-VL five-frame parsing.

4. `demo/sector4/cctv_gate4_src_vid_2217.png`
   - Synthetic CCTV/security-camera frame.
   - Shows Gate 4 lane obstruction.

5. `demo/sector4/wind_sensor_src_sen_0924.png`
   - Synthetic telemetry strip.
   - Shows wind direction, pressure variance, and source UUID.

6. `demo/sector4/operator_transcript_src_txt_7781.txt`
   - Synthetic operator note.
   - Creates the deliberate route uncertainty.

7. `demo/sector4/evidence_pack.json`
   - Source registry for all evidence.

8. `demo/sector4/vlm_output_sample.json`
   - Deterministic model fallback in the same schema live Qwen-VL should produce.

9. `demo/sector4/audit_log_sample.json`
   - Explains source UUID, prompt, model output, normalized observation, candidate plan, caveat.

10. `demo/sector4/simulation_replay_sample.json`
   - Bounded route/hazard scoring over time.

## Implementation Priority

1. Polish the procedural field map.
2. Create synthetic drone and CCTV evidence.
3. Create telemetry strip and transcript.
4. Wire source preview UI.
5. Add simulation replay panel.
6. Add audit log viewer.
7. Capture hero screenshot and fallback video.

## Research Verdict Table

| Resource family | Final verdict | Why |
| --- | --- | --- |
| Synthetic/procedural assets | Strong Use | Best fit, full control, no licensing drag |
| Lucide icons | Strong Use | Already installed and visually consistent |
| ECharts | Use if needed | Strong telemetry/simulation charts, Apache 2.0 |
| ambientCG | Use if needed | CC0 textures for optional synthetic renders |
| Mermaid/diagrams.net/custom SVG | Use | Good for docs/submission diagrams |
| OBS/screen recording tools | Use | Needed for reliable fallback demo |
| Babylon/Three digital twin examples | Maybe later | Useful but not before 2D product polish |
| Reagraph/React Flow/Cytoscape | Maybe later | Evidence graph view can wait |
| OSM/OpenMapTiles/MapTiler/OpenAerialMap | Reject for MVP visuals | Real-map licensing/location complexity |
| Unsplash/Pexels/Pixabay | Reject | Stock-photo feel, not source-specific |
| Industrial/fire/CCTV/drone datasets | Reject raw UI use | Visual inconsistency and license/privacy distractions |
| Real dispatch/911 transcripts | Reject copied content | Wrong tone/privacy risk |
| Dashboard templates | Reject | Generic admin-dashboard look |
| SCADA kits | Inspiration only | Too generic/old if implemented directly |
| Unreal/Fab packs | Reject for now | Heavy pipeline and license complexity |

## Final Recommendation

The research should guide the build, not supply the visible evidence.

For VesperGrid to look serious and display-ready, the correct asset strategy is:

> Synthetic evidence, procedural maps, custom UI, tight source lineage, and only a few permissive tools behind the scenes.

This keeps the demo beautiful, coherent, legally clean, and focused on the actual winning idea: fragmented industrial evidence becoming a source-linked operational twin on AMD infrastructure.
