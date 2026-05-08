# Strategy Decision After Expert Review

## Decision

**Stay with VesperGrid, but narrow and reposition it.**

The expert review strongly validates the core idea: VesperGrid is original, memorable, and aligned with AMD MI300X hardware. The correct move is not to abandon it. The correct move is to reduce the blast radius:

- from broad "crisis response"
- to **critical infrastructure operational twin**
- focused first on **industrial safety in ports, logistics yards, and energy-adjacent facilities**

This preserves the winning thesis while removing the most dangerous liability and execution risks.

Important refinement from the latest expert feedback:

> Narrow the use case, but do not sand off the emotional stakes.

The product should not sound like an autonomous public emergency system. But it should still feel urgent: industrial incidents can shut down ports, endanger workers, and cost millions per hour.

## Why We Are Not Pivoting Away

The expert scores were directionally excellent:

- originality: 9.5/10
- competition viability: 9/10 if demo execution is smooth
- hardware alignment: very strong

The weaknesses were not about the idea being bad. They were about scope, latency, and compliance framing. Those are solvable by narrowing the product.

## What Changed

### Positioning

Old: multimodal crisis intelligence.

New: **critical infrastructure operational twin for industrial safety teams**.

This sounds more credible to judges and buyers. It avoids the impression that the product is making autonomous emergency decisions.

It should still feel high-stakes. The demo should communicate urgency through operational consequences, not through exaggerated disaster imagery.

### Demo Scenario

Old: broad harbor heat cascade / emergency response.

New: **Sector 4 Solvent Containment** in a port logistics corridor.

The incident is high-stakes but bounded: one site, one hazard, one route contradiction, one set of candidate plans.

### Architecture Scope

Old: large evidence graph, multimodal fusion, simulation, collaboration, future live operations.

New MVP:

- five sampled keyframes, not full video streaming
- Qwen-VL through vLLM ROCm with TP=1 on the single MI300X
- strict schema: Entity, Location, Hazard, Constraint
- in-memory graph/vector state for demo reliability
- CPU/vectorized simulation for MVP
- GPU-resident multimodal inference as the AMD proof
- visible route/hazard simulation as the product proof

### UX Trust Model

The UI now emphasizes:

- clickable source lineage
- explicit source UUIDs
- uncertainty ledger
- candidate plans, not directives
- human review language
- end-to-end latency and VRAM visibility

## Must-Build Demo Proof

The live demo must show at least one new evidence input being ingested and turned into structured state. Without this, judges may assume the console is scripted.

Current implementation includes a lightweight live ingest panel that posts an operator note to `/api/ingest`, appends a source-linked evidence item, and updates uncertainty. The next implementation step is replacing that deterministic synthesis with live Qwen-VL parsing for one uploaded keyframe.

The second proof is a visible simulation response. Even if the MVP simulation is CPU/vectorized, the UI should show the candidate route becoming safer than the blocked route as evidence changes.

## Final Strategic Thesis

VesperGrid should be pitched as:

> We use AMD MI300X memory and ROCm inference to turn fragmented industrial evidence into a source-linked operational twin, so infrastructure teams can understand risk, uncertainty, and candidate actions before downtime becomes disaster.

This is stronger than both the original Nemoflix direction and the first VesperGrid draft.
