/** Public FastAPI contracts used by the containment UI. */

const configuredBackendUrl = String(import.meta.env.VITE_BACKEND_URL || "").trim().replace(/\/+$/, "");
const BACKEND_URL = configuredBackendUrl || (import.meta.env.DEV ? "http://localhost:8000" : "");

export type AsyncStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface FieldError {
  field: string;
  message: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    request_id: string;
    field_errors?: FieldError[];
  };
}

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly retryable: boolean,
    public readonly requestId?: string,
    public readonly fieldErrors?: FieldError[],
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

function apiUrl(path: string): string {
  if (!BACKEND_URL) {
    throw new Error("The API endpoint is not configured for this deployment.");
  }
  return `${BACKEND_URL}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    let envelope: ApiErrorEnvelope | null = null;
    try {
      envelope = await response.json() as ApiErrorEnvelope;
    } catch {
      // A non-JSON proxy failure still becomes a safe local error.
    }
    const error = envelope?.error;
    throw new ApiRequestError(
      error?.message || "The service could not complete the request.",
      response.status,
      error?.code || `http_${response.status}`,
      error?.retryable ?? response.status >= 500,
      error?.request_id || response.headers.get("x-request-id") || undefined,
      error?.field_errors,
    );
  }
  return response.json() as Promise<T>;
}

export interface RagRequest {
  city: string;
  role: string;
  depth?: string;
}

export interface TimelineEvent {
  run_id: string;
  agent: string;
  message: string;
  type?: string;
  stage?: string;
  level?: string;
  event_id?: string;
}

export interface CompanyResult {
  name?: string | null;
  homepage?: string | null;
  city?: string | null;
  company_name?: string | null;
  job_title?: string | null;
  job_url?: string | null;
  job_location?: string | null;
  job_source?: string | null;
  observed_at?: string | null;
  description_origin?: string | null;
  remote_policy?: string | null;
  listing_data_quality?: string | null;
  clean_company?: string | null;
  clean_title?: string | null;
  clean_snippet?: string | null;
  display_data?: {
    title?: string | null;
    company?: string | null;
    summary?: string | null;
    location?: string | null;
    source_tag?: string | null;
  } | null;
  job_posting?: {
    url?: string | null;
    title?: string | null;
    snippet?: string | null;
    location?: string | null;
    company?: string | null;
    salary?: string | null;
    source?: string | null;
    observed_at?: string | null;
    description_origin?: string | null;
    remote_policy?: string | null;
    listing_data_quality?: string | null;
  } | null;
  blurb?: string | null;
  salary?: string | null;
  tags?: string[];
}

export interface RAGResults {
  run_id?: string;
  city: string;
  role: string;
  companies: CompanyResult[];
  pagination: {
    offset: number;
    limit: number;
    total: number;
    has_more: boolean;
  };
}

export interface AIResource {
  id: string;
  title: string;
  description?: string;
  url: string;
  category?: string;
  tags?: string[];
  difficulty?: string;
  cost?: string;
  featured?: boolean;
}

export interface Pillar {
  key: string;
  label: string;
  keywords: string[];
}

export function searchCompanies(request: RagRequest): Promise<{ run_id: string; status?: AsyncStatus }> {
  return requestJson<{ run_id: string; status?: AsyncStatus }>("/rag/companies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function fetchResources(params: {
  q?: string;
  category?: string;
  difficulty?: string;
  cost?: string;
  tag?: string;
  featured?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ items: AIResource[]; count: number }> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return requestJson<{ items: AIResource[]; count: number }>(`/api/v1/resources?${query.toString()}`);
}

export function listPillars(): Promise<{ pillars: Pillar[] }> {
  return requestJson<{ pillars: Pillar[] }>("/api/v1/study/pillars");
}

export function getResults(runId: string, offset = 0, limit = 5): Promise<RAGResults> {
  return requestJson<RAGResults>(
    `/results/${encodeURIComponent(runId)}?offset=${encodeURIComponent(offset)}&limit=${encodeURIComponent(limit)}`,
  );
}

export function createTimelineStream(
  runId: string,
  onMessage: (event: TimelineEvent) => void,
  onEnd: () => void,
  onError: () => void,
  timeoutMs = 90_000,
): EventSource {
  const eventSource = new EventSource(apiUrl(`/timeline/${encodeURIComponent(runId)}`));
  const nativeClose = eventSource.close.bind(eventSource);
  let terminal = false;
  const timeoutId = globalThis.setTimeout(() => {
    if (terminal) return;
    terminal = true;
    nativeClose();
    onError();
  }, timeoutMs);
  const close = () => {
    globalThis.clearTimeout(timeoutId);
    nativeClose();
  };
  eventSource.close = close;

  eventSource.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as TimelineEvent);
    } catch {
      // Ignore a malformed update while keeping the stream open for a valid terminal event.
    }
  };
  eventSource.addEventListener("end", (event) => {
    if (terminal) return;
    terminal = true;
    close();
    try {
      const status = JSON.parse((event as MessageEvent).data) as { status?: string };
      if (status.status === "succeeded") onEnd();
      else onError();
    } catch {
      onError();
    }
  });
  eventSource.onerror = () => {
    if (terminal) return;
    terminal = true;
    close();
    onError();
  };

  return eventSource;
}
