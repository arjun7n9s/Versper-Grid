import sector4Data from "./data/sector4.json";

export type Severity = "watch" | "elevated" | "critical";
export type UncertaintyKind =
  | "missing_data"
  | "model_disagreement"
  | "stale_evidence"
  | "simulation_sensitivity";

export interface EvidenceItem {
  id: string;
  sourceUuid: string;
  source: string;
  kind: "image" | "video" | "report" | "sensor" | "audio";
  summary: string;
  confidence: number;
  signal: string;
  linkedZoneId?: string;
  assetUrl?: string;
  transcript?: string;
  metadata?: Record<string, string | number | boolean | null>;
}

export interface RiskZone {
  id: string;
  label: string;
  x: number;
  y: number;
  radius: number;
  severity: Severity;
  rationale: string;
  metadata?: Record<string, any>;
}

export interface ResponseAction {
  id: string;
  title: string;
  owner: string;
  etaMinutes: number;
  impact: number;
  confidence: number;
  caveat: string;
  sourceEntityId: string;
  status: "candidate" | "approved";
}

export interface UncertaintyIssue {
  id: string;
  kind: UncertaintyKind;
  title: string;
  detail: string;
  severity: Severity;
  sourceEntityIds: string[];
}

export interface GpuLane {
  label: string;
  workload: string;
  utilization: number;
  memoryGb: number;
  latencyMs: number;
}

export interface Scenario {
  incident: string;
  category: string;
  location: string;
  clock: string;
  thesis: string;
  confidence: number;
  evidence: EvidenceItem[];
  zones: RiskZone[];
  actions: ResponseAction[];
  uncertainties: UncertaintyIssue[];
  gpu: GpuLane[];
  brief: string[];
}

/**
 * Deterministic Sector 4 scenario shared with the FastAPI backend
 * (see `apps/api/src/vespergrid/engine.py` which reads the same JSON).
 * Used as the offline fallback when the API is unreachable so the
 * console always has a coherent scene to render.
 */
export const fallbackScenario: Scenario = sector4Data as Scenario;
