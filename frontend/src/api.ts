export interface ProviderInfo {
  id: string;
  label: string;
  default_model: string;
  models: string[];
  key_optional: boolean;
  needs_base_url: boolean;
}

export interface AppConfig {
  free_tier_available: boolean;
  default_provider: string;
  free_chain: string[];
  summary_languages: string[];
  providers: ProviderInfo[];
}

export interface Segment {
  text: string;
  start: number;
  duration: number;
}

export interface KeyPoint {
  timestamp: string;
  point: string;
  detail?: string;
}

export interface Summary {
  tldr: string;
  breakdown?: string[];
  key_points: KeyPoint[];
  takeaways?: string[];
  worth_watching?: { score: number; reason?: string };
  topics?: string[];
  truncated?: boolean;
  model?: string;
  provider?: string;
}

export interface SummarizeResult {
  video_id: string;
  duration_seconds: number;
  transcript_source: string;
  transcript_language: string;
  title: string | null;
  author: string | null;
  thumbnail: string;
  summary: Summary;
  segments: Segment[];
}

export interface SummarizeBody {
  url: string;
  provider?: string;
  llm_key?: string | null;
  supadata_key?: string | null;
  model?: string | null;
  base_url?: string | null;
  summary_lang?: string | null;
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error("config failed");
  return res.json();
}

export async function summarize(body: SummarizeBody): Promise<SummarizeResult> {
  const res = await fetch("/api/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Unknown error.");
  return data;
}
