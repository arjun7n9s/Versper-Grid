import {
  Activity, AlertTriangle, CheckCircle2, ChevronRight,
  Cpu, FileText, HelpCircle, Mic, Radio, Send,
  ShieldAlert, Siren, Video, Waves, Zap, Volume2,
  GitMerge, Brain, Eye, Megaphone, TrendingUp, Clock,
  X, RefreshCw, MapPin, MicOff
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
      {/* Viewport */}
      <div className="hero-viewport-wrap">
        {isLive && !imgErr[active] ? (
          <img key={active} src={src} alt={activeFeed.label} className="hero-img"
            onLoad={() => setImgErr(p=>({...p,[active]:false}))}
            onError={() => setImgErr(p=>({...p,[active]:true}))} />
        ) : (
          <div className="hero-no-signal">
            <Video size={36} strokeWidth={1}/>
            <span>{anyLive?"Switching feed…":"Awaiting camera signal"}</span>
          </div>
        )}
        <div className="hud-tl">
          <span className="hud-chip rec">● REC</span>
          <span className="hud-chip label">{activeFeed.icon}</span>
          <span className="hud-chip label">{activeFeed.label}</span>
        </div>
        <div className="hud-tr">
          <span className="hud-ts">{ts||"--:--:--"}</span>
        </div>
        <div className="hud-bl">
          <span className="hud-chip label mono">NORTHGATE LNG — TANK B-4 SECTOR</span>
        </div>
        <div className="hud-br">
          <span className={`hud-chip ${isLive?"live-on":"live-off"}`}>{isLive?"LIVE":"NO SIGNAL"}</span>
        </div>
        <div className="hero-scanlines"/>
      </div>
      {/* Vertical camera tabs on the right */}
      <div className="hero-tabs-wrap">
        {FEEDS.map(f=>(
          <button key={f.id}
            className={`hero-tab ${active===f.id?"active":""}`}
            onClick={()=>{setActive(f.id);setImgErr(p=>({...p,[f.id]:false}))}}
          >
            <span className="hero-tab-icon">{f.icon}</span>
            <span className="hero-tab-label">{f.label}</span>
            {avail[f.id]&&<span className="hero-tab-live"/>}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── ORCHESTRATOR AGENT ───────────────────────────────────────────────────
type JobEntry = { job_id: string; backend: string; stage: string; progress: number; status: "queued"|"running"|"complete"|"error"; ts: number; };
type OrchestratorState = {
  scenario: Scenario;
  lastJobId: string | null;
  lastBackend: string | null;
  lastUpdated: number | null;
  agentStage: string;
  agentProgress: number;
  agentStatus: "idle" | "running" | "complete" | "error";
  jobCount: number;
  jobs: JobEntry[];
};

function useOrchestrator(): OrchestratorState & { refresh: () => void; addVoiceEvidence: (items: EvidenceItem[]) => void } {
  const [state, setState] = useState<OrchestratorState>({
    scenario:      fallbackScenario,
    lastJobId:     null,
    lastBackend:   null,
    lastUpdated:   null,
    agentStage:    "idle",
    agentProgress: 0,
    agentStatus:   "idle",
    jobCount:      0,
    jobs:          [],
  });
  const watched = useRef<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval>|null>(null);

  const watchJob = useCallback((jobId: string, backend: string) => {
    if (watched.current.has(jobId)) return;
    watched.current.add(jobId);
    const entry: JobEntry = { job_id: jobId, backend, stage: "queued", progress: 0, status: "queued", ts: Date.now() };
    setState(p => ({ ...p, jobs: [entry, ...p.jobs].slice(0, 20) }));
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
            jobs: p.jobs.map(j => j.job_id === jobId ? { ...j, stage: ev.stage ?? stage, progress: ev.progress ?? 0, status: stage === "error" ? "error" : "running" } : j),
          }));
        } catch { /* */ }
      });
    }
    es.addEventListener("snapshot", (e: Event) => {
      try {
        const snap = JSON.parse((e as MessageEvent).data);
        es.close();
        if (snap.status === "complete" && snap.result) {
          const incoming = snap.result as Scenario;
          setState(p => {
            // Preserve voice evidence added locally that isn't in the new snapshot
            const incomingIds = new Set(incoming.evidence.map((ev: EvidenceItem) => ev.id));
            const voiceOnly = p.scenario.evidence.filter(ev => !incomingIds.has(ev.id) && ev.kind === "audio");
            return {
              ...p,
              scenario: {
                ...incoming,
                evidence: [...incoming.evidence, ...voiceOnly],
              },
              lastJobId:     jobId,
              lastBackend:   backend,
              lastUpdated:   Date.now(),
              agentStage:    "complete",
              agentProgress: 1,
              agentStatus:   "complete",
              jobCount:      p.jobCount + 1,
              jobs: p.jobs.map(j => j.job_id === jobId ? { ...j, stage: "complete", progress: 1, status: "complete" } : j),
            };
          });
        }
      } catch { /* */ }
    });
    es.onerror = () => {
      es.close();
      setState(p => ({
        ...p,
        ...(p.agentStatus === "running" ? { agentStatus: "error" as const, agentStage: "connection lost" } : {}),
        jobs: p.jobs.map(j => j.job_id === jobId && j.status === "running" ? { ...j, status: "error" as const } : j),
      }));
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

  const addVoiceEvidence = useCallback((items: EvidenceItem[]) => {
    setState(p => ({
      ...p,
      scenario: {
        ...p.scenario,
        evidence: [
          ...p.scenario.evidence,
          ...items.filter(it => !p.scenario.evidence.find(e => e.id === it.id)),
        ],
      },
    }));
  }, []);

  return { ...state, refresh, addVoiceEvidence };
}

// ─── AGENT PILL (compact topbar) ──────────────────────────────────────────
function AgentPill({ state }: { state: OrchestratorState & { refresh: () => void } }) {
  const pct = Math.round(state.agentProgress * 100);
  const sinceMs = state.lastUpdated ? Date.now() - state.lastUpdated : null;
  const sinceStr = sinceMs == null ? null : sinceMs < 60000 ? `${Math.round(sinceMs/1000)}s ago` : `${Math.round(sinceMs/60000)}m ago`;
  return (
    <div className={`agent-pill agent-${state.agentStatus}`}>
      <Brain size={11} className="agent-pill-icon" />
      <span className="agent-pill-label">ORCH</span>
      <span className="agent-pill-stage">{state.agentStage.toUpperCase()}</span>
      {state.agentStatus === "running" && (
        <div className="agent-pill-bar"><div className="agent-pill-fill" style={{width:`${pct}%`}} /></div>
      )}
      {sinceStr && <span className="agent-pill-since">{sinceStr}</span>}
      <button className="agent-pill-refresh" onClick={state.refresh}><RefreshCw size={10}/></button>
    </div>
  );
}

// ─── KPI BLOCK (left column) ──────────────────────────────────────────────
function KpiBlock({ scenario }: { scenario: Scenario }) {
  const pct    = Math.round(scenario.confidence * 100);
  const gas    = scenario.evidence.find(e => e.kind === "sensor");
  const gasPpm = gas?.metadata?.["latest_ppm"] as number | undefined;
  const critZ  = scenario.zones.filter(z => z.severity === "critical").length;
  const col    = confColor(scenario.confidence);
  return (
    <div className="kpi-block">
      <div className="kpi-row">
        <div className="kpi-cell">
          <div className="kpi-cell-label">AI Confidence</div>
          <div className={`kpi-cell-value ${col}`}>{pct}%</div>
          <div className="kpi-cell-bar"><div className="kpi-cell-fill" style={{width:`${pct}%`,background:`var(--${col})`}} /></div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-cell-label">Evidence</div>
          <div className="kpi-cell-value cyan">{scenario.evidence.length}</div>
        </div>
      </div>
      <div className="kpi-row">
        <div className="kpi-cell">
          <div className="kpi-cell-label">Gas ppm</div>
          <div className={`kpi-cell-value ${gasPpm && gasPpm>20?"red":gasPpm?"amber":"dim"}`}>
            {gasPpm!=null ? gasPpm.toFixed(1) : "—"}
          </div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-cell-label">Critical Zones</div>
          <div className={`kpi-cell-value ${critZ>0?"red":"dim"}`}>{critZ}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-cell-label">Actions</div>
          <div className="kpi-cell-value amber">{scenario.actions.length}</div>
        </div>
        <div className="kpi-cell">
          <div className="kpi-cell-label">Flags</div>
          <div className={`kpi-cell-value ${scenario.uncertainties?.length?"amber":"dim"}`}>
            {scenario.uncertainties?.length ?? 0}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── INCIDENT BRIEF ───────────────────────────────────────────────────────
function IncidentBrief({ scenario }: { scenario: Scenario }) {
  return (
    <div className="incident-brief">
      <div className="ib-meta">
        <div className="severity-tag"><ShieldAlert size={10}/> Critical Incident</div>
        <span className="ib-loc">{scenario.location}</span>
        <span className="ib-clock">{scenario.clock}</span>
      </div>
      <div className="ib-title">{scenario.incident}</div>
      <div className="ib-thesis">{scenario.thesis}</div>
      <div className="ib-points">
        {scenario.brief.slice(0,4).map((b,i)=>(
          <div key={i} className="ib-point">{b}</div>
        ))}
      </div>
    </div>
  );
}

// ─── EVIDENCE RAIL ───────────────────────────────────────────────────────
function EvidenceRail({ evidence }: { evidence: EvidenceItem[] }) {
  const [selected, setSelected] = useState<string|null>(null);
  return (
    <div className="panel grow">
      <div className="panel-head">
        <span className="panel-title"><GitMerge size={11}/> Evidence Rail</span>
        <span className="badge">{evidence.length}</span>
      </div>
      <div className="panel-body">
        {evidence.length===0 ? (
          <div className="empty"><Eye size={20} strokeWidth={1.2}/><span>No evidence yet</span></div>
        ) : (
          <div className="ev-list">
            {evidence.map(ev=>(
              <div key={ev.id} className={`ev-row ${selected===ev.id?"sel":""}`}
                onClick={()=>setSelected(s=>s===ev.id?null:ev.id)}>
                <div className={`ev-icon ${ev.kind}`}>{evKindIcon(ev.kind)}</div>
                <div className="ev-main">
                  <div className="ev-source">{ev.source}</div>
                  <div className="ev-summary">{ev.summary}</div>
                  {selected===ev.id&&ev.assetUrl&&ev.kind==="image"&&(
                    <img
                      src={`${API_BASE}${ev.assetUrl}?t=${Date.now()}`}
                      alt={ev.source}
                      className="ev-thumb"
                      onError={e=>{(e.target as HTMLImageElement).style.display="none"}}
                    />
                  )}
                  {selected===ev.id&&ev.transcript&&(
                    <div className="ev-transcript">"{ev.transcript}"</div>
                  )}
                </div>
                <span className={`ev-pct ${confColor(ev.confidence)}`}>{Math.round(ev.confidence*100)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── RESPONSE ACTIONS ────────────────────────────────────────────────────
function ResponseActions({ scenario, onBroadcast }: { scenario: Scenario; onBroadcast: (approvedTitles: string[]) => void }) {
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const toggle = (id:string)=>setApproved(p=>{const n=new Set(p);n.has(id)?n.delete(id):n.add(id);return n});
  const actions = scenario.actions;
  return (
    <div className="panel grow">
      <div className="panel-head">
        <span className="panel-title"><Siren size={11}/> Response Actions</span>
        <div style={{display:"flex",gap:5,alignItems:"center"}}>
          {approved.size>0&&<span className="badge green">{approved.size} approved</span>}
          <span className="badge">{actions.length} options</span>
        </div>
      </div>
      <div className="panel-body">
        {actions.length===0 ? (
          <div className="empty"><Siren size={20} strokeWidth={1.2}/><span>Awaiting model output</span></div>
        ) : (
          <div className="action-list">
            {actions.map((a,idx)=>(
              <div key={a.id} className={`action-card ${priorityClass(a.impact)} ${approved.has(a.id)?"approved":""}`}>
                <div className="action-top">
                  <span className="action-num">{idx+1}</span>
                  <div className="action-bar"/>
                  <div className="action-content">
                    <div className="action-title">{a.title}</div>
                    <div className="action-caveat">{a.caveat}</div>
                  </div>
                </div>
                <div className="action-foot">
                  <div className="action-stats">
                    <div className="astat"><span className="astat-l">ETA</span><span className="astat-v eta">{a.etaMinutes}m</span></div>
                    <div className="astat"><span className="astat-l">Impact</span><span className="astat-v impact">{a.impact}%</span></div>
                    <div className="astat"><span className="astat-l">Conf</span><span className={`astat-v ${confColor(a.confidence)}`}>{Math.round(a.confidence*100)}%</span></div>
                    <div className="astat"><span className="astat-l">Owner</span><span className="astat-v" style={{fontSize:9}}>{a.owner}</span></div>
                  </div>
                  <button className={`approve-btn ${approved.has(a.id)?"done":""}`} onClick={()=>toggle(a.id)}>
                    {approved.has(a.id)?<><CheckCircle2 size={10}/> Approved</>:<><ChevronRight size={10}/> Approve</>}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="broadcast-btn" onClick={() => {
          const titles = actions.filter(a=>approved.has(a.id)).map(a=>a.title);
          onBroadcast(titles);
        }} disabled={approved.size===0}>
          <Megaphone size={13}/> Approve Broadcast{approved.size>0?` (${approved.size})`:""}
        </button>
      </div>
    </div>
  );
}

// ─── UNCERTAINTY LEDGER ──────────────────────────────────────────────────
function UncertaintyLedger({ scenario }: { scenario: Scenario }) {
  const items = scenario.uncertainties ?? [];
  return (
    <div className="panel ledger-panel">
      <div className="panel-head">
        <span className="panel-title"><HelpCircle size={11}/> Uncertainty Ledger</span>
        <span className={`badge ${items.length>0?"amber":""}`}>{items.length}</span>
      </div>
      <div className="panel-body">
        {items.length===0 ? (
          <div className="empty"><HelpCircle size={20} strokeWidth={1.2}/><span>No open uncertainties</span></div>
        ) : (
          <div className="unc-list">
            {items.map(u=>(
              <div key={u.id} className={`unc-row ${u.severity}`}>
                <div className="unc-dot"/>
                <div className="unc-body">
                  <div className="unc-kind">{u.kind.replace(/_/g," ")}</div>
                  <div className="unc-title">{u.title}</div>
                  <div className="unc-detail">{u.detail}</div>
                </div>
                <div className={`unc-badge ${u.severity}`}>{u.severity}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── ZONE MAP ─────────────────────────────────────────────────────────────
const SEVERITY_COLORS: Record<string, string> = {
  critical: "rgba(239,68,68,0.55)",
  elevated: "rgba(245,158,11,0.45)",
  watch:    "rgba(0,212,245,0.25)",
};
const SEVERITY_STROKE: Record<string, string> = {
  critical: "#ef4444",
  elevated: "#f59e0b",
  watch:    "#00d4f5",
};

function ZoneMap({ scenario }: { scenario: Scenario }) {
  const { zones } = scenario;
  if (!zones.length) return null;

  const evac = zones.find(z => z.metadata?.is_exclusion_cone);
  const conePoints: [number, number][] = evac?.metadata?.cone_points as [number,number][] ?? [];
  const polyStr = conePoints.map(([x,y]) => `${x},${y}`).join(" ");

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title"><MapPin size={11}/> Zone Map</span>
        <span className="badge">{zones.length} zones</span>
      </div>
      <div className="zone-map-wrap">
        <svg viewBox="0 0 100 100" className="zone-map-svg" preserveAspectRatio="xMidYMid meet">
          {/* Grid lines */}
          {[25,50,75].map(v => (
            <g key={v}>
              <line x1={v} y1={0} x2={v} y2={100} stroke="rgba(255,255,255,0.04)" strokeWidth="0.3"/>
              <line x1={0} y1={v} x2={100} y2={v} stroke="rgba(255,255,255,0.04)" strokeWidth="0.3"/>
            </g>
          ))}

          {/* Evac cone polygon */}
          {conePoints.length === 3 && (
            <polygon
              points={polyStr}
              fill="rgba(239,68,68,0.12)"
              stroke="#ef4444"
              strokeWidth="0.6"
              strokeDasharray="2 1.5"
            />
          )}

          {/* Risk zone circles */}
          {zones.filter(z => !z.metadata?.is_exclusion_cone).map(z => (
            <g key={z.id}>
              <circle
                cx={z.x} cy={z.y} r={z.radius}
                fill={SEVERITY_COLORS[z.severity] ?? SEVERITY_COLORS.watch}
                stroke={SEVERITY_STROKE[z.severity] ?? SEVERITY_STROKE.watch}
                strokeWidth="0.5"
              />
              <text x={z.x} y={z.y + 1} textAnchor="middle"
                fontSize="4.5" fill="#fff" fontFamily="monospace" opacity={0.85}>
                {z.label.split(" ")[0]}
              </text>
            </g>
          ))}

          {/* Wind arrow if evac zone present */}
          {evac && (() => {
            const deg = evac.metadata?.wind_direction_deg as number ?? 225;
            const rad = (270 - deg) * Math.PI / 180;
            const ax = evac.x + 7 * Math.cos(rad);
            const ay = evac.y - 7 * Math.sin(rad);
            return (
              <g>
                <line x1={evac.x} y1={evac.y} x2={ax} y2={ay}
                  stroke="#f59e0b" strokeWidth="0.8" markerEnd="url(#arr)"/>
              </g>
            );
          })()}

          <defs>
            <marker id="arr" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto">
              <path d="M0,0 L4,2 L0,4 z" fill="#f59e0b"/>
            </marker>
          </defs>
        </svg>

        {evac && (
          <div className="zone-map-legend">
            <span className="zml-item evac">▲ Evac cone</span>
            <span className="zml-item">
              Wind {(evac.metadata?.wind_speed_mps as number)?.toFixed(1)} m/s @ {(evac.metadata?.wind_direction_deg as number)?.toFixed(0)}°
            </span>
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
      <span className="gpu-strip-lbl"><Cpu size={10}/> MI300X</span>
      {scenario.gpu.map((lane,i)=>(
        <div key={i} className="gpu-lane">
          <span className="gpu-lane-name">{lane.label.split('·')[0].trim()}</span>
          <div className="gpu-lane-bar"><div className="gpu-lane-fill" style={{width:`${lane.utilization}%`}}/></div>
          <span className="gpu-lane-pct">{lane.utilization}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── PIPELINE TICKER (compact topbar pill) ────────────────────────────────
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

// ─── JOB LIST (left panel, restores old pipeline feed) ────────────────────
function JobList({ jobs }: { jobs: JobEntry[] }) {
  return (
    <div className="panel job-panel">
      <div className="panel-head">
        <span className="panel-title"><Zap size={11}/> Pipeline Jobs</span>
        <span className="badge">{jobs.length}</span>
      </div>
      <div className="panel-body">
        {jobs.length===0 ? (
          <div className="empty"><Activity size={18} strokeWidth={1.2}/><span>Awaiting ingest</span></div>
        ) : (
          <div className="job-list">
            {jobs.map(j=>(
              <div key={j.job_id} className={`job-row job-${j.status}`}>
                <div className="job-row-top">
                  <span className="job-id">{j.job_id.slice(0,14)}…</span>
                  <span className="job-stage-badge">{j.stage}</span>
                </div>
                <div className="job-bar"><div className="job-bar-fill" style={{width:`${Math.round(j.progress*100)}%`}}/></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── VOICE CHANNEL ────────────────────────────────────────────────────────
const DEMO_VOICE = [
  { source_uuid: "SRC-AUD-S2347", speaker: "S2347", role: "sector supervisor", location: "Sector 4", transcript: "Supervisor S2347 from Sector 4 — smoke is coming from the tanker area and spreading across the sector.", file: "/audio/2347-Sector4.aac" },
  { source_uuid: "SRC-AUD-S2451", speaker: "S2451", role: "nearby sector supervisor", location: "Sector 5", transcript: "Supervisor S2451 from Sector 5 — strange smell in the air for the past ten minutes.", file: "/audio/2451-sector5.aac" },
];
type VMsg = { id: number; type: "hq"|"field"; sender: string; location: string; text: string; file?: string };

function VoiceChannel({ onIngest, onVoiceEvidence }: { onIngest: () => void; onVoiceEvidence: (items: EvidenceItem[]) => void }) {
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
    const voiceEvItems: EvidenceItem[] = [];
    for (const rep of DEMO_VOICE) {
      setMessages(p => [...p, { id: Date.now(), type: "field", sender: rep.speaker, location: rep.location, text: rep.transcript, file: rep.file }]);
      // Immediately add to evidence so count updates without waiting for VLM
      const evItem: EvidenceItem = {
        id: rep.source_uuid,
        sourceUuid: rep.source_uuid,
        source: `Voice · ${rep.speaker} · ${rep.location}`,
        kind: "audio",
        summary: rep.transcript,
        confidence: 0.78,
        signal: "voice_report",
        transcript: rep.transcript,
      };
      voiceEvItems.push(evItem);
      onVoiceEvidence([evItem]);
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
      if (res.ok) { onIngest(); }
    } catch(e) { console.error("Voice ingest error", e); }
    setProcessing(false);
  };

  const toggleMic = () => {
    if (processing) return;
    if (micActive) { setMicActive(false); void trigger(); }
    else setMicActive(true);
  };

  return (
    <div className="panel grow">
      <div className="panel-head">
        <span className="panel-title"><Radio size={11}/> Command Voice</span>
        {processing&&<span className="badge amber">Processing</span>}
      </div>
      <div className="voice-history" ref={histRef}>
        {messages.length===0 ? (
          <div className="empty"><Radio size={16} strokeWidth={1.5}/><span>No active comms</span></div>
        ) : messages.map(m=>(
          <div key={m.id} className={`vmsg ${m.type}`}>
            <div className="vmsg-meta"><span className="vmsg-sender">{m.sender}</span><span className="vmsg-loc">{m.location}</span></div>
            <div className="vmsg-text">{m.text}</div>
            {m.file&&<audio controls src={m.file} style={{width:"100%",height:22,marginTop:3}}/>}
          </div>
        ))}
      </div>
      <div className="voice-controls">
        <button className={`mic-btn ${micActive?"active":""}`} onClick={toggleMic} disabled={processing}>
          {micActive ? <MicOff size={15}/> : <Mic size={15}/>}
        </button>
        <div className={`waveform ${micActive?"active":""}`}>
          {Array.from({length:7},(_,i)=><div key={i} className="wv-bar"/>)}
        </div>
        <button className="send-btn" onClick={toggleMic} disabled={!micActive||processing}>
          <Send size={10}/> Dispatch
        </button>
      </div>
    </div>
  );
}

// ─── BROADCAST TOAST ──────────────────────────────────────────────────────
function BroadcastToast({ scenario, approvedTitles, onClose }: {
  scenario: Scenario;
  approvedTitles: string[];
  onClose: () => void;
}) {
  const [script, setScript] = useState("");
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState("");
  const audioRef = useRef<HTMLAudioElement|null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const windInfo = scenario.evidence
          .find(e => e.kind === "sensor")?.summary?.match(/wind.+/i)?.[0] ?? "";
        const res = await fetch(`${API_BASE}/api/broadcast/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            incident: scenario.incident,
            location: scenario.location,
            approved_actions: approvedTitles,
            wind_info: windInfo,
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setScript(data.script ?? "");
        setLoading(false);
        if (data.audio_url) {
          const audio = new Audio(`${API_BASE}${data.audio_url}?t=${Date.now()}`);
          audioRef.current = audio;
          audio.onplay  = () => setPlaying(true);
          audio.onended = () => setPlaying(false);
          audio.play().catch(() => setPlaying(false));
        } else {
          setError("TTS unavailable — script generated only");
        }
      } catch (e: any) {
        if (!cancelled) { setLoading(false); setError(String(e)); }
      }
    };
    run();
    const t = setTimeout(onClose, 30000);
    return () => { cancelled = true; clearTimeout(t); audioRef.current?.pause(); };
  }, []);

  return (
    <div className="broadcast-toast">
      <div className="bcast-icon">
        <Megaphone size={18} className={playing ? "bcast-pulse" : ""}/>
      </div>
      <div className="bcast-body">
        <div className="bcast-title">
          {loading ? "Generating PA announcement…" : playing ? "⏵ Broadcasting…" : "PA Broadcast Ready"}
        </div>
        {script && <div className="bcast-script">{script}</div>}
        {error  && <div className="bcast-err">{error}</div>}
      </div>
      <button className="bcast-close" onClick={onClose}><X size={13}/></button>
    </div>
  );
}

// ─── APP ROOT ─────────────────────────────────────────────────────────────
export function App() {
  const orch = useOrchestrator();
  const [showBroadcast, setShowBroadcast] = useState(false);
  const [broadcastTitles, setBroadcastTitles] = useState<string[]>([]);

  const scenario = orch.scenario;
  const critZ    = scenario.zones.filter(z => z.severity === "critical").length;
  const vllm     = scenario.gpu?.some(g => g.utilization > 0) ?? false;

  return (
    <div className="shell">

      {/* ── TOP BAR ── */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon"><Activity size={18} /></div>
          <div className="brand-text">
            <h1>VESPERGRID</h1>
            <p>Multimodal Ops Command · AMD MI300X</p>
          </div>
        </div>
        <div className="topbar-center">
          <AgentPill state={orch} />
          <PipelineTicker agentState={orch} />
        </div>
        <div className="topbar-right">
          {critZ > 0 && <div className="alert-chip"><AlertTriangle size={11}/> {critZ} Critical Zone{critZ>1?"s":""}</div>}
          <div className={`status-chip ${vllm?"":"warn"}`}>
            <div className="dot"/> {vllm ? "Qwen-VL · MI300X Online" : "Deterministic Mode"}
          </div>
        </div>
      </header>

      {/* ── 3-COLUMN WORKSPACE ── */}
      <main className="workspace">

        {/* LEFT: KPIs + Zone Map + Jobs + Evidence */}
        <div className="col col-left">
          <KpiBlock scenario={scenario} />
          <ZoneMap scenario={scenario} />
          <JobList jobs={orch.jobs} />
          <EvidenceRail evidence={scenario.evidence} />
        </div>

        {/* CENTER: Video Feed + Voice Comms + GPU */}
        <div className="col col-center">
          <HeroFeeds />
          <VoiceChannel
            onIngest={() => orch.refresh()}
            onVoiceEvidence={orch.addVoiceEvidence}
          />
          <GpuTelemetry scenario={scenario} />
        </div>

        {/* RIGHT: Incident Summary + Uncertainty + Actions */}
        <div className="col">
          <IncidentBrief scenario={scenario} />
          <UncertaintyLedger scenario={scenario} />
          <ResponseActions scenario={scenario} onBroadcast={(titles) => { setBroadcastTitles(titles); setShowBroadcast(true); }} />
        </div>

      </main>

      {showBroadcast && <BroadcastToast scenario={scenario} approvedTitles={broadcastTitles} onClose={() => setShowBroadcast(false)} />}
    </div>
  );
}
