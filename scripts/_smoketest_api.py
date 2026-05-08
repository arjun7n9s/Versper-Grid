import json
from fastapi.testclient import TestClient
from vespergrid.main import app

c = TestClient(app)
print("--- /api/health ---")
print(json.dumps(c.get("/api/health").json(), indent=2)[:400])

print("--- /api/scenarios/sector-4-containment ---")
r = c.get("/api/scenarios/sector-4-containment")
print("status:", r.status_code, "evidence:", len(r.json()["evidence"]))

print("--- POST /api/ingest ---")
r = c.post(
    "/api/ingest",
    json={
        "location": "X",
        "field_notes": "live note about Gate 4 queue",
        "media_count": 3,
        "sensor_count": 2,
    },
)
job = r.json()
print(job)

print("--- POST /api/ingest/{id}/await ---")
r = c.post(f"/api/ingest/{job['job_id']}/await", params={"timeout_seconds": 5})
snap = r.json()
print("status:", snap["status"], "backend:", snap["backend"])
print("events:", [(e["stage"], round(e["progress"], 2)) for e in snap["events"]])
print("result evidence count:", len(snap["result"]["evidence"]))

print("--- GET /api/ingest/{id} (snapshot after completion) ---")
r = c.get(f"/api/ingest/{job['job_id']}")
print("status:", r.json()["status"])
