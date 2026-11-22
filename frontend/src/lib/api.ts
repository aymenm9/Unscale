// Tiny fetch wrapper. Every call goes to /api (proxied to FastAPI by next.config.ts).

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init?.method ?? (init?.body ? "POST" : "GET"),
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    body: init?.body ? JSON.stringify(init.body) : undefined,
    credentials: "include",
  });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) {
    window.location.href = "/login";
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data);
  return data as T;
}

export const post = <T,>(path: string, body: unknown = {}) => api<T>(path, { method: "POST", body });

/** Failed checks from a 422 response, or the error text. */
export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail as { checks?: Check[] } | string | null;
    if (d && typeof d === "object" && d.checks) {
      return d.checks.filter((c) => !c.passed).map((c) => c.detail).join(" ");
    }
    if (typeof d === "string") return d;
  }
  return e instanceof Error ? e.message : "Something went wrong.";
}

// ---- shapes returned by the backend (see backend/app/api/) ----

export type Evidence = { id: number; claim: string; quote: string; url: string; source_type: string; fetched_at: string };
export type Reason = { text: string; points: number; evidence_ids: number[] };
export type Qualification = {
  score: number;
  verdict: "good" | "maybe" | "poor";
  reasons: Reason[];
  confidence: number;
  summary: string;
};
export type Check = { name: string; passed: boolean; detail: string };

export type CompanyRow = {
  id: number;
  name: string;
  domain: string;
  status: string;
  platform: string;
  revenue_band: string;
  revenue_confidence: string;
  employee_band: string;
  employee_confidence: string;
  location: string;
  channels: string[];
  campaign_id: number | null;
  score: number | null;
  verdict: "good" | "maybe" | "poor" | null;
  why: string;
  evidence_count: number;
};

export type Strategy = {
  voice: string;
  trigger_evidence_id: number;
  pain: string;
  follow_up_angles: { step: number; angle: string; evidence_id: number | null }[];
  avoid: string[];
};

export type Draft = {
  id: number;
  status: string;
  subject: string;
  body: string;
  checks: Check[];
  strategy: Strategy;
  handoff_reason: string;
  created_at: string;
  citations: Evidence[];
  company: CompanyRow;
  qualification: Qualification | null;
  contact: { name: string; title: string; email: string };
};

export type ThreadRow = {
  id: number;
  subject: string;
  mode: "agent" | "human";
  status: "open" | "needs_human" | "booked" | "closed" | "suppressed";
  handoff_reason: string;
  human_touched: boolean;
  step: number;
  updated_at: string;
  next_followup_at: string | null;
  followups_sent: number;
  company: { id: number; name: string };
  contact: { name: string; title: string; email?: string };
  last_message: { direction: string; body: string } | null;
};

export type AgentNotes = {
  action: string;
  reason: string;
  step?: number;
  analysis: { intent: string; confidence: number; summary: string } | null;
  offered_slots?: string[];
};

export type Report = {
  interest?: string;
  pain?: string | null;
  objections?: string[];
  next_step?: string;
  new_since_last?: string[];
  call_prep?: string[] | null;
};

export type ThreadDetail = ThreadRow & {
  contact: { name: string; title: string; email: string };
  report: Report;
  strategy: Strategy;
  evidence: Evidence[];
  qualification: Qualification | null;
  messages: {
    id: number;
    direction: "inbound" | "outbound";
    author: string;
    body: string;
    subject: string;
    kind: string;
    sent_to: string;
    agent_notes: AgentNotes | null;
    created_at: string;
  }[];
  meeting: { start_at: string; label: string } | null;
};

export type CampaignSettings = {
  categories: string[];
  channels: string[];
  revenue_min: number;
  revenue_max: number;
  staff_min: number;
  staff_max: number;
  location: string;
  signals: string[];
  roles: string[];
  voice: string;
  target: number;
};

export type CampaignStats = {
  found: number;
  researched: number;
  good: number;
  maybe: number;
  poor: number;
  drafts: number;
  emailed: number;
  replies: number;
  calls: number;
};

export type Campaign = {
  id: number;
  name: string;
  settings: CampaignSettings;
  status: "running" | "done" | "stopped" | "failed" | "draft";
  stage: string;
  progress_done: number;
  progress_total: number;
  message: string;
  created_at: string;
  finished_at: string | null;
  stats: CampaignStats;
};

export type CampaignDetail = Campaign & {
  companies: (CompanyRow & { step: number; draft_id: number | null; thread_id: number | null; needs_you: boolean })[];
  rejections: { id: number; name: string; domain: string; stage: string; reason: string; company_id: number | null }[];
};

export type Home = {
  user: string;
  stats: { found: number; good: number; emailed: number; replies: number; calls: number; sent_emails: number };
  running: Campaign | null;
  waiting: { kind: "reply" | "draft"; id: number; company: string; why: string; when: string }[];
  pipeline: ThreadRow[];
  next_meeting: { label: string; company: string; thread_id: number } | null;
};

export type OutboxItem = {
  id: number;
  thread_id: number;
  direction: "inbound" | "outbound";
  kind: string;
  author: string;
  subject: string;
  sent_to: string;
  created_at: string;
  company: string;
  contact: { name: string; email: string };
  text: string;
  html: string;
  thread_status: string;
};
