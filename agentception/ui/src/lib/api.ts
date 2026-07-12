/**
 * API utilities for connecting to the FastAPI backend
 */

import { supabase } from "@/lib/supabase";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

async function authenticatedHeaders(): Promise<HeadersInit> {
  const result = supabase ? await supabase.auth.getSession() : { data: { session: null } };
  if (!result.data.session?.access_token) throw new Error("Sign in to manage applications.");
  return { "Content-Type": "application/json", Authorization: `Bearer ${result.data.session.access_token}` };
}

export interface RagRequest {
  city: string;
  role?: string;
  resumeToken?: string | null;
  depth?: string;
  offset?: number;
  limit?: number;
  filters?: {
    remote?: boolean | null;
    company_size?: string | null;
    technologies?: string[] | null;
    salary_min?: number | null;
  };
  run_id?: string | null;
}

export interface WriterRequest {
  run_id: string;
  n?: number;
}

export interface TimelineEvent {
  run_id: string;
  agent: "RAG" | "Writer" | "System";
  message: string;
  type?: string;
}

export interface CompanyIntel {
  name: string;
  homepage: string;
  city: string;
  job_posting?: {
    url: string;
    title: string;
    snippet: string;
  } | null;
  resume_match_score?: number;
  score?: number;
  blurb?: string;
  tags?: string[];
}

export interface RAGResults {
  run_id?: string;
  city: string;
  role: string;
  companies: CompanyIntel[];
  pagination: {
    offset: number;
    limit: number;
    total: number;
    has_more: boolean;
  };
  emails?: Email[];
  // New fields for "Load 5 more roles" feature
  searched_roles?: string[];
  total_roles_searched?: number;
  has_more_roles?: boolean;
}

export interface LoadMoreRolesRequest {
  run_id: string;
  count?: number;
}

export interface LoadMoreRolesResponse {
  run_id: string;
  status: string;
  message: string;
  next_roles: string[];
  searched_roles: string[];
  total_roles_searched: number;
  has_more: boolean;
}

export interface Email {
  company: string;
  email: string;
  subject: string;
  body: string;
}

export interface TailorFromJobRequest {
  run_id: string;
  job_url: string;
  resume_token: string;
  job_snippet?: string;
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
  verified?: boolean;
  upvotes?: number;
  featured?: boolean;
}

export interface LearningPathRequest {
  topic: string;
  expertise_level: string;
  learning_style: string;
  time_commitment: string;
  goals: string[];
  user_id?: string;
}

export interface LearningPath {
  id: string;
  title: string;
  description: string;
  topic: string;
  expertise_level: string;
  learning_style: string;
  time_commitment: string;
  goals: string[];
  milestones: Array<{
    title: string;
    description: string;
    estimated_hours: number;
    resources: Array<{
      id?: string;
      title: string;
      url: string;
      description?: string;
      category?: string;
      tags?: string[];
    }>;
    skills_gained: string[];
  }>;
  total_hours: number;
  created_at: string;
}

export interface SkillGapAnalysis {
  resume_skills: string[];
  target_skills: string[];
  missing_skills: string[];
}

export interface ResumeStructured {
  contact: {
    name: string;
    email: string;
    phone: string;
    location: string;
    linkedin: string;
    github: string;
    portfolio: string;
  };
  summary: string;
  experience: Array<{
    company: string;
    title: string;
    dates: string;
    location: string;
    bullets: string[];
  }>;
  education: Array<{
    school: string;
    degree: string;
    dates: string;
    gpa: string;
    details: string[];
  }>;
  skills: {
    technical: string[];
    frameworks: string[];
    tools: string[];
    soft: string[];
  };
  projects: Array<{
    title: string;
    description: string;
    tech_stack: string[];
    links: string[];
  }>;
  certifications: string[];
}

export interface ApplicationRecord {
  id: string;
  user_id?: string;
  company_name: string;
  job_title: string;
  job_url: string;
  application_status: string;
  created_at?: string;
  updated_at?: string;
}

/**
 * Upload resume PDF and get token
 */
export async function uploadResume(file: File): Promise<{
  token: string;
  chars: number;
  filename: string;
  insights?: any;
  text_preview?: string;
  structured?: ResumeStructured;
}> {
  const formData = new FormData();
  formData.append("file", file);
  
  const response = await fetch(`${BACKEND_URL}/upload/resume`, {
    method: "POST",
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error(`Resume upload failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getResumeByToken(token: string): Promise<{
  token: string;
  chars: number;
  text_preview: string;
  insights?: any;
  structured?: ResumeStructured;
}> {
  const response = await fetch(`${BACKEND_URL}/upload/resume/${token}`);
  
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Resume not found. Please upload again.");
    }
    throw new Error(`Failed to fetch resume: ${response.statusText}`);
  }
  
  return response.json();
}

export async function bridgeResumeToSupabase(token: string): Promise<{
  resumeId: string;
  structuredData: any;
  rawText?: string;
  atsText?: string;
}> {
  const response = await fetch(`${BACKEND_URL}/api/supabase/parse-resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Failed to bridge resume to Supabase: ${response.status} ${text}`);
  }
  
  return response.json();
}

/**
 * Start RAG company search
 */
export async function searchCompanies(request: RagRequest): Promise<{ run_id: string }> {
  const response = await fetch(`${BACKEND_URL}/rag/companies`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Search failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function fetchResources(params: {
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
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  const response = await fetch(`${BACKEND_URL}/api/v1/resources?${query.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to load resources: ${response.statusText}`);
  }
  return response.json();
}

export async function fetchResource(resourceId: string): Promise<AIResource> {
  const response = await fetch(`${BACKEND_URL}/api/v1/resources/${resourceId}`);
  if (!response.ok) {
    throw new Error(`Failed to load resource: ${response.statusText}`);
  }
  return response.json();
}

export async function listLearningPaths(userId?: string): Promise<{ paths: Array<{ id: string; title: string; topic: string; expertise_level: string; created_at: string }> }> {
  const url = new URL(`${BACKEND_URL}/api/v1/learning-paths`);
  if (userId) url.searchParams.set("user_id", userId);
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to list learning paths: ${response.statusText}`);
  }
  return response.json();
}

export async function getLearningPath(pathId: string): Promise<LearningPath> {
  const response = await fetch(`${BACKEND_URL}/api/v1/learning-paths/${pathId}`);
  if (!response.ok) {
    throw new Error(`Failed to get learning path: ${response.statusText}`);
  }
  return response.json();
}

export async function createLearningPath(request: LearningPathRequest): Promise<LearningPath> {
  const response = await fetch(`${BACKEND_URL}/api/v1/learning-paths/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Failed to generate learning path: ${response.statusText}`);
  }
  return response.json();
}

export async function analyzeSkillGaps(payload: {
  resume_text: string;
  job_text?: string;
  target_role?: string;
}): Promise<{ analysis: SkillGapAnalysis; recommendations: Record<string, AIResource[]> }> {
  const response = await fetch(`${BACKEND_URL}/api/v1/skill-gaps/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Failed to analyze skill gaps: ${response.statusText}`);
  }
  return response.json();
}

export async function createApplication(payload: {
  user_id?: string;
  company_name: string;
  job_title: string;
  job_url: string;
  application_status?: string;
}): Promise<ApplicationRecord> {
  const response = await fetch(`${BACKEND_URL}/api/v1/applications`, {
    method: "POST",
    headers: await authenticatedHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Failed to create application: ${response.statusText}`);
  }
  return response.json();
}

export async function listApplications(user_id?: string): Promise<{ items: ApplicationRecord[] }> {
  const response = await fetch(`${BACKEND_URL}/api/v1/applications`, { headers: await authenticatedHeaders() });
  if (!response.ok) {
    throw new Error(`Failed to load applications: ${response.statusText}`);
  }
  return response.json();
}

export async function updateApplicationStatus(applicationId: string, application_status: string): Promise<ApplicationRecord> {
  const response = await fetch(`${BACKEND_URL}/api/v1/applications/${applicationId}`, {
    method: "PUT",
    headers: await authenticatedHeaders(),
    body: JSON.stringify({ application_status }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update application: ${response.statusText}`);
  }
  return response.json();
}

export async function refreshApplicationListings(): Promise<{ items: Array<{ id: string; status: "open" | "closed" | "unknown"; checked_at: string; status_code?: number }> }> {
  const response = await fetch(`${BACKEND_URL}/api/v1/applications/refresh-listings`, { method: "POST", headers: await authenticatedHeaders() });
  if (!response.ok) throw new Error(`Failed to refresh job availability: ${response.statusText}`);
  return response.json();
}

export async function fetchRecommendations(topic?: string): Promise<{ resources: AIResource[]; job_boards: Array<{ title: string; url: string }> }> {
  const query = topic ? `?topic=${encodeURIComponent(topic)}` : "";
  const response = await fetch(`${BACKEND_URL}/api/v1/recommendations${query}`);
  if (!response.ok) {
    throw new Error(`Failed to load recommendations: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Get search results with pagination
 */
export async function getResults(runId: string, offset: number = 0, limit: number = 5): Promise<RAGResults> {
  const response = await fetch(`${BACKEND_URL}/results/${runId}?offset=${offset}&limit=${limit}`);
  
  if (!response.ok) {
    if (response.status === 404) {
      // Return empty results if not found
      return {
        city: "",
        role: "",
        companies: [],
        pagination: {
          offset,
          limit,
          total: 0,
          has_more: false,
        },
      };
    }
    throw new Error(`Failed to fetch results: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Generate outreach emails
 */
export async function generateEmails(request: WriterRequest): Promise<{ run_id: string }> {
  const response = await fetch(`${BACKEND_URL}/writer/outreach`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Email generation failed: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Fetch job description text from URL
 * Falls back to snippet if fetch fails (e.g., aggregator URLs, 404s)
 */
export async function fetchJobDescriptionText(jobUrl: string, snippet?: string): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  
  try {
    const response = await fetch(`${BACKEND_URL}/api/fetch-job-description`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ job_url: jobUrl, snippet }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      if (snippet && snippet.length > 50) {
        console.warn(`Job fetch failed (${response.status}), using snippet fallback`);
        return snippet;
      }
      const errorText = await response.text();
      throw new Error(`Failed to fetch job description: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    const fetchedText = data.job_text || data.text || "";
    
    if (fetchedText.length < 100 && snippet && snippet.length > fetchedText.length) {
      return snippet;
    }
    
    return fetchedText || snippet || "";
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error?.name === "AbortError") {
      console.warn("Job description fetch timed out after 60s, using snippet fallback");
      return snippet || "";
    }
    if (snippet && snippet.length > 50) {
      console.warn("Job fetch error, using snippet fallback:", error);
      return snippet;
    }
    throw error;
  }
}

/**
 * Tailor resume directly from a job card (one-click)
 * DEPRECATED: Use Supabase flow instead via TailorJobButton
 */
export async function tailorResumeFromJob(request: TailorFromJobRequest) {
  const response = await fetch(`${BACKEND_URL}/api/tailor-resume-from-job`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to tailor resume: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Load 5 more similar role variations
 * Allows users to expand their search to related roles (e.g., AI Engineer -> ML Engineer)
 * Maximum 20 total roles can be searched
 */
export async function loadMoreRoles(request: LoadMoreRolesRequest): Promise<LoadMoreRolesResponse> {
  const response = await fetch(`${BACKEND_URL}/rag/companies/load-more-roles`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Failed to load more roles: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create EventSource for timeline SSE stream
 */
export function createTimelineStream(runId: string, onMessage: (event: TimelineEvent) => void, onEnd: () => void): EventSource {
  const eventSource = new EventSource(`${BACKEND_URL}/timeline/${runId}`);
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error("Failed to parse timeline event:", error);
    }
  };
  
  eventSource.addEventListener("end", () => {
    eventSource.close();
    onEnd();
  });
  
  eventSource.onerror = (error) => {
    console.error("Timeline stream error:", error);
    eventSource.close();
    onEnd();
  };
  
  return eventSource;
}

// Cohort types and API
export interface CohortMember {
  username: string;
  target_role: string;
  timezone: string;
  skills: string[];
  level: string;
}

export interface CohortMatchResponse {
  cohort_id: string;
  size: number;
  members: CohortMember[];
  mock_interview_plan: {
    live_video_provider: string;
    feedback_sections: string[];
  };
  weekly_accountability_template: string[];
}

export async function matchCohort(payload: {
  target_profile: CohortMember & { weekly_goal: string };
  candidates: CohortMember[];
  cohort_size: number;
}): Promise<CohortMatchResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v2/cohort/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Cohort match failed");
  return res.json();
}

// Trust Profile types and API
export interface TrustProfile {
  username: string;
  name: string;
  target_role: string;
  trust_score: number;
  trust_label: string;
  verified_skills: string[];
  projects: Array<{ title: string; description: string; tags: string[] }>;
  learning_trajectory: { weeks_completed: number };
  application_stats: { callback_rate: number };
  public_url: string;
}

export async function createTrustProfile(payload: {
  username: string;
  name: string;
  target_role: string;
  verified_skills: string[];
  learning_weeks_completed: number;
  skill_receipts: Array<{
    id: string;
    project_title: string;
    skills: string[];
    github_url: string;
    deployment_url: string;
    verification_score: number;
    verification_level: string;
    proof_signals: Record<string, unknown>;
    resume_bullets: string[];
    created_at: string;
  }>;
  applications: Array<{ status: string }>;
  peer_reviews: Array<{ rating: number }>;
}): Promise<TrustProfile> {
  const res = await fetch(`${BACKEND_URL}/api/v2/profile/trust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Trust profile generation failed");
  return res.json();
}

// Portfolio API
export interface ProjectBrief {
  title: string;
  problem_statement: string;
  tech_stack: string[];
  deliverables: string[];
  readme_template: string[];
}

export interface SkillReceipt {
  id: string;
  project_title: string;
  skills: string[];
  verification_score: number;
  verification_level: string;
  github_url?: string;
  deployment_url?: string;
  proof_signals: {
    commit_count: number;
    checks_passed: boolean;
    code_quality_score: number;
  };
  resume_bullets: string[];
  created_at: string;
}

export interface CareerReverseEngineerResponse {
  phase: string;
  target_role: string;
  city: string;
  dream_companies: string[];
  source_summary: {
    job_descriptions_analyzed: number;
    current_skills_count: number;
    generated_without_supabase: boolean;
  };
  skill_graph: {
    hard_skills: string[];
    system_design_patterns: string[];
    soft_skills: string[];
    gaps: string[];
    evidence: Array<{ skill: string; mentions: number }>;
  };
  roadmap: Array<{
    week: number;
    theme: string;
    learning_module: string;
    micro_project: string;
    measurable_output: string;
    skills: string[];
    success_criteria: string[];
  }>;
}

export interface ApiKeyHealthResponse {
  checked_at: string;
  cheap_model_policy: {
    chat_primary: string;
    openai_fallback: string;
    embedding: string;
  };
  checks: Record<
    string,
    {
      ok: boolean;
      configured: boolean;
      status: string;
      status_code?: number;
      error?: string;
    }
  >;
}

export async function createProjectBrief(payload: {
  target_role: string;
  week: number;
  skills: string[];
  project_title: string;
}): Promise<ProjectBrief> {
  const res = await fetch(`${BACKEND_URL}/api/v2/portfolio/project-brief`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create project brief");
  return res.json();
}

export async function createSkillReceipt(payload: {
  project_title: string;
  skills: string[];
  github_url?: string;
  deployment_url?: string;
  commit_count: number;
  checks_passed: boolean;
  code_quality_score: number;
}): Promise<SkillReceipt> {
  const res = await fetch(`${BACKEND_URL}/api/v2/portfolio/skill-receipt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create skill receipt");
  return res.json();
}

export async function reverseEngineerCareer(payload: {
  target_role: string;
  city?: string;
  dream_companies?: string[];
  current_skills?: string[];
  job_descriptions?: string[];
  weeks?: number;
}): Promise<CareerReverseEngineerResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v2/career/reverse-engineer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to reverse-engineer career roadmap");
  return res.json();
}

export async function getApiKeyHealth(): Promise<ApiKeyHealthResponse> {
  const res = await fetch(`${BACKEND_URL}/api/v2/system/api-key-health`);
  if (!res.ok) throw new Error("Failed to check API key health");
  return res.json();
}

export async function getApplicationRecommendations(applications: Array<Record<string, unknown>>) {
  const res = await fetch(`${BACKEND_URL}/api/v2/applications/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ applications }),
  });
  if (!res.ok) throw new Error("Failed to get application recommendations");
  return res.json();
}

/**
 * fetch + status check + JSON decode, in one place.
 * The older functions above each inline this; new code should use it.
 */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, init);
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/* ---------------- Study materials ---------------- */

export interface StudyItem {
  title: string;
  url: string;
  snippet: string;
  published?: string;
  video_id?: string;
  thumbnail?: string;
}

export interface CuratedPick {
  title: string;
  kind: "youtube_channel" | "site" | "course";
  url: string;
}

export interface StudyResults {
  topic: string;
  level: string;
  pillar: { key: string; label: string };
  videos: StudyItem[];
  articles: StudyItem[];
  courses: StudyItem[];
  docs: StudyItem[];
  curated_picks: CuratedPick[];
  cached: boolean;
}

export interface Pillar {
  key: string;
  label: string;
  keywords: string[];
}

export function searchStudyMaterials(payload: {
  topic: string;
  role?: string;
  level?: string;
}): Promise<StudyResults> {
  return postJson<StudyResults>("/api/v1/study/search", payload);
}

export function listPillars(): Promise<{ pillars: Pillar[] }> {
  return apiFetch<{ pillars: Pillar[] }>("/api/v1/study/pillars");
}

export interface InterviewPrep {
  role: string;
  company?: string | null;
  sources: Array<{ title: string; url: string; snippet: string }>;
  cached: boolean;
}

export function getInterviewPrep(role: string, company?: string): Promise<InterviewPrep> {
  const query = new URLSearchParams({ role });
  if (company) query.set("company", company);
  return apiFetch<InterviewPrep>(`/api/v1/study/interview-prep?${query.toString()}`);
}

export interface CompanyBrief {
  company: string;
  overview: string;
  recent_news: Array<{ title: string; url: string; snippet: string }>;
  careers_hint: string;
  cached: boolean;
}

export function getCompanyBrief(name: string): Promise<CompanyBrief> {
  return apiFetch<CompanyBrief>(`/api/v1/company/brief?name=${encodeURIComponent(name)}`);
}

