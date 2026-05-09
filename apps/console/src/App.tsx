import {
  Activity, AlertTriangle, CheckCircle2, ChevronRight,
  Cpu, FileText, HelpCircle, Mic, Radio, Send,
  ShieldAlert, Siren, Video, Waves, Zap, Image, Volume2, GitMerge
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fallbackScenario, type EvidenceItem, type Scenario } from "./domain";

declare const __API_BASE__: string;
const API_BASE = typeof __API_BASE__ !== "undefined" ? __API_BASE__ : "";

// ─── Demo data ────────────────────────────────────────────────────────────
const DEMO_VOICE = [
  { source_uuid: "SRC-AUD-S2347", speaker: "S2347", role: "sector supervisor",        location: "Sector 4", transcript: "Supervisor S2347 from Sector 4 — smoke is coming from the tanker area and spreading across the sector.", file: "/audio/2347-Sector4.aac" },
  { source_uuid: "SRC-AUD-S2451", speaker: "S2451", role: "nearby sector supervisor", location: "Sector 5", transcript: "Supervisor S2451 from Sector 5 — strange smell in the air for the past ten minutes.",                    file: "/audio/2451-sector5.aac" },
];

function demoSensorTrace() {
  const now = Date.now() / 1000;
  return Array.from({ length: 30 }, (_, i) => {
    const t = i * 3;
    const gas = t < 18 ? 2.4 + Math.sin(t) * 0.3 : t < 60 ? 2.4 + (t - 18) * 0.72 : 32;
    return { timestamp: now - (29 - i) * 3, gas_ppm: Math.round(gas * 10) / 10, wind_speed_mps: 3.7, wind_direction_deg: 225 };
  });
}

async function startIngestUpload(
  note: string, files: File[], audioFiles: File[] = [],
  voiceManifest: typeof DEMO_VOICE = [], sensorTrace: Array<Record<string,number>> = []
): Promise<{ job_id: string; backend: string }> {
  const form = new FormData();
  form.append("location", "Sector 4 — Tank B-4 Flange, Northgate LNG Terminal");
  form.append("field_notes", note);
  form.append("sensor_count", String(sensorTrace.length || 2));
  form.append("sensor_trace", JSON.stringify(sensorTrace));
  form.append("voice_manifest", JSON.stringify(voiceManifest));
  for (const f of files) form.append("images", f);
  for (const f of audioFiles) form.append("audio", f);
  const res = await fetch(`${API_BASE}/api/ingest/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error("ingest upload failed");
  return res.json();
}

// ─── Helpers ──────────────────────────────────────────────────────────────
function priorityClass(impact: number) {
  if (impact >= 85) return "priority-critical";
  if (impact >= 70) return "priority-high";
  return "priority-medium";
}

function evKindIcon(kind: EvidenceItem["kind"]) {
  switch (kind) {
    case "image":  return <Image  size={14} />;
    case "audio":  return <Volume2 size={14} />;
    case "sensor": return <Waves  size={14} />;
    default:       return <FileText size={14} />;
  }
}

// ─── FEED PANEL ──────────────────────────────────────────────────────────
const FEEDS = [
  { id: "cctv_south", label: "CCTV South", topic: "/cctv_south/image_raw" },
  { id: "drone_d1",   label: "Drone D-1",  topic: "/drone_d1/image_raw"   },
  { id: "cctv_gate",  label: "CCTV Gate",  topic: "/cctv_gate/image_raw"  },
];

function FeedPanel() {
  const [active, setActive]       = useState("cctv_south");
  const [bust,   setBust]         = useState<Record<string,number>>({});
  const [avail,  setAvail]        = useState<Record<string,boolean>>({});
  const [imgErr, setImgErr]       = useState<Record<string,boolean>>({});
  const [ts,     setTs]           = useState("");

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/feeds`);
        if (res.ok) {
          const feeds: Array<{source:string;available:boolean}> = await res.json();
          const av: Record<string,boolean> = {};
          for (const f of feeds) av[f.source] = f.available;
          setAvail(av);
          setImgErr({});
        }
      } catch { /* silent */ }
      const now = Date.now();
      setBust({ cctv_south: now, drone_d1: now, cctv_gate: now });
      setTs(new Date().toLocaleTimeString("en-GB", { hour12: false }));
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  const feed   = FEEDS.find(f => f.id === active)!;
  const src    = `${API_BASE}/api/feeds/latest/${active}?t=${bust[active] ?? 0}`;
  const isLive = avail[active];

  return (
    <div className="panel feeds-panel">
      <div className="panel-head">
        <span className="panel-label"><Video size={13} /> Gazebo Live Feeds</span>
        <div className="live-dot" title="Live polling active" />
      </div>

      <div className="feed-tabs">
        {FEEDS.map(f => (
          <button
            key={f.id}
            className={`feed-tab ${active === f.id ? "active" : ""} ${avail[f.id] ? "live" : ""}`}
            onClick={() => setActive(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="feed-viewport">
        {isLive && !imgErr[active] ? (
          <img
            src={src}
            alt={feed.label}
            style={{width:"100%",height:"100%",objectFit:"cover"}}
            onError={() => setImgErr(p => ({...p, [active]: true}))}
          />
        ) : (
          <div className="feed-no-signal">
            <Video size={28} />
            <span>{isLive && imgErr[active] ? "Frame Error — Retrying…" : "Awaiting Signal"}</span>
          </div>
        )}
      </div>

      <div className="feed-footer">
        <span className="feed-topic">{feed.topic}</span>
        <span className="feed-ts">{ts || "--:--:--"}</span>
      </div>
    </div>
  );
}

// ─── PIPELINE TICKER ─────────────────────────────────────────────────────
type Tick = { job_id: string; backend: string; status: "running"|"complete"|"error"; stage: string; message: string; progress: number; ts: number };

function PipelineTicker({ onScenarioUpdate, watchFnRef }: { onScenarioUpdate: (s: Scenario) => void; watchFnRef: React.MutableRefObject<((id:string,b:string)=>void)|null> }) {
  const [ticks, setTicks] = useState<Tick[]>([]);
  const watched = useRef<Set<string>>(new Set());

  const watchJob = (jobId: string, backend: string) => {
    if (watched.current.has(jobId)) return;
    watched.current.add(jobId);
    const es = new EventSource(`${API_BASE}/api/ingest/${jobId}/events`);
    const STAGES = ["queued","sampling","transcribing","analyzing","parsing","normalizing","synthesizing","complete","error"];
    for (const stage of STAGES) {
      es.addEventListener(stage, (e: Event) => {
        try {
          const ev = JSON.parse((e as MessageEvent).data);
          setTicks(p => [{ job_id: jobId, backend, status: stage === "error" ? "error" : "running", stage: ev.stage, message: ev.message, progress: ev.progress, ts: Date.now() }, ...p.slice(0, 24)]);
        } catch { /* */ }
      });
    }
    es.addEventListener("snapshot", (e: Event) => {
      try {
        const snap = JSON.parse((e as MessageEvent).data);
        es.close();
        if (snap.status === "complete" && snap.result) {
          onScenarioUpdate(snap.result as Scenario);
          setTicks(p => [{ job_id: jobId, backend, status: "complete", stage: "complete", message: "Scenario updated — scenario live", progress: 1, ts: Date.now() }, ...p.slice(0, 24)]);
        }
      } catch { /* */ }
    });
    es.onerror = () => es.close();
  };

  useEffect(() => { watchFnRef.current = watchJob; });

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs?limit=10`);
        if (!res.ok) return;
        const jobs = await res.json();
        for (const j of jobs) watchJob(j.job_id, j.backend);
      } catch { /* */ }
    };
    poll();
    const id = setInterval(poll, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="panel grow">
      <div className="panel-head">
        <span className="panel-label"><Zap size={13} /> Pipeline Ticker</span>
        {ticks.length > 0 && <span className="panel-badge">{ticks.length}</span>}
      </div>
      <div className="panel-body">
        {ticks.length === 0 ? (
          <div className="ticker-empty">
            <Cpu size={24} strokeWidth={1.5} />
            <span>Awaiting ingest jobs…</span>
          </div>
        ) : (
          <div className="tick-list">
            {ticks.map((t, i) => (
              <div key={`${t.job_id}-${i}`} className={`tick-item ${t.status}`}>
                <div className="tick-header">
                  <span className="tick-id mono">{t.job_id.slice(0, 12)}…</span>
                  <span className="tick-stage-badge">{t.stage}</span>
                </div>
                <div className="tick-msg">{t.message}</div>
                <div className="tick-bar">
                  <div className="tick-bar-fill" style={{ width: `${Math.round(t.progress * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── INCIDENT HEADER ─────────────────────────────────────────────────────
function IncidentHeader({ scenario }: { scenario: Scenario }) {
  const pct = Math.round(scenario.confidence * 100);
  const gas = scenario.evidence.find(e => e.kind === "sensor");
  const gasPpm = gas?.metadata?.["latest_ppm"] as number | undefined;

  return (
    <div className="incident-header">
      <div className="incident-meta">
        <div className="severity-tag">
          <ShieldAlert size={11} /> Critical Incident
        </div>
        <span className="incident-loc">{scenario.location}</span>
      </div>

      <div className="incident-title">{scenario.incident}</div>

      <div className="incident-brief-rows">
        {scenario.brief.slice(0, 3).map((b, i) => (
          <div key={i} className="incident-brief-row">{b}</div>
        ))}
      </div>

      <div className="incident-kpi-row">
        <div className="kpi-box">
          <div className="kpi-label">AI Confidence</div>
          <div className={`kpi-value ${pct >= 80 ? "cyan" : pct >= 60 ? "amber" : "red"}`}>{pct}%</div>
        </div>
        <div className="kpi-box">
          <div className="kpi-label">Evidence Items</div>
          <div className="kpi-value cyan">{scenario.evidence.length}</div>
        </div>
        <div className="kpi-box">
          <div className="kpi-label">Gas (ppm)</div>
          <div className={`kpi-value ${gasPpm && gasPpm > 20 ? "red" : gasPpm ? "amber" : ""}`}>{gasPpm != null ? gasPpm.toFixed(1) : "—"}</div>
        </div>
        <div className="kpi-box">
          <div className="kpi-label">Clock</div>
          <div className="kpi-value amber">{scenario.clock}</div>
        </div>
      </div>
    </div>
  );
}

// ─── TACTICAL MAP ────────────────────────────────────────────────────────
function TacticalMap({ scenario }: { scenario: Scenario }) {
  return (
    <div className="map-panel">
      <img src="/assets/vesper-field-map.png" alt="" className="map-img" />
      <div className="map-grid-overlay" />
      <div className="map-vignette" />

      {scenario.zones.map(zone => (
        <div
          key={zone.id}
          className={`risk-zone ${zone.severity}`}
          style={{ left: `${zone.x}%`, top: `${zone.y}%`, width: `${zone.radius * 2}%`, height: `${zone.radius * 2}%` }}
        >
          <div className="zone-pip" />
          <div className="zone-tooltip">{zone.label}</div>
        </div>
      ))}

      <div className="map-hud">
        <div className="map-hud-box">
          <label>Active Zones</label>
          <span>{scenario.zones.length}</span>
        </div>
        <div className="map-hud-box">
          <label>Highest Severity</label>
          <span>{scenario.zones.some(z => z.severity === "critical") ? "CRITICAL" : scenario.zones.some(z => z.severity === "elevated") ? "ELEVATED" : "WATCH"}</span>
        </div>
        <div className="map-hud-box" style={{ marginLeft: "auto" }}>
          <label>System Clock</label>
          <span>{scenario.clock}</span>
        </div>
      </div>
    </div>
  );
}

// ─── GPU BAR ─────────────────────────────────────────────────────────────
function GpuBar({ scenario }: { scenario: Scenario }) {
  if (!scenario.gpu?.length) return null;
  return (
    <div className="gpu-bar">
      {scenario.gpu.map((lane, i) => (
        <div key={i} className="gpu-lane">
          <div className="gpu-lane-label">{lane.label}</div>
          <div className="gpu-lane-bar">
            <div className="gpu-lane-fill" style={{ width: `${lane.utilization}%` }} />
          </div>
          <div className="gpu-lane-meta">
            <span>{lane.utilization}%</span>
            <span>{lane.latencyMs}ms</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── VOICE CHANNEL ────────────────────────────────────────────────────────
type VMsg = { id: number; type: "hq"|"field"; sender: string; location: string; text: string; file?: string };

function VoiceChannel({ watchFnRef }: { watchFnRef: React.MutableRefObject<((id:string,b:string)=>void)|null> }) {
  const [micActive,   setMicActive]   = useState(false);
  const [messages,    setMessages]    = useState<VMsg[]>([]);
  const [processing,  setProcessing]  = useState(false);
  const histRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (histRef.current) histRef.current.scrollTop = histRef.current.scrollHeight;
  }, [messages]);

  const trigger = async () => {
    setProcessing(true);
    setMessages(p => [...p, { id: Date.now(), type: "hq", sender: "COMMAND HQ", location: "Ops Center", text: "HQ to all sectors — suspected breach at Tank B-4. Report status immediately." }]);
    await new Promise(r => setTimeout(r, 1800));

    for (const rep of DEMO_VOICE) {
      setMessages(p => [...p, { id: Date.now(), type: "field", sender: rep.speaker, location: rep.location, text: rep.transcript, file: rep.file }]);
      const audio = new Audio(rep.file);
      void audio.play().catch(() => {/* browser block */});
      await new Promise<void>(res => { audio.onended = () => res(); setTimeout(res, 9000); });
      await new Promise(r => setTimeout(r, 800));
    }

    try {
      const fetchAudio = async (url: string, name: string) => { const res = await fetch(url); const b = await res.blob(); return new File([b], name, { type: "audio/aac" }); };
      const files = await Promise.all(DEMO_VOICE.map(v => fetchAudio(v.file, v.file.split("/").pop()!)));
      const job = await startIngestUpload("Multi-sector voice confirmation of breach.", [], files, DEMO_VOICE, demoSensorTrace());
      if (watchFnRef.current) watchFnRef.current(job.job_id, job.backend);
    } catch (e) { console.error("Pipeline error", e); }
    setProcessing(false);
  };

  const toggleMic = () => {
    if (processing) return;
    if (micActive) { setMicActive(false); void trigger(); }
    else setMicActive(true);
  };

  return (
    <div className="panel voice-panel">
      <div className="panel-head">
        <span className="panel-label"><Radio size={13} /> Command Voice Channel</span>
        {processing && <span className="panel-badge amber">Processing</span>}
      </div>

      <div className="voice-history" ref={histRef}>
        {messages.length === 0 ? (
          <div className="voice-empty">
            <Radio size={22} strokeWidth={1.5} />
            <span>No active communications</span>
          </div>
        ) : messages.map(m => (
          <div key={m.id} className={`vmsg ${m.type}`}>
            <div className="vmsg-meta">
              <span className="vmsg-sender">{m.sender}</span>
              <span className="vmsg-loc">{m.location}</span>
            </div>
            <div className="vmsg-text">{m.text}</div>
            {m.file && <audio controls src={m.file} />}
          </div>
        ))}
      </div>

      <div className="voice-controls-bar">
        <button className={`mic-btn ${micActive ? "active" : ""}`} onClick={toggleMic} disabled={processing} title={micActive ? "Stop & dispatch" : "Activate mic"}>
          <Mic size={18} />
        </button>
        <div className={`waveform ${micActive ? "active" : ""}`}>
          {Array.from({ length: 7 }, (_, i) => <div key={i} className="wv-bar" />)}
        </div>
        <button className="send-btn" onClick={toggleMic} disabled={!micActive || processing}>
          <Send size={13} /> Dispatch
        </button>
      </div>
    </div>
  );
}

// ─── EVIDENCE RAIL ───────────────────────────────────────────────────────
function EvidenceRail({ evidence, selected, onSelect }: { evidence: EvidenceItem[]; selected: string|null; onSelect: (id: string) => void }) {
  return (
    <div className="panel evidence-panel">
      <div className="panel-head">
        <span className="panel-label"><GitMerge size={13} /> Evidence Rail</span>
        <span className="panel-badge">{evidence.length}</span>
      </div>
      <div className="panel-body">
        <div className="evidence-list">
          {evidence.map(ev => (
            <div key={ev.id} className={`ev-item ${selected === ev.id ? "selected" : ""}`} onClick={() => onSelect(ev.id)}>
              <div className={`ev-icon ${ev.kind}`}>{evKindIcon(ev.kind)}</div>
              <div className="ev-body">
                <div className="ev-source truncate">{ev.source}</div>
                <div className="ev-summary">{ev.summary}</div>
              </div>
              <span className="ev-conf">{Math.round(ev.confidence * 100)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── RESPONSE ACTIONS ────────────────────────────────────────────────────
function ResponseActions({ scenario }: { scenario: Scenario }) {
  const [approved, setApproved] = useState<Set<string>>(new Set());

  const toggle = (id: string) => setApproved(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  return (
    <div className="panel grow actions-panel">
      <div className="panel-head">
        <span className="panel-label"><Siren size={13} /> Response Actions</span>
        {approved.size > 0 && <span className="panel-badge green">{approved.size} approved</span>}
      </div>
      <div className="panel-body">
        <div className="action-list">
          {scenario.actions.map(a => (
            <div key={a.id} className={`action-card ${priorityClass(a.impact)} ${approved.has(a.id) ? "approved" : ""}`}>
              <div className="action-top">
                <div className="action-priority" />
                <div className="action-content">
                  <div className="action-title">{a.title}</div>
                  <div className="action-caveat">{a.caveat}</div>
                </div>
              </div>
              <div className="action-bottom">
                <div className="action-stats">
                  <div className="action-stat">
                    <span className="action-stat-label">ETA</span>
                    <span className="action-stat-value eta">{a.etaMinutes}m</span>
                  </div>
                  <div className="action-stat">
                    <span className="action-stat-label">Impact</span>
                    <span className="action-stat-value impact">{a.impact}%</span>
                  </div>
                  <div className="action-stat">
                    <span className="action-stat-label">Owner</span>
                    <span className="action-stat-value">{a.owner}</span>
                  </div>
                </div>
                <button className="action-approve-btn" onClick={() => toggle(a.id)}>
                  {approved.has(a.id) ? <><CheckCircle2 size={11} /> Approved</> : <><ChevronRight size={11} /> Approve</>}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── UNCERTAINTY LEDGER ──────────────────────────────────────────────────
function UncertaintyLedger({ scenario }: { scenario: Scenario }) {
  if (!scenario.uncertainties?.length) return null;
  return (
    <div className="panel uncertainty-panel">
      <div className="panel-head">
        <span className="panel-label"><HelpCircle size={13} /> Uncertainty Ledger</span>
        <span className="panel-badge amber">{scenario.uncertainties.length}</span>
      </div>
      <div className="panel-body">
        <div className="unc-list">
          {scenario.uncertainties.map(u => (
            <div key={u.id} className={`unc-item ${u.severity}`}>
              <div className="unc-dot" />
              <div className="unc-body">
                <div className="unc-title">{u.title}</div>
                <div className="unc-detail">{u.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── APP ROOT ────────────────────────────────────────────────────────────
export function App() {
  const [scenario,   setScenario]   = useState<Scenario>(fallbackScenario);
  const [processing, setProcessing] = useState(false);
  const [selectedEv, setSelectedEv] = useState<string|null>(null);
  const watchFnRef = useRef<((id:string,b:string)=>void)|null>(null);

  const handleScenarioUpdate = (s: Scenario) => { setScenario(s); setProcessing(false); };

  const criticalZones  = scenario.zones.filter(z => z.severity === "critical").length;
  const vllmOnline     = scenario.gpu?.some(g => g.utilization > 0) ?? false;

  return (
    <div className="shell">
      {processing && <div className="processing-bar" />}

      {/* ── TOPBAR ── */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon"><Activity size={18} /></div>
          <div className="brand-text">
            <h1>VESPERGRID</h1>
            <p>Multimodal Ops Command · AMD MI300X</p>
          </div>
        </div>

        <div className="topbar-center">
          <span className="nav-pill active"><ShieldAlert size={12} /> Live Incident</span>
          <span className="nav-pill"><Cpu size={12} /> MI300X Telemetry</span>
          <span className="nav-pill"><Activity size={12} /> Sensor Grid</span>
        </div>

        <div className="topbar-right">
          {criticalZones > 0 && (
            <div className="alert-chip">
              <AlertTriangle size={11} /> {criticalZones} Critical Zone{criticalZones > 1 ? "s" : ""}
            </div>
          )}
          <div className={`status-chip ${vllmOnline ? "" : "warn"}`}>
            <div className="dot" /> {vllmOnline ? "Qwen-VL · MI300X Online" : "Deterministic Mode"}
          </div>
        </div>
      </header>

      {/* ── WORKSPACE ── */}
      <main className="workspace">

        {/* LEFT — Feeds + Ticker */}
        <div className="col">
          <FeedPanel />
          <PipelineTicker
            onScenarioUpdate={s => { handleScenarioUpdate(s); setProcessing(false); }}
            watchFnRef={watchFnRef}
          />
        </div>

        {/* CENTER — Incident + Map + GPU */}
        <div className="col">
          <IncidentHeader scenario={scenario} />
          <TacticalMap    scenario={scenario} />
          <GpuBar         scenario={scenario} />
        </div>

        {/* RIGHT — Voice + Evidence + Actions + Uncertainty */}
        <div className="col">
          <VoiceChannel watchFnRef={watchFnRef} />
          <EvidenceRail evidence={scenario.evidence} selected={selectedEv} onSelect={setSelectedEv} />
          <ResponseActions scenario={scenario} />
          <UncertaintyLedger scenario={scenario} />
        </div>

      </main>
    </div>
  );
}
