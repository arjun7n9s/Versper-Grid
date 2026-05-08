# VesperGrid Master Idea Document

## Executive Vision

VesperGrid is an AI decision-support theater for critical infrastructure operators. It ingests messy multimodal evidence such as sampled drone frames, CCTV keyframes, operator notes, sensor feeds, site maps, and local constraints, then builds a source-linked operational twin that explains what is happening, what may happen next, and which candidate plan is safest.

The product is designed to make judges remember one sentence:

> VesperGrid turns raw industrial evidence into a source-linked operational twin on AMD MI300X infrastructure.

## Problem Statement

Industrial operators do not fail because they lack data. They fail because their data arrives fragmented, late, and in different formats. A drone keyframe shows heat. An operator note says a route is clear. A road camera shows congestion. A wind sensor changes the vapor drift model. Human teams must fuse all of this while downtime and safety risk compound.

Existing AI demos usually stop at captioning, chatting, or generating media. VesperGrid pushes further: multimodal perception becomes a structured decision model, and the decision model becomes a simulation.

## Market Gap

There is a missing middle between dashboards and autonomous agents:

- Dashboards show data but do not reason over uncertainty.
- Chatbots can summarize but rarely preserve operational state.
- Vision models can describe media but rarely generate action plans.
- Digital twins are powerful but often slow, expensive, and disconnected from fresh field evidence.

VesperGrid occupies that gap as a real-time multimodal operational intelligence layer.

## Innovation Thesis

The winning move is not "AI agent plus tools." The winning move is evidence-to-simulation:

1. Parse each modality with specialized models.
2. Convert model outputs into auditable entities, risks, constraints, and confidence scores.
3. Fuse those outputs into a spatial-temporal incident graph.
4. Run scenario simulations over that graph.
5. Compile action plans with uncertainty, caveats, owners, and timing.

This is memorable because the user does not watch an AI talk. They watch an industrial situation become intelligible, with every recommendation tied back to evidence.

## Track Strategy

Primary track: **Vision & Multimodal AI**.

Why this track is strongest:

- It best exploits the MI300X memory profile.
- It supports a visually unforgettable demo.
- It avoids the crowded generic agent category.
- It creates room for Qwen-VL, video embeddings, simulation, and reasoning.
- It maps directly to judging criteria: technology integration, originality, business value, and presentation clarity.

Secondary integrations:

- **Qwen challenge:** Qwen-VL/Qwen reasoning models power evidence interpretation and decision synthesis.
- **Hugging Face:** publish a lightweight Space that connects to the AMD backend and shows the public demo.

## Product Positioning

VesperGrid is for infrastructure teams that coordinate under uncertainty:

- ports and logistics
- factories and energy infrastructure
- insurance catastrophe response
- smart city operations

The premium positioning: "A critical infrastructure operational twin that is multimodal-first, source-linked, and deployable on AMD."

## Interaction Philosophy

VesperGrid avoids a generic chatbot. The UI is built around operational cognition:

- **Evidence Mesh:** every model conclusion remains tied to a source.
- **Live Twin:** risks appear spatially and temporally, not as prose alone.
- **Decision Support Synthesizer:** candidate plans include owners, ETA, impact, confidence, source lineage, and caveats.
- **Uncertainty Ledger:** the system shows what it does not know.
- **GPU Runtime:** compute is visible so AMD infrastructure feels central, not incidental.

## Visual Language

The visual design is a cinematic operations room:

- dark field-map base imagery
- industrial blues, slate neutrals, safety orange
- dense but legible panels
- no chatbot bubbles
- no generic gradient landing page
- spatial risk zones and route vectors as the main visual artifact

## Architecture Overview

```text
Field Media + Reports + Sensors
          |
          v
Ingest Gateway
          |
          v
Modality Workers
  - Qwen-VL sampled keyframe reasoning
  - speech/transcript normalization
  - OCR and document extraction
  - sensor anomaly detection
          |
          v
Evidence Graph
  - entities
  - locations
  - constraints
  - confidence
  - source lineage
          |
          v
Simulation Layer
  - spread models
  - route constraints
  - route constraints
  - bounded uncertainty
          |
          v
Decision Support Synthesizer
  - prioritized candidate plan
  - caveats
  - audit trail
  - presentation brief
          |
          v
Vesper Console + Public HF Space
```

## AMD Infrastructure Plan

Target hardware from `Specs of Cloud.txt`:

- 1x AMD MI300X (single-GPU allocation; corrected 2026-05-08)
- 192 GB VRAM
- 20 vCPU
- 240 GB RAM
- 720 GB boot NVMe
- 5 TB scratch NVMe
- Ubuntu with ROCm, vLLM, SGLang, PyTorch, Megatron, or GPT-OSS images

> Earlier drafts referenced an 8-GPU cluster. The live target is a single MI300X with 192 GB VRAM, TP=1, and 5 TB scratch storage.

Recommended quick-start image: **vLLM 0.17.1 with ROCm 7.2.0** for serving Qwen and reasoning models. Use PyTorch ROCm containers for simulation workers if vLLM image lacks scientific dependencies.

GPU allocation:

- GPU 0: Qwen-VL through vLLM ROCm with tensor parallelism set to 1
- CPU/RAM: embedding normalization, in-memory graph scoring, lightweight route/hazard simulation, and deterministic fallback

Memory strategy:

- keep large models resident instead of repeatedly loading checkpoints
- sample five keyframes per clip and submit them in one multimodal request
- keep demo graph/vector state in memory; flush asynchronously to the 5 TB scratch disk
- keep the demo scenario warm to avoid cold-start risk
- expose backpressure instead of pretending all jobs are real-time

## AI Stack

Baseline demo:

- deterministic typed FastAPI pipeline
- React console with fallback scenario
- auditable scenario objects

Competition-grade backend:

- Qwen2.5-VL or Qwen3-VL for images and sampled video frames
- Qwen reasoning model or GPT-OSS on ROCm for plan synthesis
- Whisper or faster-whisper for audio transcripts
- SigLIP/CLIP embeddings for similarity and retrieval
- CPU/vectorized simulation for MVP, with ROCm PyTorch port as Phase 2
- in-memory graph store for evidence lineage
- vLLM for ROCm inference serving

## Core Features

- Multimodal incident ingest
- Evidence graph with source lineage
- Spatial risk twin
- Bounded scenario simulation with uncertainty
- Prioritized decision-support synthesizer
- GPU-aware runtime observability
- Judge brief export
- Hugging Face public demo surface

## Differentiators

- Simulation-native rather than chatbot-native
- Multimodal evidence fusion, not single-model captioning
- Visually memorable operational twin
- AMD hardware is architecturally necessary
- Clear business use case beyond hackathon spectacle
- Auditable outputs with caveats and source references

## Engineering Roadmap

Phase 1: ship the deterministic console and API.

Phase 2: connect Qwen-VL to parse one uploaded image and five sampled video keyframes.

Phase 3: add graph storage and retrieval.

Phase 4: implement lightweight route/hazard scoring, keeping GPU simulation as a roadmap item.

Phase 5: produce exportable incident brief and HF Space.

Phase 6: harden deployment, metrics, and failure modes.

## Deployment Strategy

1. Start AMD cloud image with vLLM or ROCm.
2. Install API and console.
3. Serve Qwen-VL with tensor parallelism set to 1.
4. Start VesperGrid API on port `8742`.
5. Serve console through Vite preview, Nginx, or static hosting.
6. Publish HF Space as a public frontend that calls the AMD backend.

## Monetization Potential

VesperGrid can become a real company through:

- SaaS command-center subscriptions
- private cloud/on-prem deployments
- incident review and training simulation packages
- API access for insurance and logistics platforms
- premium compliance/audit modules

## Demo Walkthrough

1. Open VesperGrid to the Sector 4 operational twin.
2. Ingest a sampled evidence pack: one keyframe, one transcript, one sensor strip.
3. Watch evidence items become source-linked structured signals.
4. Click a candidate plan and trace it back to the exact source UUID.
5. Show the uncertainty ledger flagging the route contradiction.
6. Show MI300X runtime allocation.
7. Export the judge brief.
8. End with the thesis: AMD enables a live multimodal operational twin, not another wrapper.

## Storytelling Strategy For Judges

Start with a human moment:

"A port operator has 18 minutes, three incompatible evidence streams, and no single operational truth."

Then show the system:

"VesperGrid turns that chaos into a source-linked operational twin, with every candidate plan tied to evidence and uncertainty."

Close with the business:

"This can serve ports, logistics yards, factories, and energy infrastructure."

## Why This Deserves To Win

VesperGrid deserves to win because it is original, demoable, technically aligned with AMD, and commercially plausible. It uses the hardware for a reason: large multimodal models, video-frame batching, high-memory graph state, and simulation workloads. It has emotional weight, visual impact, and a clear path from hackathon prototype to startup.
