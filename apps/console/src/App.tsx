import {
  Activity,
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Cpu,
  FileAudio,
  FileText,
  GitBranch,
  Layers3,
  Link2,
  Mic,
  Radar,
  Radio,
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

const demoVoiceReports = [
  {
    source_uuid: "SRC-AUD-S2347",
    speaker: "S2347",
    role: "sector supervisor",
    location: "Sector 4",
    transcript: "Supervisor S2347 from Sector 4 reports smoke coming from the tanker area and spreading across the sector.",
    file: "/audio/2347-Sector4.aac"
  },
  {
    source_uuid: "SRC-AUD-S2451",
    speaker: "S2451",
    role: "nearby sector supervisor",
    location: "Sector 5",
    transcript: "Supervisor S2451 from Sector 5 reports a strange smell over the last ten minutes.",
    file: "/audio/2451-sector5.aac"
  }
];

type VoiceReport = (typeof demoVoiceReports)[number];
type VoicePlaybackState = {
  source_uuid: string;
  speaker: string;
  location: string;
  status: "idle" | "queued" | "speaking" | "complete";
};

function demoSensorTrace() {
  const now = Date.now() / 1000;
  return Array.from({ length: 30 }, (_, index) => {
    const t = index * 3;
    const gas = t < 18 ? 2.4 + Math.sin(t) * 0.3 : t < 60 ? 2.4 + (t - 18) * 0.72 : 32;
    return {
      timestamp: now - (29 - index) * 3,
      gas_ppm: Math.round(gas * 10) / 10,
      wind_speed_mps: 3.7,
      wind_direction_deg: 225
    };
  });
}

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
  files: File[],
  audioFiles: File[] = [],
  voiceManifest: typeof demoVoiceReports = [],
  sensorTrace: Array<Record<string, number>> = []
): Promise<{ job_id: string; backend: string }> {
  const form = new FormData();
  form.append("location", "Sector 4 — Tank B-4 Flange, Northgate LNG Terminal");
  form.append("field_notes", note);
  form.append("sensor_count", String(sensorTrace.length || 2));
  form.append("sensor_trace", JSON.stringify(sensorTrace));
  form.append("voice_manifest", JSON.stringify(voiceManifest));
  for (const f of files) form.append("images", f);
  for (const f of audioFiles) form.append("audio", f);
  const response = await fetch(`${API_BASE}/api/ingest/upload`, {
    method: "POST",
    body: form
  });
  if (!response.ok) throw new Error("ingest upload unavailable");
  return response.json();
}

async function transcribeOperatorAudio(file: File, fallbackText: string) {
  const form = new FormData();
  form.append("audio", file);
  form.append("fallback_text", fallbackText);
  const response = await fetch(`${API_BASE}/api/audio/transcribe`, {
    method: "POST",
    body: form
  });
  if (!response.ok) throw new Error("audio transcription unavailable");
  return response.json() as Promise<{ text: string; confidence: number; backend: string }>;
}

async function playVoiceSequence(
  reports: VoiceReport[],
  onState: (states: VoicePlaybackState[]) => void
) {
  const states: VoicePlaybackState[] = reports.map((report, index) => ({
    source_uuid: report.source_uuid,
    speaker: report.speaker,
    location: report.location,
    status: index === 0 ? "queued" : "idle",
  }));
  onState(states);

  for (let i = 0; i < reports.length; i += 1) {
    states.forEach((state, idx) => {
      state.status = idx < i ? "complete" : idx === i ? "speaking" : idx === i + 1 ? "queued" : "idle";
    });
    onState([...states]);
    try {
      await new Promise<void>((resolve) => {
        const audio = new Audio(reports[i].file);
        const finish = () => resolve();
        audio.addEventListener("ended", finish, { once: true });
        audio.addEventListener("error", finish, { once: true });
        void audio.play().catch(() => resolve());
        window.setTimeout(resolve, 12_000);
      });
    } catch {
      /* keep pipeline moving */
    }
  }

  states.forEach((state) => {
    state.status = "complete";
  });
  onState([...states]);
}

function ingestStream(
  jobId: string,
  backend: string,
  onProgress: (p: IngestProgress) => void
): Promise<Scenario> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`${API_BASE}/api/ingest/${jobId}/events`);
    const stages = ["queued", "sampling", "parsing", "transcribing", "analyzing", "normalizing", "synthesizing", "complete", "error"];
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
  const mediaUrl = evidence?.assetUrl ? `${API_BASE}${evidence.assetUrl}` : asset?.src;
  if (!evidence && !action && !issue) return null;

  return (
    <section className="panel source-preview" aria-label="Source preview">
      <div className="panel-title">
        <Link2 size={18} />
        <span>Source Lineage</span>
      </div>
      <div className="source-preview-body">
        {evidence?.kind === "audio" && mediaUrl ? (
          <div className="source-thumb source-thumb-text">
            <Radio size={28} />
            <span>{evidence.source}</span>
            <audio controls src={mediaUrl} />
          </div>
        ) : mediaUrl ? (
          <img className="source-thumb" src={mediaUrl} alt={asset?.alt ?? evidence?.source ?? "Evidence asset"} />
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
              {evidence.transcript && <p className="transcript-line">"{evidence.transcript}"</p>}
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
  if (item.kind === "audio") return <FileAudio size={16} />;
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
        <span>Evidence Timeline</span>
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
        <span>Response Options</span>
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
        <span>Incident State</span>
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
  // cachebust token per feed — bumped every 10s to force img reload
  const [bust, setBust] = useState<Record<string, number>>({
    cctv_south: Date.now(), drone_d1: Date.now(), cctv_gate: Date.now(),
  });
  // track which feeds actually have a frame available
  const [available, setAvailable] = useState<Record<string, boolean>>({
    cctv_south: false, drone_d1: false, cctv_gate: false,
  });

  useEffect(() => {
    const poll = async () => {
      // Check /api/feeds to know which sources have frames
      try {
        const res = await fetch(`${API_BASE}/api/feeds`);
        if (res.ok) {
          const feeds: Array<{ source: string; available: boolean }> = await res.json();
          const av: Record<string, boolean> = {};
          for (const f of feeds) av[f.source] = f.available;
          setAvailable(av);
        }
      } catch { /* silent */ }
      // always bump bust so img refreshes
      setBust({ cctv_south: Date.now(), drone_d1: Date.now(), cctv_gate: Date.now() });
    };
    poll();
    const id = window.setInterval(poll, 5_000);
    return () => window.clearInterval(id);
  }, []);

  const feed = GAZEBO_FEEDS.find((f) => f.id === activeFeed)!;
  const hasFrame = available[activeFeed];
  const imgSrc = `${API_BASE}/api/feeds/latest/${activeFeed}?t=${bust[activeFeed]}`;

  return (
    <section className="panel gazebo-panel">
      <div className="panel-title">
        <Video size={18} />
        <span>Gazebo Live Feeds</span>
        {hasFrame && <span className="feed-live-dot" title="Frames received from frame_sampler" />}
      </div>
      <div className="feed-tabs">
        {GAZEBO_FEEDS.map((f) => (
          <button
            key={f.id}
            className={`feed-tab ${activeFeed === f.id ? "active" : ""} ${available[f.id] ? "has-frame" : ""}`}
            onClick={() => setActiveFeed(f.id)}
          >
            {f.label}
            {available[f.id] && <span className="feed-tab-dot" />}
          </button>
        ))}
      </div>
      <div className="feed-viewport">
        {hasFrame ? (
          <img
            key={imgSrc}
            src={imgSrc}
            alt={`${feed.label} latest frame`}
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
              setAvailable((prev) => ({ ...prev, [activeFeed]: false }));
            }}
          />
        ) : (
          <div className="feed-placeholder">
            <Video size={32} style={{ opacity: 0.28 }} />
            <span>{feed.label}</span>
            <small>{feed.topic}</small>
            <small style={{ color: "#818679", marginTop: 6 }}>
              Waiting for Gazebo + frame_sampler
            </small>
          </div>
        )}
      </div>
      <div className="feed-meta">
        <small>ROS2 topic</small>
        <code>{feed.topic}</code>
        <small style={{ marginTop: 6 }}>Last polled</small>
        <code>{new Date(bust[activeFeed]).toLocaleTimeString()}</code>
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
    const stages = ["queued", "sampling", "parsing", "transcribing", "analyzing", "normalizing", "synthesizing", "complete", "error"];
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

  // Poll /api/jobs every 8s — auto-discovers jobs from frame_sampler
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs?limit=10`);
        if (!res.ok) return;
        const jobs: Array<{ job_id: string; backend: string; status: string }> = await res.json();
        for (const j of jobs) {
          if (!watchedRef.current.has(j.job_id)) {
            watchJob(j.job_id, j.backend);
          }
        }
      } catch { /* silent — API may be briefly unavailable */ }
    };
    poll();
    const id = window.setInterval(poll, 8_000);
    return () => window.clearInterval(id);
  }, []);  // eslint-disable-line

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

function SensorTrendPanel({ scenario }: { scenario: Scenario }) {
  const sensorEvidence = [...scenario.evidence].reverse().find((item) => item.kind === "sensor");
  const trace = demoSensorTrace();
  const max = Math.max(...trace.map((p) => p.gas_ppm), 30);
  const points = trace
    .map((p, i) => `${(i / (trace.length - 1)) * 100},${58 - (p.gas_ppm / max) * 54}`)
    .join(" ");
  const peak = sensorEvidence?.metadata?.peak_ppm ?? Math.max(...trace.map((p) => p.gas_ppm));
  const band = sensorEvidence?.metadata?.toxicity_band ?? "demo trace";

  return (
    <section className="panel sensor-panel">
      <div className="panel-title">
        <BarChart3 size={18} />
        <span>Gas Trend</span>
      </div>
      <div className="sensor-chart">
        <svg viewBox="0 0 100 62" preserveAspectRatio="none">
          <line x1="0" y1="30" x2="100" y2="30" />
          <polyline points={points} />
        </svg>
      </div>
      <div className="sensor-stats">
        <div><small>Peak ppm</small><strong>{String(peak)}</strong></div>
        <div><small>Band</small><strong>{String(band)}</strong></div>
      </div>
      <p>{sensorEvidence?.summary ?? "Awaiting structured gas and wind telemetry from ROS2."}</p>
    </section>
  );
}

function VoiceChannelPanel({
  onVoiceIncident,
  onRunVoiceTest,
  playbackStates,
  processing
}: {
  onVoiceIncident: (operatorText: string, operatorAudio: File | null) => Promise<void>;
  onRunVoiceTest: () => Promise<void>;
  playbackStates: VoicePlaybackState[];
  processing: boolean;
}) {
  const [recording, setRecording] = useState(false);
  const [operatorText, setOperatorText] = useState(
    "Attention everybody, VesperGrid is showing contamination risk in the workspace. Supervisors around Sector 4, give me current status."
  );
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    chunks.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.current.push(event.data);
    };
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks.current, { type: "audio/webm" });
      const file = new File([blob], "operator_command.webm", { type: "audio/webm" });
      try {
        const transcript = await transcribeOperatorAudio(file, operatorText);
        setOperatorText(transcript.text || operatorText);
        await onVoiceIncident(transcript.text || operatorText, file);
      } catch {
        await onVoiceIncident(operatorText, file);
      }
    };
    recorder.start();
    setMediaRecorder(recorder);
    setRecording(true);
  };

  const stopRecording = () => {
    mediaRecorder?.stop();
    setRecording(false);
    setMediaRecorder(null);
  };

  const dispatchTextOnly = async () => {
    await onVoiceIncident(operatorText, null);
  };

  return (
    <section className="panel voice-panel">
      <div className="panel-title">
        <Mic size={18} />
        <span>Voice Channel</span>
      </div>
      <textarea value={operatorText} onChange={(event) => setOperatorText(event.target.value)} />
      <div className="voice-controls">
        <button disabled={processing} onClick={recording ? stopRecording : startRecording}>
          <Mic size={14} />
          {recording ? "Stop and dispatch" : "Open mic"}
        </button>
        <button disabled={processing || recording} onClick={dispatchTextOnly}>
          <Radio size={14} />
          Dispatch scripted reports
        </button>
        <button disabled={processing || recording} onClick={onRunVoiceTest}>
          <FileAudio size={14} />
          Run STT test
        </button>
      </div>
      <div className="voice-report-list">
        {demoVoiceReports.map((report) => (
          <article key={report.source_uuid} className={`voice-report-card ${playbackStates.find((item) => item.source_uuid === report.source_uuid)?.status ?? "idle"}`}>
            <div className="row-heading">
              <span>{report.speaker}</span>
              <b>{playbackStates.find((item) => item.source_uuid === report.source_uuid)?.status === "speaking" ? `${report.speaker} speaking` : report.location}</b>
            </div>
            <audio controls src={report.file} />
            <p>{report.transcript}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function App() {
  const [scenario, setScenario] = useState<Scenario>(fallbackScenario);
  const [backend, setBackend] = useState<"online" | "offline" | "checking">("checking");
  const [selectedSource, setSelectedSource] = useState<string | null>("SRC-VID-2217");
  const [processing, setProcessing] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<IngestProgress | null>(null);
  const [voicePlaybackStates, setVoicePlaybackStates] = useState<VoicePlaybackState[]>(
    demoVoiceReports.map((report) => ({
      source_uuid: report.source_uuid,
      speaker: report.speaker,
      location: report.location,
      status: "idle",
    }))
  );
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

  const handleVoiceIncident = async (operatorText: string, operatorAudio: File | null) => {
    setProcessing(true);
    setIngestProgress(null);
    try {
      const voiceFiles: File[] = [];
      if (operatorAudio) voiceFiles.push(operatorAudio);
      const manifest = [...demoVoiceReports];
      for (const report of demoVoiceReports) {
        const response = await fetch(report.file);
        const blob = await response.blob();
        voiceFiles.push(new File([blob], report.file.split("/").pop() ?? "voice.aac", { type: blob.type || "audio/aac" }));
      }
      void playVoiceSequence(demoVoiceReports, setVoicePlaybackStates);
      const note = `${operatorText}\n\nDispatch requested two Sector 4 voice status reports.`;
      const { job_id, backend: jobBackend } = await startIngestUpload(
        note,
        [],
        voiceFiles,
        operatorAudio
          ? [
              {
                source_uuid: "SRC-AUD-OPERATOR",
                speaker: "Operator",
                role: "incident commander",
                location: "VesperGrid console",
                transcript: operatorText,
                file: "operator_command.webm"
              },
              ...manifest
            ]
          : manifest,
        demoSensorTrace()
      );
      watchJobRef.current?.(job_id, jobBackend);
      await _runIngestStream(job_id, jobBackend);
    } catch {
      setBackend("offline");
    } finally {
      setProcessing(false);
      window.setTimeout(() => {
        setVoicePlaybackStates((prev) => prev.map((state) => ({ ...state, status: "idle" })));
      }, 4000);
      window.setTimeout(() => setIngestProgress(null), 1400);
    }
  };

  const handleVoiceTest = async () => {
    await handleVoiceIncident(
      "Attention Sector 4 and nearby sectors. VesperGrid is requesting immediate status on smoke, odor, and spill spread.",
      null
    );
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

      <section className="feed-strip">
        <GazeboFeedPanel />
        <LiveJobTicker
          onScenarioUpdate={(s) => { setScenario(s); setBackend("online"); }}
          onRegister={(fn) => { watchJobRef.current = fn; }}
        />
      </section>

      <section className="workspace">
        <div className="left-column">
          <VoiceChannelPanel
            onVoiceIncident={handleVoiceIncident}
            onRunVoiceTest={handleVoiceTest}
            playbackStates={voicePlaybackStates}
            processing={processing}
          />
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
        <SensorTrendPanel scenario={scenario} />
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
