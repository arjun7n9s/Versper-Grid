"""RAG Incident Memory — ChromaDB + sentence-transformers.

Provides:
- `store_incident(scenario)`  — embed + upsert a completed scenario into ChromaDB
- `retrieve_similar(text, n)` — retrieve the n most similar past incidents
- `format_precedents(hits)`   — format retrieved hits as a VLM prompt injection

At startup, seeds the collection with 8 synthetic historical LNG terminal
incidents so the system has meaningful context even before the first live ingest.

Dependencies: chromadb, sentence-transformers (both CPU-only, no GPU needed).
If either is unavailable the module degrades gracefully — all public functions
return empty results and the pipeline continues without RAG context.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_collection = None
_embedder = None
_COLLECTION_NAME = "vespergrid_incidents"

# ─── Synthetic seed incidents ─────────────────────────────────────────────────
_SEED_INCIDENTS = [
    {
        "id": "hist-001",
        "text": (
            "LNG terminal Tank A-2 flange failure. Gas plume detected by CCTV south "
            "at 03:40. Workers evacuated via north gate. Foam unit staged at NE perimeter. "
            "Incident resolved in 47 minutes. Key action: immediate downwind evacuation."
        ),
        "outcome": "contained",
        "location": "Tank A-2, North Sector",
        "severity": "critical",
    },
    {
        "id": "hist-002",
        "text": (
            "Vapor drift incident near loading bay 7. Wind speed 6.2 m/s NW. "
            "Gas sensor crossed 18 ppm LEL threshold. Supervisors dispatched for "
            "confirmation. No ignition. Resolved by halting tanker operations."
        ),
        "outcome": "contained",
        "location": "Loading Bay 7",
        "severity": "elevated",
    },
    {
        "id": "hist-003",
        "text": (
            "Hydrant pressure failure during drill at Gate 4. Route obstruction "
            "forced containment team to reroute through Junction E. Tanker relay "
            "required to compensate for lost pressure. Drill completed with delay."
        ),
        "outcome": "resolved",
        "location": "Gate 4, South Sector",
        "severity": "watch",
    },
    {
        "id": "hist-004",
        "text": (
            "Cross-camera contradiction: drone footage showed clear zone while CCTV "
            "ground level detected vehicle queue blocking emergency route. Manual "
            "verification required before dispatch. Route confirmed blocked."
        ),
        "outcome": "verified",
        "location": "Junction E",
        "severity": "elevated",
    },
    {
        "id": "hist-005",
        "text": (
            "Solvent spill in storage lane adjacent to fuel tanks. Thermal signature "
            "on drone keyframe confirmed. Wind at 21 km/h pushing vapor toward "
            "fuel-adjacent storage. Access held until wind dropped below 10 km/h."
        ),
        "outcome": "contained",
        "location": "Storage Lane 3, West Sector",
        "severity": "critical",
    },
    {
        "id": "hist-006",
        "text": (
            "Sensor anomaly flagged by automated system: gas ppm rose 4x in 90 "
            "seconds without threshold breach. IsolationForest model flagged reading "
            "as out-of-distribution. Supervisor dispatched. False positive — "
            "sensor calibration drift confirmed."
        ),
        "outcome": "false_positive",
        "location": "Sensor Array B, East Sector",
        "severity": "watch",
    },
    {
        "id": "hist-007",
        "text": (
            "Night-shift gas leak at Tank B-1. Drone D1 orbiting at 22m confirmed "
            "visible plume correlating with ground CCTV observation. Emergency "
            "broadcast issued. All workers evacuated downwind corridor within 8 min."
        ),
        "outcome": "evacuated",
        "location": "Tank B-1, North Sector",
        "severity": "critical",
    },
    {
        "id": "hist-008",
        "text": (
            "Worker voice report of strong gas odor in Sector 5. Cross-checked with "
            "sensor trace showing 12 ppm — below LEL threshold but rising. Wind "
            "direction NW at 3.7 m/s. Classified as elevated watch. Tanker relay "
            "pre-staged as precaution."
        ),
        "outcome": "monitored",
        "location": "Sector 5, Downwind Corridor",
        "severity": "elevated",
    },
]


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("SentenceTransformer loaded: all-MiniLM-L6-v2")
    except Exception as exc:
        logger.warning("sentence-transformers unavailable: %s — RAG disabled", exc)
        _embedder = None
    return _embedder


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        _client = chromadb.Client()
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        _seed_collection(_collection)
        logger.info("ChromaDB collection ready: %d documents", _collection.count())
    except Exception as exc:
        logger.warning("ChromaDB unavailable: %s — RAG disabled", exc)
        _collection = None
    return _collection


def _embed(texts: list[str]) -> list[list[float]]:
    emb = _get_embedder()
    if emb is None:
        return []
    try:
        vecs = emb.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vecs]
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return []


def _seed_collection(collection) -> None:
    existing = set(collection.get()["ids"])
    to_add = [s for s in _SEED_INCIDENTS if s["id"] not in existing]
    if not to_add:
        return
    texts = [s["text"] for s in to_add]
    embeddings = _embed(texts)
    if not embeddings:
        return
    collection.add(
        ids=[s["id"] for s in to_add],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"location": s["location"], "severity": s["severity"], "outcome": s["outcome"]} for s in to_add],
    )
    logger.info("Seeded %d historical incidents into ChromaDB", len(to_add))


# ─── Public API ───────────────────────────────────────────────────────────────

def store_incident(scenario_dict: dict) -> bool:
    """Embed and upsert a completed scenario into the incident memory."""
    collection = _get_collection()
    if collection is None:
        return False
    try:
        text = (
            f"{scenario_dict.get('incident','')}. "
            f"{scenario_dict.get('location','')}. "
            f"{scenario_dict.get('thesis','')} "
            + " ".join(scenario_dict.get("brief", []))
        )
        doc_id = "live-" + hashlib.md5(text.encode()).hexdigest()[:12]
        embeddings = _embed([text])
        if not embeddings:
            return False
        collection.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[text],
            metadatas=[{
                "location": scenario_dict.get("location", ""),
                "severity": "critical" if scenario_dict.get("confidence", 0) > 0.8 else "elevated",
                "outcome": "live",
            }],
        )
        logger.info("Stored live incident in memory: %s", doc_id)
        return True
    except Exception as exc:
        logger.warning("Failed to store incident: %s", exc)
        return False


def retrieve_similar(query_text: str, n: int = 2) -> list[dict[str, Any]]:
    """Return the n most similar past incidents to the query text."""
    collection = _get_collection()
    if collection is None:
        return []
    try:
        embeddings = _embed([query_text])
        if not embeddings:
            return []
        results = collection.query(
            query_embeddings=embeddings,
            n_results=min(n, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "location": meta.get("location", ""),
                "severity": meta.get("severity", ""),
                "outcome": meta.get("outcome", ""),
                "similarity": round(1.0 - dist, 3),
            })
        return hits
    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        return []


def format_precedents(hits: list[dict[str, Any]]) -> str:
    """Format retrieved hits as a concise historical precedent block for VLM injection."""
    if not hits:
        return ""
    lines = ["Historical precedents from similar incidents:"]
    for i, h in enumerate(hits, 1):
        lines.append(
            f"{i}. [{h['severity'].upper()} | {h['location']} | outcome={h['outcome']}] "
            f"{h['text']}"
        )
    return "\n".join(lines)
