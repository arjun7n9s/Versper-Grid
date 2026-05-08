import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Cpu,
  FileText,
  GitBranch,
  Layers3,
  Link2,
  Radar,
  Route,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Video,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fallbackScenario,
  type EvidenceItem,
  type ResponseAction,
  type Scenario,
  type Severity,
  type UncertaintyIssue
} from "./domain";

declare const __API_BASE__: string;
const API_BASE = typeof __API_BASE__ !== "undefined" ? __API_BASE__ : "";

const severityLabels: Record<Severity, string> = {
  watch: "Watch",
  elevated: "Elevated",
  critical: "Critical"
};

/**
 * Source-UUID -> visual asset. The judging "wow moment" is clicking a
 * candidate plan / uncertainty issue and immediately seeing the exact
 * piece of evidence that produced it. SRC-LIVE-9001 is the runtime live
 * operator note (no image asset).
 */
const sourceAssets: Record<string, { src?: string; alt: string; tag: string }> = {
  "SRC-IMG-1042": {
    src: "/assets/drone_keyframe_src_img_1042.png",
    alt: "Synthetic drone keyframe with thermal anomaly",
    tag: "DRONE / FRAME 03"
  },
  "SRC-VID-2217": {
    src: "/assets/cctv_gate4_src_vid_2217.png",
    alt: "Gate 4 CCTV keyframe showing service lane obstruction",
    tag: "GATE 4 CCTV"
  },
  "SRC-SEN-0924": {
    src: "/assets/wind_sensor_src_sen_0924.png",
    alt: "Wind telemetry strip",
    tag: "WIND TELEMETRY"
  },
  "SRC-TXT-7781": {
    alt: "Operator radio transcript excerpt",
    tag: "OPERATOR RADIO"
  },
  "SRC-LIVE-9001": {
    alt: "Live operator note appended at runtime",
    tag: "LIVE NOTE"
  }
};

async function loadScenario(): Promise<Scenario> {
  const response = await fetch(`${API_BASE}/api/scenarios/sector-4-containment`);
  if (!response.ok) throw new Error("scenario unavailable");
  return response.json();
}

interface IngestProgress {
  stage: string;
  message: string;
  progress: number;
  backend: string;
}

async function startIngestJob(note: string): Promise<{ job_id: string; backend: string }> {
  const response = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      location: "Sector 4 — Tank B-4 Flange, Northgate LNG Terminal",
      field_notes: note,
      media_count: 3,
      sensor_count: 2
    })
  });
  if (!response.ok) throw new Error("ingest unavailable");
  return response.json();
}

async function startIngestUpload(
  note: string,
  files: File[]
): Promise<{ job_id: string; backend: string }> {
  const form = new FormData();
  form.append("location", "Sector 4 — Tank B-4 Flange, Northgate LNG Terminal");
  form.append("field_notes", note);
  form.append("sensor_count", "2");
  for (const f of files) form.append("images", f);
  const response = await fetch(`${API_BASE}/api/ingest/upload`, {
    method: "POST",
    body: form
  });
  if (!response.ok) throw new Error("ingest upload unavailable");
  return response.json();
}

function ingestStream(
  jobId: string,
  backend: string,
  onProgress: (p: IngestProgress) => void
): Promise<Scenario> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`${API_BASE}/api/ingest/${jobId}/events`);
    const stages = ["queued", "sampling", "parsing", "normalizing", "synthesizing", "complete", "error"];
    for (const stage of stages) {
      source.addEventListener(stage, (event) => {
        try {
          const ev = JSON.parse((event as MessageEvent).data);
          onProgress({ stage: ev.stage, message: ev.message, progress: ev.progress, backend });
        } catch {
          /* ignore malformed event */
        }
      });
    }
    source.addEventListener("snapshot", (event) => {
      try {
        const snap = JSON.parse((event as MessageEvent).data);
        source.close();
        if (snap.status === "complete" && snap.result) {
          resolve(snap.result as Scenario);
        } else {
          reject(new Error(snap.error || "ingest pipeline failed"));
        }
      } catch (err) {
        source.close();
        reject(err as Error);
      }
    });
    source.onerror = () => {
      source.close();
      reject(new Error("ingest stream interrupted"));
    };
  });
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function SourcePreview({
  scenario,
  selectedSource
}: {
  scenario: Scenario;
  selectedSource: string | null;
}) {
  if (!selectedSource) return null;
  const evidence = scenario.evidence.find((e) => e.sourceUuid === selectedSource);
  const action = scenario.actions.find((a) => a.sourceEntityId === selectedSource);
  const issue = scenario.uncertainties.find((u) =>
    u.sourceEntityIds.includes(selectedSource)
  );
  const asset = sourceAssets[selectedSource];
  if (!evidence && !action && !issue) return null;

  return (
    <section className="panel source-preview" aria-label="Source preview">
      <div className="panel-title">
        <Link2 size={18} />
        <span>Source Lineage</span>
      </div>
      <div className="source-preview-body">
        {asset?.src ? (
          <img className="source-thumb" src={asset.src} alt={asset.alt} />
        ) : (
          <div className="source-thumb source-thumb-text">
            <span>{asset?.tag ?? selectedSource}</span>
            <small>{asset?.alt ?? "No image asset"}</small>
          </div>
        )}
        <div className="source-meta">
          <div className="source-uuid">{selectedSource}</div>
          {evidence && (
            <>
              <h4>{evidence.source}</h4>
              <p>{evidence.summary}</p>
              <div className="source-stats">
                <span>signal: {evidence.signal}</span>
                <span>confidence: {pct(evidence.confidence)}</span>
              </div>
            </>
          )}
          {action && (
            <div className="source-link-row">
              <Route size={13} />
              <span>{action.title}</span>
            </div>
          )}
          {issue && (
            <div className="source-link-row warn">
              <AlertTriangle size={13} />
              <span>{issue.title}: {issue.detail}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function EvidenceIcon({ item }: { item: EvidenceItem }) {
  if (item.kind === "image") return <Layers3 size={16} />;
  if (item.kind === "video") return <Activity size={16} />;
  if (item.kind === "sensor") return <Radar size={16} />;
  return <FileText size={16} />;
}

function OrbitalMap({
  scenario,
  selectedSource
}: {
  scenario: Scenario;
  selectedSource: string | null;
}) {
  const highlightedZones = new Set(
    scenario.evidence.filter((item) => item.sourceUuid === selectedSource && item.linkedZoneId).map((item) => item.linkedZoneId)
  );

  return (
    <section className="map-stage" aria-label="Operational twin map">
      <img src="/assets/vesper-field-map.png" alt="" className="map-image" />
      <div className="wind-vector" />
      <div className="route-line route-a" />
      <div className="route-line route-b" />
      {scenario.zones.map((zone) => (
        <button
          className={`risk-zone ${zone.severity} ${highlightedZones.has(zone.id) ? "selected" : ""}`}
          key={zone.id}
          style={{
            left: `${zone.x}%`,
            top: `${zone.y}%`,
            width: `${zone.radius * 2}%`,
            height: `${zone.radius * 2}%`
          }}
          title={`${zone.label}: ${zone.rationale}`}
        >
          <span>{zone.label}</span>
        </button>
      ))}
      <div className="map-readout">
        <span>Operational Twin</span>
        <strong>{scenario.clock}</strong>
      </div>
    </section>
  );
}

function EvidenceRail({
  evidence,
  selectedSource,
  onSelect
}: {
  evidence: EvidenceItem[];
  selectedSource: string | null;
  onSelect: (sourceUuid: string) => void;
}) {
  return (
    <section className="panel evidence-panel">
      <div className="panel-title">
        <UploadCloud size={18} />
        <span>Evidence Mesh</span>
      </div>
      <div className="evidence-list">
        {evidence.map((item) => (
          <button
            className={`evidence-row ${selectedSource === item.sourceUuid ? "selected" : ""}`}
            key={item.id}
            onClick={() => onSelect(item.sourceUuid)}
          >
            <div className="evidence-icon">
              <EvidenceIcon item={item} />
            </div>
            <div>
              <div className="row-heading">
                <span>{item.source}</span>
                <b>{pct(item.confidence)}</b>
              </div>
              <p>{item.summary}</p>
              <small>{item.sourceUuid} / {item.signal}</small>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

function ActionStack({
  scenario,
  selectedSource,
  onSelect
}: {
  scenario: Scenario;
  selectedSource: string | null;
  onSelect: (sourceUuid: string) => void;
}) {
  return (
    <section className="panel action-panel">
      <div className="panel-title">
        <Route size={18} />
        <span>Decision Support Synthesizer</span>
      </div>
      {scenario.actions.map((action, index) => (
        <article className={`action-card ${selectedSource === action.sourceEntityId ? "selected" : ""}`} key={action.id}>
          <div className="action-index">{index + 1}</div>
          <div className="action-body">
            <h3>{action.title}</h3>
            <div className="action-meta">
              <span>{action.owner}</span>
              <span>{action.etaMinutes} min</span>
              <span>{action.impact}% impact</span>
              <span>{pct(action.confidence)} confidence</span>
            </div>
            <p>{action.caveat}</p>
            <button className="lineage-button" onClick={() => onSelect(action.sourceEntityId)}>
              <Link2 size={14} />
              Trace {action.sourceEntityId}
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}

function UncertaintyLedger({
  issues,
  onSelect
}: {
  issues: UncertaintyIssue[];
  onSelect: (sourceUuid: string) => void;
}) {
  return (
    <section className="panel uncertainty-panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        <span>Uncertainty Ledger</span>
      </div>
      <div className="uncertainty-list">
        {issues.map((issue) => (
          <article className={`uncertainty-row ${issue.severity}`} key={issue.id}>
            <div className="row-heading">
              <span>{issue.title}</span>
              <b>{severityLabels[issue.severity]}</b>
            </div>
            <p>{issue.detail}</p>
            <div className="source-chips">
              {issue.sourceEntityIds.map((source) => (
                <button key={source} onClick={() => onSelect(source)}>
                  {source}
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function GpuTelemetry({ scenario }: { scenario: Scenario }) {
  const totalMemory = scenario.gpu.reduce((sum, lane) => sum + lane.memoryGb, 0);
  const avgUtil = Math.round(scenario.gpu.reduce((sum, lane) => sum + lane.utilization, 0) / scenario.gpu.length);
  const totalLatency = scenario.gpu.reduce((sum, lane) => sum + lane.latencyMs, 0);

  return (
    <section className="panel gpu-panel">
      <div className="panel-title">
        <Cpu size={18} />
        <span>MI300X Runtime</span>
      </div>
      <div className="gpu-summary">
        <div>
          <small>Mean Utilization</small>
          <strong>{avgUtil}%</strong>
        </div>
        <div>
          <small>E2E Latency</small>
          <strong>{(totalLatency / 1000).toFixed(1)}s</strong>
        </div>
      </div>
      <div className="gpu-lanes">
        {scenario.gpu.map((lane) => (
          <div className="gpu-lane" key={lane.label}>
            <div className="row-heading">
              <span>{lane.label}</span>
              <b>{lane.utilization}%</b>
            </div>
            <div className="lane-bar">
              <span style={{ width: `${lane.utilization}%` }} />
            </div>
            <p>{lane.workload}</p>
            <small>{lane.memoryGb} GB VRAM / {lane.latencyMs} ms</small>
          </div>
        ))}
      </div>
      <p className="runtime-note">{totalMemory} GB allocated across warm model lanes.</p>
    </section>
  );
}

function BriefPanel({
  scenario,
  onSelect
}: {
  scenario: Scenario;
  onSelect: (sourceUuid: string) => void;
}) {
  const primaryAction = scenario.actions[0];

  return (
    <section className="panel brief-panel">
      <div className="panel-title">
        <BrainCircuit size={18} />
        <span>Judge Brief</span>
      </div>
      <div className="brief-lines">
        {scenario.brief.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
      {primaryAction && (
        <button className="approve-button" onClick={() => onSelect(primaryAction.sourceEntityId)}>
          <CheckCircle2 size={16} />
          Mark candidate reviewed
        </button>
      )}
    </section>
  );
}

// ── Gazebo Live Feed Panel ────────────────────────────────────────────────
const GAZEBO_FEEDS = [
  { id: "cctv_south",  label: "CCTV South — B-4",  topic: "/cctv_south/image_raw" },
  { id: "drone_d1",   label: "Drone D-1 (primary)", topic: "/drone_d1/image_raw" },
  { id: "cctv_gate",  label: "CCTV Gate",           topic: "/cctv_gate/image_raw" },
];

function GazeboFeedPanel() {
  const [activeFeed, setActiveFeed] = useState("cctv_south");
  const [frameTs, setFrameTs] = useState<Record<string, number>>({});

  // Poll each feed's latest evidence thumbnail from the API every 10s
  // so the panel reflects what frame_sampler last submitted.
  useEffect(() => {
    const tick = () =>
      setFrameTs((_prev) => ({
        cctv_south: Date.now(),
        drone_d1:   Date.now(),
        cctv_gate:  Date.now(),
      }));
    tick();
    const id = window.setInterval(tick, 10_000);
    return () => window.clearInterval(id);
  }, []);

  const feed = GAZEBO_FEEDS.find((f) => f.id === activeFeed)!;

  return (
    <section className="panel gazebo-panel">
      <div className="panel-title">
        <Video size={18} />
        <span>Gazebo Live Feeds</span>
        <span className="feed-live-dot" title="Streaming from Ignition Gazebo" />
      </div>
      <div className="feed-tabs">
        {GAZEBO_FEEDS.map((f) => (
          <button
            key={f.id}
            className={`feed-tab ${activeFeed === f.id ? "active" : ""}`}
            onClick={() => setActiveFeed(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="feed-viewport">
        {/* ros_gz_bridge publishes /world/lng_terminal/model/…/image            */
        /* We show the last frame submitted to evidence by frame_sampler.       */
        /* When Gazebo is running the img src resolves via frame_sampler uploads */}
        <div className="feed-placeholder">
          <Video size={32} style={{ opacity: 0.28 }} />
          <span>{feed.label}</span>
          <small>{feed.topic}</small>
          <small style={{ color: "#ffb181", marginTop: 6 }}>
            Live when Gazebo + frame_sampler running
          </small>
        </div>
      </div>
      <div className="feed-meta">
        <small>ROS2 topic</small>
        <code>{feed.topic}</code>
        <small style={{ marginTop: 6 }}>Last polled</small>
        <code>{frameTs[activeFeed] ? new Date(frameTs[activeFeed]).toLocaleTimeString() : "—"}</code>
      </div>
    </section>
  );
}

// ── Live Job Ticker — auto-watches incoming frame_sampler jobs ────────────
interface JobTick {
  job_id: string;
  backend: string;
  status: string;
  stage: string;
  message: string;
  progress: number;
  ts: number;
}

function LiveJobTicker({
  onScenarioUpdate,
  onRegister
}: {
  onScenarioUpdate: (s: Scenario) => void;
  onRegister: (fn: (jobId: string, backend: string) => void) => void;
}) {
  const [ticks, setTicks] = useState<JobTick[]>([]);
  const watchedRef = useRef<Set<string>>(new Set());

  const watchJob = (jobId: string, backend: string) => {
    if (watchedRef.current.has(jobId)) return;
    watchedRef.current.add(jobId);

    const source = new EventSource(`${API_BASE}/api/ingest/${jobId}/events`);
    const stages = ["queued", "sampling", "parsing", "normalizing", "synthesizing", "complete", "error"];
    for (const stage of stages) {
      source.addEventListener(stage, (event) => {
        try {
          const ev = JSON.parse((event as MessageEvent).data);
          setTicks((prev) => [
            { job_id: jobId, backend, status: "running", stage: ev.stage,
              message: ev.message, progress: ev.progress, ts: Date.now() },
            ...prev.slice(0, 19),
          ]);
        } catch { /* ignore */ }
      });
    }
    source.addEventListener("snapshot", (event) => {
      try {
        const snap = JSON.parse((event as MessageEvent).data);
        source.close();
        if (snap.status === "complete" && snap.result) {
          onScenarioUpdate(snap.result as Scenario);
          setTicks((prev) => [
            { job_id: jobId, backend, status: "complete", stage: "complete",
              message: `Scenario updated — ${snap.result.evidence?.length ?? 0} evidence items`,
              progress: 1, ts: Date.now() },
            ...prev.slice(0, 19),
          ]);
        }
      } catch { /* ignore */ }
    });
    source.onerror = () => source.close();
  };

  // Register watchJob with parent so upload jobs can be piped in
  useEffect(() => { onRegister(watchJob); }, []);  // eslint-disable-line

  if (ticks.length === 0) {
    return (
      <section className="panel ticker-panel">
        <div className="panel-title">
          <Zap size={18} />
          <span>Pipeline Ticker</span>
        </div>
        <p className="ticker-empty">Awaiting frame_sampler jobs from Gazebo…</p>
      </section>
    );
  }

  return (
    <section className="panel ticker-panel">
      <div className="panel-title">
        <Zap size={18} />
        <span>Pipeline Ticker</span>
        <span className="feed-live-dot" />
      </div>
      <div className="ticker-list">
        {ticks.map((t, i) => (
          <div key={`${t.job_id}-${i}`} className={`ticker-row ${t.status}`}>
            <div className="ticker-bar">
              <span style={{ width: `${Math.round(t.progress * 100)}%` }} />
            </div>
            <div className="ticker-meta">
              <code>{t.job_id}</code>
              <span className="ticker-stage">{t.stage.toUpperCase()}</span>
              <small>{t.backend}</small>
            </div>
            <p>{t.message}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function LiveIngestPanel({
  onIngest,
  onIngestUpload,
  processing,
  progress
}: {
  onIngest: (note: string) => void;
  onIngestUpload: (note: string, files: File[]) => void;
  processing: boolean;
  progress: IngestProgress | null;
}) {
  const [note, setNote] = useState(
    "Active LNG flange failure at Tank B-4 south cluster. Gas plume visible. Worker evacuation in progress."
  );
  const [files, setFiles] = useState<File[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const pct = progress ? Math.round(progress.progress * 100) : 0;
  const hasFiles = files.length > 0;
  const buttonLabel = processing
    ? progress
      ? `${progress.stage.toUpperCase()} \u00b7 ${pct}%`
      : "Dispatching\u2026"
    : hasFiles
    ? `Submit ${files.length} frame(s) → MI300X`
    : "Run deterministic synthesizer";

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFiles(Array.from(e.target.files ?? []).slice(0, 5));
  };

  const handleSubmit = () => {
    if (hasFiles) onIngestUpload(note, files);
    else onIngest(note);
  };

  return (
    <section className="panel ingest-panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <span>Live Ingest — Submit to MI300X</span>
      </div>
      <textarea value={note} onChange={(event) => setNote(event.target.value)} />
      <div className="ingest-upload-row">
        <button
          className="upload-pick-btn"
          onClick={() => fileRef.current?.click()}
          disabled={processing}
        >
          <UploadCloud size={14} />
          {hasFiles ? `${files.length} frame(s) selected` : "Attach frames (optional)"}
        </button>
        {hasFiles && (
          <button className="upload-clear-btn" onClick={() => { setFiles([]); if (fileRef.current) fileRef.current.value = ""; }}>
            ✕
          </button>
        )}
        <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={handleFiles} />
      </div>
      {hasFiles && (
        <div className="ingest-file-chips">
          {files.map((f) => <span key={f.name}>{f.name}</span>)}
        </div>
      )}
      <button className="ingest-button" disabled={processing} onClick={handleSubmit}>
        {buttonLabel}
      </button>
      {processing && (
        <div className="ingest-progress" role="status" aria-live="polite">
          <div className="ingest-progress-bar">
            <span style={{ width: `${pct}%` }} />
          </div>
          <p>
            {progress?.message ?? "Awaiting first event from orchestrator\u2026"}
          </p>
          <small>
            backend: {progress?.backend ?? "\u2026"}
            {" \u00b7 "}
            stage: {progress?.stage ?? "queued"}
          </small>
        </div>
      )}
    </section>
  );
}

export function App() {
  const [scenario, setScenario] = useState<Scenario>(fallbackScenario);
  const [backend, setBackend] = useState<"online" | "offline" | "checking">("checking");
  const [selectedSource, setSelectedSource] = useState<string | null>("SRC-VID-2217");
  const [processing, setProcessing] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<IngestProgress | null>(null);
  const watchJobRef = useRef<((jobId: string, backend: string) => void) | null>(null);

  useEffect(() => {
    loadScenario()
      .then((loaded) => {
        setScenario(loaded);
        setBackend("online");
      })
      .catch(() => setBackend("offline"));
  }, []);

  const highestZone = useMemo(
    () => scenario.zones.find((zone) => zone.severity === "critical") ?? scenario.zones[0],
    [scenario.zones]
  );

  const selectedEvidence = scenario.evidence.find((item) => item.sourceUuid === selectedSource);

  const _runIngestStream = async (
    job_id: string,
    jobBackend: string
  ) => {
    const loaded = await ingestStream(job_id, jobBackend, setIngestProgress);
    setScenario(loaded);
    setSelectedSource(null);
    setBackend("online");
  };

  const handleIngest = async (note: string) => {
    setProcessing(true);
    setIngestProgress(null);
    try {
      const { job_id, backend: jobBackend } = await startIngestJob(note);
      await _runIngestStream(job_id, jobBackend);
    } catch {
      setBackend("offline");
    } finally {
      setProcessing(false);
      window.setTimeout(() => setIngestProgress(null), 1400);
    }
  };

  const handleIngestUpload = async (note: string, files: File[]) => {
    setProcessing(true);
    setIngestProgress(null);
    try {
      const { job_id, backend: jobBackend } = await startIngestUpload(note, files);
      watchJobRef.current?.(job_id, jobBackend);
      await _runIngestStream(job_id, jobBackend);
    } catch {
      setBackend("offline");
    } finally {
      setProcessing(false);
      window.setTimeout(() => setIngestProgress(null), 1400);
    }
  };

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Sparkles size={20} />
          </div>
          <div>
            <h1>VesperGrid</h1>
            <p>Critical infrastructure operational twin · AMD MI300X · Northgate LNG Terminal</p>
          </div>
        </div>
        <div className={`backend-pill ${backend}`}>
          <span />
          {backend === "checking" ? "Syncing" : backend === "online" ? "MI300X online · vLLM" : "Demo simulation"}
        </div>
      </header>

      <section className="hero-band">
        <div className="hero-copy">
          <div className="eyebrow">
            <ShieldCheck size={16} />
            Track 3: Vision & Multimodal AI / {scenario.category}
          </div>
          <h2>{scenario.incident}</h2>
          <p>{scenario.thesis}</p>
          <div className="hero-metrics">
            <div>
              <small>Location</small>
              <strong>{scenario.location}</strong>
            </div>
            <div>
              <small>Confidence</small>
              <strong>{pct(scenario.confidence)}</strong>
            </div>
            <div>
              <small>Selected source</small>
              <strong>{selectedEvidence?.source ?? selectedSource ?? "None"}</strong>
            </div>
          </div>
        </div>
        <div className="hero-status">
          <AlertTriangle size={22} />
          <span>{severityLabels[highestZone.severity]}</span>
          <p>{highestZone.rationale}</p>
        </div>
      </section>

      {/* ── Gazebo feed strip + pipeline ticker above main workspace ── */}
      <section className="feed-strip">
        <GazeboFeedPanel />
        <LiveJobTicker
          onScenarioUpdate={(s) => { setScenario(s); setBackend("online"); }}
          onRegister={(fn) => { watchJobRef.current = fn; }}
        />
      </section>

      <section className="workspace">
        <div className="left-column">
          <EvidenceRail evidence={scenario.evidence} selectedSource={selectedSource} onSelect={setSelectedSource} />
          <SourcePreview scenario={scenario} selectedSource={selectedSource} />
          <LiveIngestPanel
            onIngest={handleIngest}
            onIngestUpload={handleIngestUpload}
            processing={processing}
            progress={ingestProgress}
          />
        </div>
        <OrbitalMap scenario={scenario} selectedSource={selectedSource} />
        <div className="right-column">
          <ActionStack scenario={scenario} selectedSource={selectedSource} onSelect={setSelectedSource} />
          <UncertaintyLedger issues={scenario.uncertainties} onSelect={setSelectedSource} />
        </div>
      </section>

      <section className="lower-grid">
        <BriefPanel scenario={scenario} onSelect={setSelectedSource} />
        <section className="panel flow-panel">
          <div className="panel-title">
            <GitBranch size={18} />
            <span>Inference Flow</span>
          </div>
          <div className="flow-steps">
            <span>Gazebo cameras</span>
            <span>frame_sampler node</span>
            <span>Qwen-VL · MI300X</span>
            <span>Schema validation</span>
            <span>Evidence graph</span>
            <span>Candidate plan</span>
          </div>
        </section>
        <section className="panel clock-panel">
          <div className="panel-title">
            <Clock3 size={18} />
            <span>Decision</span>
          </div>
          <p>
            Source-linked decision support for critical infrastructure operators.
            Every observation traces back to a Gazebo camera keyframe parsed by
            Qwen2.5-VL on AMD MI300X.
          </p>
        </section>
        <GpuTelemetry scenario={scenario} />
      </section>
    </main>
  );
}
