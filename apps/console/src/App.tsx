import {
  Activity, AlertTriangle, CheckCircle2, ChevronRight,
  Cpu, FileText, HelpCircle, Mic, Radio, Send,
  ShieldAlert, Siren, Video, Waves, Zap, Image, Volume2,
  GitMerge, Brain, Eye, Megaphone, TrendingUp, Clock,
  X, RefreshCw
} from "lucide-react";
import { useEffect, useRef, useState, useCallback } from "react";
import { fallbackScenario, type EvidenceItem, type Scenario } from "./domain";

declare const __API_BASE__: string;
const API_BASE = typeof __API_BASE__ !== "undefined" ? __API_BASE__ : "";

// ─── Helpers ──────────────────────────────────────────────────────────────
function priorityClass(impact: number) {
  if (impact >= 85) return "priority-critical";
  if (impact >= 70) return "priority-high";
  return "priority-medium";
}

function evKindIcon(kind: EvidenceItem["kind"]) {
  switch (kind) {
    case "image":  return <Eye    size={13} />;
    case "audio":  return <Volume2 size={13} />;
    case "sensor": return <Waves  size={13} />;
    default:       return <FileText size={13} />;
  }
}

function confColor(c: number) {
  if (c >= 0.8) return "cyan";
  if (c >= 0.6) return "amber";
  return "red";
}

// ─── LIVE FEEDS HERO ──────────────────────────────────────────────────────
const FEEDS = [
  { id: "cctv_south",   label: "CCTV South",    icon: "CAM-A" },
  { id: "drone_d1",     label: "Drone D-1 Main", icon: "UAV-F" },
  { id: "drone_d1_back",label: "Drone D-1 Back", icon: "UAV-B" },
  { id: "cctv_gate",    label: "CCTV Gate",      icon: "CAM-G" },
];

function HeroFeeds() {
  const [active, setActive]   = useState("cctv_south");
  const [bust,   setBust]     = useState<Record<string,number>>({});
  const [avail,  setAvail]    = useState<Record<string,boolean>>({});
  const [imgErr, setImgErr]   = useState<Record<string,boolean>>({});
  const [ts,     setTs]       = useState("");

  useEffect(() => {
    let pollCount = 0;
    const poll = async () => {
      pollCount++;
      const now = Date.now();
      setBust({ cctv_south: now, drone_d1: now, drone_d1_back: now, cctv_gate: now });
      setTs(new Date().toLocaleTimeString("en-GB", { hour12: false }));
      if (pollCount % 10 === 1) {
        try {
          const res = await fetch(`${API_BASE}/api/feeds`);
          if (res.ok) {
            const feeds: Array<{source:string;available:boolean}> = await res.json();
            const av: Record<string,boolean> = {};
            for (const f of feeds) av[f.source] = f.available;
            setAvail(av);
          }
        } catch { /* silent */ }
      }
    };
    poll();
    const id = setInterval(poll, 500);
    return () => clearInterval(id);
  }, []);

  const src    = `${API_BASE}/api/feeds/latest/${active}?t=${bust[active] ?? 0}`;
  const isLive = avail[active];
  const activeFeed = FEEDS.find(f => f.id === active)!;
  const anyLive = Object.values(avail).some(Boolean);

  return (
    <div className="hero-feeds">
      {/* Main viewport */}
      <div className="hero-viewport">
        {isLive && !imgErr[active] ? (
          <img
            key={active}
            src={src}
            alt={activeFeed.label}
            className="hero-img"
            onLoad={() => setImgErr(p => ({...p, [active]: false}))}
            onError={() => setImgErr(p => ({...p, [active]: true}))}
          />
        ) : (
          <div className="hero-no-signal">
            <Video size={36} strokeWidth={1} />
            <span>{anyLive ? "Switching feed…" : "Awaiting camera signal"}</span>
          </div>
        )}

        {/* HUD overlays */}
        <div className="hero-hud-tl">
          <span className="hud-badge red-glow">● REC</span>
          <span className="hud-label">{activeFeed.icon}</span>
          <span className="hud-label">{activeFeed.label}</span>
        </div>
        <div className="hero-hud-tr">
          <span className="hud-ts">{ts || "--:--:--"}</span>
        </div>
        <div className="hero-hud-bl">
          <span className="hud-label mono">NORTHGATE LNG — TANK B-4 SECTOR</span>
        </div>
        <div className="hero-hud-br">
          <span className={`hud-live ${isLive ? "on" : "off"}`}>{isLive ? "LIVE" : "NO SIGNAL"}</span>
        </div>

        {/* Scan-line effect */}
        <div className="hero-scanlines" />
      </div>

      {/* Camera tabs below viewport */}
      <div className="hero-tabs">
        {FEEDS.map(f => (
          <button
            key={f.id}
            className={`hero-tab ${active === f.id ? "active" : ""} ${avail[f.id] ? "live" : ""}`}
            onClick={() => { setActive(f.id); setImgErr(p => ({...p, [f.id]: false})); }}
          >
            <span className="hero-tab-icon">{f.icon}</span>
            <span className="hero-tab-label">{f.label}</span>
            {avail[f.id] && <span className="hero-tab-dot" />}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── ORCHESTRATOR AGENT ───────────────────────────────────────────────────
// Central hub: polls jobs, watches SSE, drives all scenario state.
// This is the "main orchestrator" — every downstream component reads from
// the scenario it emits.
type OrchestratorState = {
  scenario: Scenario;
  lastJobId: string | null;
  lastBackend: string | null;
  lastUpdated: number | null;
  agentStage: string;
  agentProgress: number;
  agentStatus: "idle" | "running" | "complete" | "error";
  jobCount: number;
};

function useOrchestrator(): OrchestratorState & { refresh: () => void } {
  const [state, setState] = useState<OrchestratorState>({
    scenario:      fallbackScenario,
    lastJobId:     null,
    lastBackend:   null,
    lastUpdated:   null,
    agentStage:    "idle",
    agentProgress: 0,
    agentStatus:   "idle",
    jobCount:      0,
  });
  const watched = useRef<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval>|null>(null);

  const watchJob = useCallback((jobId: string, backend: string) => {
    if (watched.current.has(jobId)) return;
    watched.current.add(jobId);
    const es = new EventSource(`${API_BASE}/api/ingest/${jobId}/events`);
    const STAGES = ["queued","sampling","transcribing","analyzing","parsing","normalizing","synthesizing","complete","error"];
    for (const stage of STAGES) {
      es.addEventListener(stage, (e: Event) => {
        try {
          const ev = JSON.parse((e as MessageEvent).data);
          setState(p => ({
            ...p,
            lastJobId:     jobId,
            lastBackend:   backend,
            agentStage:    ev.stage ?? stage,
            agentProgress: ev.progress ?? 0,
            agentStatus:   stage === "error" ? "error" : "running",
          }));
        } catch { /* */ }
      });
    }
    es.addEventListener("snapshot", (e: Event) => {
      try {
        const snap = JSON.parse((e as MessageEvent).data);
        es.close();
        if (snap.status === "complete" && snap.result) {
          setState(p => ({
            ...p,
            scenario:      snap.result as Scenario,
            lastJobId:     jobId,
            lastBackend:   backend,
            lastUpdated:   Date.now(),
            agentStage:    "complete",
            agentProgress: 1,
            agentStatus:   "complete",
            jobCount:      p.jobCount + 1,
          }));
        }
      } catch { /* */ }
    });
    es.onerror = () => {
      es.close();
      setState(p => p.agentStatus === "running" ? { ...p, agentStatus: "error", agentStage: "connection lost" } : p);
    };
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/jobs?limit=5`);
      if (!res.ok) return;
      const jobs: Array<{job_id:string;backend:string}> = await res.json();
      for (const j of jobs) watchJob(j.job_id, j.backend);
    } catch { /* */ }
  }, [watchJob]);

  useEffect(() => {
    fetchJobs();
    pollRef.current = setInterval(fetchJobs, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchJobs]);

  const refresh = useCallback(() => { fetchJobs(); }, [fetchJobs]);

  return { ...state, refresh };
}

// ─── ORCHESTRATOR STATUS BAR ──────────────────────────────────────────────
function AgentStatusBar({ state }: { state: OrchestratorState & { refresh: () => void } }) {
  const pct = Math.round(state.agentProgress * 100);
  const sinceMs = state.lastUpdated ? Date.now() - state.lastUpdated : null;
  const sinceStr = sinceMs == null ? "—" : sinceMs < 60000 ? `${Math.round(sinceMs/1000)}s ago` : `${Math.round(sinceMs/60000)}m ago`;

  return (
    <div className={`agent-bar agent-${state.agentStatus}`}>
      <div className="agent-bar-left">
        <Brain size={13} className="agent-icon" />
        <span className="agent-label">ORCHESTRATOR</span>
        <span className="agent-stage">{state.agentStage.toUpperCase()}</span>
        {state.agentStatus === "running" && (
          <div className="agent-progress">
            <div className="agent-progress-fill" style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
      <div className="agent-bar-right">
        {state.lastBackend && (
          <span className="agent-meta mono">{state.lastBackend}</span>
        )}
        {state.jobCount > 0 && (
          <span className="agent-meta">
            <TrendingUp size={10} /> {state.jobCount} updates
          </span>
        )}
        {state.lastUpdated && (
          <span className="agent-meta">
            <Clock size={10} /> {sinceStr}
          </span>
        )}
        <button className="agent-refresh" onClick={state.refresh} title="Refresh jobs">
          <RefreshCw size={11} />
        </button>
      </div>
    </div>
  );
}

// ─── KPI STRIP ───────────────────────────────────────────────────────────
function KpiStrip({ scenario }: { scenario: Scenario }) {
  const pct    = Math.round(scenario.confidence * 100);
  const gas    = scenario.evidence.find(e => e.kind === "sensor");
  const gasPpm = gas?.metadata?.["latest_ppm"] as number | undefined;
  const hazards = scenario.evidence.filter(e => e.signal?.includes("hazard") || e.signal === "hazard").length;
  const critZ  = scenario.zones.filter(z => z.severity === "critical").length;

  return (
    <div className="kpi-strip">
      <div className="kpi-tile">
        <div className="kpi-tile-label">AI Confidence</div>
        <div className={`kpi-tile-value ${confColor(scenario.confidence)}`}>{pct}%</div>
        <div className="kpi-tile-bar"><div className="kpi-tile-fill" style={{width:`${pct}%`, background: pct>=80?"var(--cyan)":pct>=60?"var(--amber)":"var(--red)"}} /></div>
      </div>
      <div className="kpi-tile">
        <div className="kpi-tile-label">Evidence Items</div>
        <div className="kpi-tile-value cyan">{scenario.evidence.length}</div>
        <div className="kpi-tile-sub">{hazards} hazard signals</div>
      </div>
      <div className="kpi-tile">
        <div className="kpi-tile-label">Gas Level (ppm)</div>
        <div className={`kpi-tile-value ${gasPpm && gasPpm > 20 ? "red" : gasPpm ? "amber" : "dim"}`}>
          {gasPpm != null ? gasPpm.toFixed(1) : "—"}
        </div>
        <div className="kpi-tile-sub">{gasPpm && gasPpm > 20 ? "ABOVE LEL" : gasPpm ? "Below LEL" : "No sensor"}</div>
      </div>
      <div className="kpi-tile">
        <div className="kpi-tile-label">Critical Zones</div>
        <div className={`kpi-tile-value ${critZ > 0 ? "red" : "dim"}`}>{critZ}</div>
        <div className="kpi-tile-sub">{scenario.zones.length} zones total</div>
      </div>
      <div className="kpi-tile">
        <div className="kpi-tile-label">Actions Ready</div>
        <div className="kpi-tile-value amber">{scenario.actions.length}</div>
        <div className="kpi-tile-sub">Awaiting approval</div>
      </div>
      <div className="kpi-tile">
        <div className="kpi-tile-label">Uncertainties</div>
        <div className={`kpi-tile-value ${scenario.uncertainties?.length ? "amber" : "dim"}`}>
          {scenario.uncertainties?.length ?? 0}
        </div>
        <div className="kpi-tile-sub">Open flags</div>
      </div>
    </div>
  );
}

// ─── INCIDENT BRIEF ───────────────────────────────────────────────────────
function IncidentBrief({ scenario }: { scenario: Scenario }) {
  return (
    <div className="incident-brief-panel">
      <div className="ib-header">
        <div className="severity-tag"><ShieldAlert size={11} /> Critical Incident</div>
        <span className="ib-loc">{scenario.location}</span>
        <span className="ib-clock mono">{scenario.clock}</span>
      </div>
      <div className="ib-title">{scenario.incident}</div>
      <div className="ib-thesis">{scenario.thesis}</div>
      <div className="ib-brief-rows">
        {scenario.brief.slice(0, 4).map((b, i) => (
          <div key={i} className="ib-row">
            <span className="ib-arrow">›</span>
            {b}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── EVIDENCE RAIL ───────────────────────────────────────────────────────
function EvidenceRail({ evidence }: { evidence: EvidenceItem[] }) {
  const [selected, setSelected] = useState<string|null>(null);

  return (
    <div className="sub-panel evidence-panel">
      <div className="sub-panel-head">
        <span className="sub-panel-label"><GitMerge size={12} /> Evidence Rail</span>
        <span className="badge">{evidence.length}</span>
      </div>
      <div className="sub-panel-body">
        {evidence.length === 0 ? (
          <div className="empty-state"><Eye size={20} strokeWidth={1.2} /><span>No evidence yet</span></div>
        ) : (
          <div className="ev-list">
            {evidence.map(ev => (
              <div
                key={ev.id}
                className={`ev-row ${selected === ev.id ? "sel" : ""}`}
                onClick={() => setSelected(s => s === ev.id ? null : ev.id)}
              >
                <div className={`ev-kind-icon ${ev.kind}`}>{evKindIcon(ev.kind)}</div>
                <div className="ev-main">
                  <div className="ev-source">{ev.source}</div>
                  <div className="ev-summary">{ev.summary}</div>
                  {selected === ev.id && ev.transcript && (
                    <div className="ev-transcript">"{ev.transcript}"</div>
                  )}
                </div>
                <span className={`ev-pct ${confColor(ev.confidence)}`}>{Math.round(ev.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── RESPONSE ACTIONS ────────────────────────────────────────────────────
function ResponseActions({ scenario, onBroadcast }: { scenario: Scenario; onBroadcast: () => void }) {
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const toggle = (id: string) => setApproved(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const actions = scenario.actions;

  return (
    <div className="sub-panel actions-panel">
      <div className="sub-panel-head">
        <span className="sub-panel-label"><Siren size={12} /> Response Actions</span>
        <div style={{display:"flex",gap:6,alignItems:"center"}}>
          {approved.size > 0 && <span className="badge green">{approved.size} approved</span>}
          <span className="badge">{actions.length} options</span>
        </div>
      </div>
      <div className="sub-panel-body">
        {actions.length === 0 ? (
          <div className="empty-state"><Siren size={20} strokeWidth={1.2} /><span>Awaiting model output</span></div>
        ) : (
          <div className="action-list">
            {actions.map((a, idx) => (
              <div key={a.id} className={`action-card ${priorityClass(a.impact)} ${approved.has(a.id) ? "approved" : ""}`}>
                <div className="action-top">
                  <div className="action-index">{idx + 1}</div>
                  <div className="action-priority-bar" />
                  <div className="action-content">
                    <div className="action-title">{a.title}</div>
                    <div className="action-caveat">{a.caveat}</div>
                  </div>
                </div>
                <div className="action-bottom">
                  <div className="action-stats">
                    <div className="action-stat"><span className="stat-lbl">ETA</span><span className="stat-val eta">{a.etaMinutes}m</span></div>
                    <div className="action-stat"><span className="stat-lbl">Impact</span><span className="stat-val impact">{a.impact}%</span></div>
                    <div className="action-stat"><span className="stat-lbl">Conf</span><span className={`stat-val ${confColor(a.confidence)}`}>{Math.round(a.confidence * 100)}%</span></div>
                    <div className="action-stat"><span className="stat-lbl">Owner</span><span className="stat-val">{a.owner}</span></div>
                  </div>
                  <button className={`approve-btn ${approved.has(a.id) ? "done" : ""}`} onClick={() => toggle(a.id)}>
                    {approved.has(a.id) ? <><CheckCircle2 size={11} /> Approved</> : <><ChevronRight size={11} /> Approve</>}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {/* Emergency Broadcast Button */}
        <button className="broadcast-btn" onClick={onBroadcast} disabled={approved.size === 0} title={approved.size === 0 ? "Approve at least one action first" : "Broadcast approved actions over PA"}>
          <Megaphone size={14} />
          Approve Broadcast{approved.size > 0 ? ` (${approved.size})` : ""}
        </button>
      </div>
    </div>
  );
}

// ─── UNCERTAINTY LEDGER ──────────────────────────────────────────────────
function UncertaintyLedger({ scenario }: { scenario: Scenario }) {
  const items = scenario.uncertainties ?? [];
  return (
    <div className="sub-panel unc-panel">
      <div className="sub-panel-head">
        <span className="sub-panel-label"><HelpCircle size={12} /> Uncertainty Ledger</span>
        <span className={`badge ${items.length > 0 ? "amber" : ""}`}>{items.length}</span>
      </div>
      <div className="sub-panel-body">
        {items.length === 0 ? (
          <div className="empty-state"><HelpCircle size={20} strokeWidth={1.2} /><span>No open uncertainties</span></div>
        ) : (
          <div className="unc-list">
            {items.map(u => (
              <div key={u.id} className={`unc-row ${u.severity}`}>
                <div className="unc-dot" />
                <div className="unc-body">
                  <div className="unc-kind">{u.kind.replace(/_/g," ")}</div>
                  <div className="unc-title">{u.title}</div>
                  <div className="unc-detail">{u.detail}</div>
                </div>
                <div className={`unc-sev-badge ${u.severity}`}>{u.severity}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── GPU TELEMETRY ────────────────────────────────────────────────────────
function GpuTelemetry({ scenario }: { scenario: Scenario }) {
  if (!scenario.gpu?.length) return null;
  return (
    <div className="gpu-strip">
      <span className="gpu-strip-label"><Cpu size={11} /> MI300X</span>
      {scenario.gpu.map((lane, i) => (
        <div key={i} className="gpu-lane">
          <span className="gpu-lane-name">{lane.label}</span>
          <div className="gpu-lane-bar"><div className="gpu-lane-fill" style={{ width:`${lane.utilization}%` }} /></div>
          <span className="gpu-lane-pct">{lane.utilization}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── PIPELINE TICKER (compact) ────────────────────────────────────────────
function PipelineTicker({ agentState }: { agentState: OrchestratorState }) {
  const s = agentState;
  if (s.agentStatus === "idle") return null;
  return (
    <div className={`pipeline-ticker ticker-${s.agentStatus}`}>
      <Zap size={11} />
      <span className="ticker-id mono">{s.lastJobId?.slice(0,10) ?? "—"}</span>
      <span className="ticker-stage">{s.agentStage}</span>
      {s.agentStatus === "running" && (
        <div className="ticker-bar">
          <div className="ticker-fill" style={{width:`${Math.round(s.agentProgress*100)}%`}} />
        </div>
      )}
      {s.agentStatus === "complete" && <CheckCircle2 size={11} className="ticker-done" />}
      {s.agentStatus === "error" && <X size={11} className="ticker-err" />}
    </div>
  );
}

// ─── VOICE CHANNEL (compact sidebar) ─────────────────────────────────────
const DEMO_VOICE = [
  { source_uuid: "SRC-AUD-S2347", speaker: "S2347", role: "sector supervisor", location: "Sector 4", transcript: "Supervisor S2347 from Sector 4 — smoke is coming from the tanker area and spreading across the sector.", file: "/audio/2347-Sector4.aac" },
  { source_uuid: "SRC-AUD-S2451", speaker: "S2451", role: "nearby sector supervisor", location: "Sector 5", transcript: "Supervisor S2451 from Sector 5 — strange smell in the air for the past ten minutes.", file: "/audio/2451-sector5.aac" },
];
type VMsg = { id: number; type: "hq"|"field"; sender: string; location: string; text: string; file?: string };

function VoiceChannel({ onIngest }: { onIngest: (jobId:string, backend:string) => void }) {
  const [micActive,  setMicActive]  = useState(false);
  const [messages,   setMessages]   = useState<VMsg[]>([]);
  const [processing, setProcessing] = useState(false);
  const histRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (histRef.current) histRef.current.scrollTop = histRef.current.scrollHeight;
  }, [messages]);

  const trigger = async () => {
    setProcessing(true);
    setMessages(p => [...p, { id: Date.now(), type: "hq", sender: "COMMAND HQ", location: "Ops Center", text: "HQ to all sectors — suspected breach at Tank B-4. Report status immediately." }]);
    await new Promise(r => setTimeout(r, 1400));
    for (const rep of DEMO_VOICE) {
      setMessages(p => [...p, { id: Date.now(), type: "field", sender: rep.speaker, location: rep.location, text: rep.transcript, file: rep.file }]);
      const audio = new Audio(rep.file);
      void audio.play().catch(() => {});
      await new Promise<void>(res => { audio.onended = () => res(); setTimeout(res, 9000); });
      await new Promise(r => setTimeout(r, 600));
    }
    try {
      const now = Date.now() / 1000;
      const sensorTrace = Array.from({ length: 30 }, (_, i) => {
        const t = i * 3;
        const gas = t < 18 ? 2.4 + Math.sin(t) * 0.3 : t < 60 ? 2.4 + (t - 18) * 0.72 : 32;
        return { timestamp: now - (29 - i) * 3, gas_ppm: Math.round(gas * 10) / 10, wind_speed_mps: 3.7, wind_direction_deg: 225 };
      });
      const fetchAudio = async (url: string, name: string) => { const r = await fetch(url); const b = await r.blob(); return new File([b], name, { type: "audio/aac" }); };
      const files = await Promise.all(DEMO_VOICE.map(v => fetchAudio(v.file, v.file.split("/").pop()!)));
      const form = new FormData();
      form.append("location", "Sector 4 — Tank B-4 Flange, Northgate LNG Terminal");
      form.append("field_notes", "Multi-sector voice confirmation of breach.");
      form.append("sensor_count", String(sensorTrace.length));
      form.append("sensor_trace", JSON.stringify(sensorTrace));
      form.append("voice_manifest", JSON.stringify(DEMO_VOICE));
      for (const f of files) form.append("audio", f);
      const res = await fetch(`${API_BASE}/api/ingest/upload`, { method:"POST", body:form });
      if (res.ok) { const j = await res.json(); onIngest(j.job_id, j.backend); }
    } catch(e) { console.error("Voice ingest error", e); }
    setProcessing(false);
  };

  const toggleMic = () => {
    if (processing) return;
    if (micActive) { setMicActive(false); void trigger(); }
    else setMicActive(true);
  };

  return (
    <div className="sub-panel voice-panel">
      <div className="sub-panel-head">
        <span className="sub-panel-label"><Radio size={12} /> Command Voice</span>
        {processing && <span className="badge amber">Processing</span>}
      </div>
      <div className="voice-history" ref={histRef}>
        {messages.length === 0 ? (
          <div className="empty-state small"><Radio size={16} strokeWidth={1.5} /><span>No active comms</span></div>
        ) : messages.map(m => (
          <div key={m.id} className={`vmsg ${m.type}`}>
            <div className="vmsg-meta"><span className="vmsg-sender">{m.sender}</span><span className="vmsg-loc">{m.location}</span></div>
            <div className="vmsg-text">{m.text}</div>
            {m.file && <audio controls src={m.file} style={{width:"100%",height:22,marginTop:3}} />}
          </div>
        ))}
      </div>
      <div className="voice-controls">
        <button className={`mic-btn ${micActive ? "active" : ""}`} onClick={toggleMic} disabled={processing}>
          <Mic size={16} />
        </button>
        <div className={`waveform ${micActive ? "active" : ""}`}>
          {Array.from({length:7},(_,i)=><div key={i} className="wv-bar"/>)}
        </div>
        <button className="send-btn" onClick={toggleMic} disabled={!micActive || processing}>
          <Send size={11} /> Dispatch
        </button>
      </div>
    </div>
  );
}

// ─── BROADCAST TOAST ──────────────────────────────────────────────────────
function BroadcastToast({ onClose }: { onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 6000); return () => clearTimeout(t); }, [onClose]);
  return (
    <div className="broadcast-toast">
      <Megaphone size={16} />
      <div>
        <div className="bcast-title">PA Broadcast Dispatched</div>
        <div className="bcast-sub">Evacuation announcement queued for site speaker system</div>
      </div>
      <button onClick={onClose}><X size={14} /></button>
    </div>
  );
}

// ─── APP ROOT ─────────────────────────────────────────────────────────────
export function App() {
  const orch = useOrchestrator();
  const [showBroadcast, setShowBroadcast] = useState(false);

  const scenario = orch.scenario;
  const critZ    = scenario.zones.filter(z => z.severity === "critical").length;
  const vllm     = scenario.gpu?.some(g => g.utilization > 0) ?? false;

  const handleBroadcast = () => {
    setShowBroadcast(true);
  };

  return (
    <div className="shell">
      {/* TOPBAR */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon"><Activity size={16} /></div>
          <div className="brand-text">
            <h1>VESPERGRID</h1>
            <p>Multimodal Ops Command · AMD MI300X</p>
          </div>
        </div>

        <div className="topbar-center">
          <PipelineTicker agentState={orch} />
        </div>

        <div className="topbar-right">
          {critZ > 0 && (
            <div className="alert-chip">
              <AlertTriangle size={11} /> {critZ} Critical Zone{critZ > 1 ? "s" : ""}
            </div>
          )}
          <div className={`status-chip ${vllm ? "" : "warn"}`}>
            <div className="dot" /> {vllm ? "Qwen-VL · MI300X Online" : "Deterministic Mode"}
          </div>
        </div>
      </header>

      {/* ORCHESTRATOR BAR */}
      <AgentStatusBar state={orch} />

      {/* HERO FEEDS — full width */}
      <HeroFeeds />

      {/* KPI STRIP */}
      <KpiStrip scenario={scenario} />

      {/* MAIN WORKSPACE — 3 columns */}
      <main className="workspace">

        {/* LEFT: Incident brief + Evidence */}
        <div className="col">
          <IncidentBrief scenario={scenario} />
          <EvidenceRail evidence={scenario.evidence} />
        </div>

        {/* CENTER: Actions + GPU */}
        <div className="col col-center">
          <ResponseActions scenario={scenario} onBroadcast={handleBroadcast} />
          <GpuTelemetry scenario={scenario} />
        </div>

        {/* RIGHT: Uncertainty + Voice */}
        <div className="col">
          <UncertaintyLedger scenario={scenario} />
          <VoiceChannel onIngest={(id, b) => orch.refresh()} />
        </div>

      </main>

      {/* BROADCAST TOAST */}
      {showBroadcast && <BroadcastToast onClose={() => setShowBroadcast(false)} />}
    </div>
  );
}
