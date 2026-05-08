# VesperGrid Execution Roadmap

## Milestone 0: Reinvention Complete

Status: complete.

- New identity, product thesis, and track strategy
- New monorepo structure
- New React console
- New FastAPI scenario API
- New docs and AMD deployment plan
- Expert review incorporated: VesperGrid stays, but narrows to critical infrastructure operational twins.

## Milestone 1: Demo-Credible MVP

Priority: highest.

- Run console and API locally
- Add one real image/report ingest path
- Preserve source lineage in responses
- Render uncertainty ledger and candidate plans
- Add visible route/hazard simulation replay panel
- Add source preview cards for lineage clicks
- Export judge brief as Markdown
- Add latency and GPU telemetry placeholders with documented swap-in points

## Milestone 2: Multimodal Model Integration

Priority: highest.

- Serve Qwen-VL on ROCm using vLLM with TP=1 on the single MI300X
- Parse five sampled frames from a short clip
- Add a secondary unseen test image for live judge defense
- Convert model outputs into evidence entities
- Add confidence scoring and disagreement handling
- Cache outputs to avoid repeated inference during demo

## Milestone 3: Evidence Graph

Priority: high.

- Define graph schema: entity, source, location, hazard, constraint, action
- Store graph in SQLite/DuckDB for MVP or Neo4j/Arango for production path
- Add source-to-claim drill-down UI
- Keep MVP graph in memory with strict Entity, Location, Hazard, Constraint records

## Milestone 4: Simulation Layer

Priority: high.

- Implement simple route-risk and hazard scoring
- Keep MVP simulation CPU/vectorized; document ROCm PyTorch port as Phase 2
- Make simulation visually prominent without overclaiming GPU physics
- Visualize scenario alternatives in the console
- Expose uncertainty bands rather than single predictions

## Milestone 5: Public Submission Polish

Priority: high.

- Create Hugging Face Space frontend or proxy
- Prepare slide deck and short demo script
- Record a 90-second backup demo
- Publish technical write-up
- Prepare build-in-public updates

## Priority Matrix

| Feature | Demo Impact | Technical Depth | Risk | Priority |
| --- | --- | --- | --- | --- |
| Live twin UI | Very high | Medium | Low | P0 |
| Qwen-VL image parsing | High | High | Medium | P0 |
| Evidence lineage | High | Medium | Low | P0 |
| GPU telemetry | Medium | Medium | Low | P1 |
| Video-frame batching | High | High | Medium | P1 |
| Route/hazard scoring | Very high | Medium | Low | P1 |
| Multi-user collaboration | Medium | High | High | P3 |
| Full compliance suite | Low for demo | High | High | P3 |

## Sprint Structure

Sprint 1: stabilize local app and docs.

Sprint 2: deploy to AMD cloud, verify ROCm, install inference server.

Sprint 3: wire Qwen-VL evidence parsing and caching.

Sprint 4: add simulation, brief export, and telemetry.

Sprint 5: polish visuals, create HF Space, record demo, refine pitch.

## Demo Preparation Strategy

- Keep one deterministic scenario warm and always available.
- Prepare one real evidence pack that can be parsed live.
- Show the deterministic scenario first, then reveal one live ingest/parsing step.
- Pace the reveal: raw evidence, graph structuring, simulation response, candidate plan.
- Keep terminal commands short and pre-tested.
- Make the final judging narrative about operational transformation, not implementation trivia.

## Contingency Plans

- If Qwen-VL fails on ROCm: use precomputed model outputs and clearly label the integration path.
- If GPU provisioning fails: run local deterministic console plus architecture walkthrough and backup recording.
- If video parsing is slow: parse still frames and present temporal aggregation as next-stage.
- If simulation is not GPU-ready: say it is CPU/vectorized MVP and emphasize Qwen-VL GPU-resident inference.
- If live image parsing fails: use precomputed VLM JSON, but still show source lineage and simulation response.
- If HF Space cannot reach backend: deploy static console with recorded scenario and link to repo/API docs.
