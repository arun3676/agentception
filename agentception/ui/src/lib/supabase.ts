/**
 * Supabase Client Configuration
 * 
 * This file provides the Supabase client for connecting to Edge Functions
 * and database operations for the Resume Tailoring feature.
 */

import { createClient } from '@supabase/supabase-js'

// Environment variables with fallback for development
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ""
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ""
const supabaseDefaultUserId = import.meta.env.VITE_SUPABASE_DEFAULT_USER_ID || ''
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"

// Check if Supabase is configured
const isSupabaseConfigured = supabaseUrl && supabaseAnonKey

// Log warning if not fully configured
if (!isSupabaseConfigured) {
  console.warn(
    'Supabase environment variables not fully set. Resume tailoring features will not work until VITE_SUPABASE_ANON_KEY is set in .env.local'
  )
}

if (isSupabaseConfigured && !supabaseDefaultUserId) {
  console.warn(
    'VITE_SUPABASE_DEFAULT_USER_ID is not set. Pass a valid Supabase auth user id to parseResume/parseJobDescription/tailorResume/generateDocx or uploads will fail.'
  )
}

// Create Supabase client (will be null-safe in API calls)
export const supabase = supabaseAnonKey 
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

/**
 * Types for Resume Tailoring Feature
 */

// Parsed Resume Data
export interface ParsedResumeData {
  contact: {
    name: string
    email: string | null
    phone: string | null
    linkedin?: string | null
    github?: string | null
    website?: string | null
    address?: string | null
    city?: string | null
    state?: string | null
    country?: string | null
  }
  summary?: string
  experience: Array<{
    company: string
    position: string
    duration: {
      start: string
      end: string | 'present'
    }
    location?: string
    description?: string
    achievements?: string[]
    technologies?: string[]
    remote?: boolean
  }>
  education: Array<{
    institution: string
    degree: string
    field: string | null
    duration: {
      start: string
      end: string | 'present'
    }
    gpa?: number | string
    honors?: string[]
    location?: string
  }>
  skills: {
    technical?: string[]
    soft?: string[]
    languages?: string[]
    industry?: string[]
    tools?: string[]
    frameworks?: string[]
  }
  certifications?: Array<{
    name: string
    issuer: string
    dateObtained: string
    expirationDate?: string | null
    credentialId?: string
  }>
  projects?: Array<{
    name: string
    description?: string
    technologies?: string[]
    url?: string
  }>
  parsingConfidence?: number
}

// Parsed Job Description Data
export interface ParsedJobData {
  requirements: {
    skills: {
      required?: string[]
      preferred?: string[]
      categories?: {
        programming_languages?: string[]
        frameworks?: string[]
        libraries?: string[]
        tools?: string[]
        databases?: string[]
        cloud_platforms?: string[]
        methodologies?: string[]
        soft_skills?: string[]
      }
      yearsOfExperience?: number
    }
    experience: {
      minYears?: number
      maxYears?: number
      level?: string
      specific?: Record<string, unknown>
      industry?: string[]
    }
    education: {
      degreeLevel?: string
      fields?: string[]
      required?: boolean
      notes?: string
    }
    certifications?: string[]
    other?: string[]
    mustHave?: string[]
    niceToHave?: string[]
  }
  responsibilities?: string[]
  benefits?: string[]
  salary?: {
    min?: number
    max?: number
    currency?: string
    period?: string
    text?: string
  }
  keywords?: {
    primary?: string[]
    secondary?: string[]
    skills?: string[]
    technologies?: string[]
    industry?: string[]
    weighted?: Record<string, number>
    count?: number
  }
  company?: {
    name?: string
    size?: string
    industry?: string
    website?: string
    location?: {
      city?: string
      state?: string
      country?: string
      remote?: boolean
    }
  }
  jobType?: string
  remote?: boolean | string
  metadata?: {
    confidence?: number
    parserVersion?: string
    parsedSections?: string[]
    failedSections?: string[]
  }
}

// Keyword with Priority
export interface Keyword {
  text: string
  priority: number
  category: 'technical' | 'soft' | 'tool' | 'methodology' | 'industry' | 'other'
  frequency: number
  context?: 'required' | 'preferred' | 'nice-to-have'
}

// Tailored Resume Data
export interface TailoredResumeData extends ParsedResumeData {
  target_job_title?: string
  targetJobTitle?: string
}

export interface TemplateOption {
  id: string
  name: string
  description: string
  features?: string[]
}

// API Response Types
export interface ParseResumeResponse {
  resumeId: string
  filePath: string
  fileName: string
  structuredData: ParsedResumeData
  rawText: string
  atsText: string
  confidence: number
}

export interface ParseJobDescriptionResponse {
  jobDescriptionId: string
  parsedData: ParsedJobData
  keywords: Keyword[]
  experienceRequirement: {
    type: 'range' | 'minimum' | 'exact' | 'level' | 'none'
    min?: number
    max?: number
    years?: number
    level?: string
  }
  confidence: number
}

export interface TailorResumeResponse {
  tailoredResumeId: string
  tailoredData: TailoredResumeData
  matchScore: number
  scoreBreakdown: {
    keywordMatch: number
    skillMatch: number
    experienceMatch: number
    educationMatch: number
  }
  changes: {
    addedKeywords: string[]
    modifiedSections: string[]
    reorderedSections: string[]
    optimizedBullets: number
  }
  confidence: number
}

/**
 * Edge Function API Calls
 */

// Use backend proxy in dev (avoids CORS issues with Supabase Edge Functions)
// In production, calls go directly to Supabase
const isDev = typeof window !== 'undefined' && window.location.hostname === 'localhost'
const EDGE_FUNCTION_BASE = supabaseUrl 
  ? (isDev ? '/api/proxy/supabase' : `${supabaseUrl}/functions/v1`) 
  : ''

/**
 * Check if Supabase is configured
 */
export function isSupabaseReady(): boolean {
  return Boolean(isSupabaseConfigured && supabaseDefaultUserId)
}

// Resolve which Supabase user id should be used for persistence
function resolveUserId(explicitUserId?: string): string {
  const resolvedUserId = explicitUserId || supabaseDefaultUserId

  if (!resolvedUserId) {
    throw new Error(
      'Missing Supabase user ID. Pass userId explicitly or set VITE_SUPABASE_DEFAULT_USER_ID to a valid auth.users id.'
    )
  }

  return resolvedUserId
}

/**
 * Parse a resume file (PDF or DOCX)
 * Calls the parse-resume Edge Function
 */
export async function parseResume(
  file: File,
  userId?: string
): Promise<ParseResumeResponse> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env.local file.')
  }

  // Use provided userId or fall back to configured default
  const effectiveUserId = resolveUserId(userId)

  const formData = new FormData()
  formData.append('file', file)
  formData.append('userId', effectiveUserId)
  formData.append('fileName', file.name)

  const response = await fetch(`${EDGE_FUNCTION_BASE}/parse-resume`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error?.message || `Failed to parse resume: ${response.statusText}`)
  }

  const result = await response.json()
  
  // Debug: Log parsed resume structure
  if (result.data?.structuredData) {
    const expCount = result.data.structuredData.experience?.length || 0
    const skillsCount = result.data.structuredData.skills?.technical?.length || 0
    console.log('📄 Parsed Resume Data:', {
      experienceCount: expCount,
      skillsCount: skillsCount,
      hasContact: !!result.data.structuredData.contact,
      contactName: result.data.structuredData.contact?.name,
      rawTextLength: result.data.rawText?.length || 0,
      experience: result.data.structuredData.experience,
      skills: result.data.structuredData.skills,
      fullStructuredData: result.data.structuredData,
    })
    
    // Warn if empty
    if (expCount === 0) {
      console.warn('⚠️ No experience entries found in parsed resume')
    }
    if (skillsCount === 0) {
      console.warn('⚠️ No technical skills found in parsed resume')
    }
  }
  
  return result.data
}

/**
 * Parse a job description text
 * Calls the parse-job-description Edge Function
 */
export async function parseJobDescription(
  text: string,
  userId?: string,
  options?: {
    jobTitle?: string
    companyName?: string
    jobUrl?: string
  }
): Promise<ParseJobDescriptionResponse> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env.local file.')
  }

  // Use provided userId or fall back to configured default
  const effectiveUserId = resolveUserId(userId)

  const response = await fetch(`${EDGE_FUNCTION_BASE}/parse-job-description`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({
      userId: effectiveUserId,
      text,
      ...options,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error?.message || `Failed to parse job description: ${response.statusText}`)
  }

  const result = await response.json()
  return result.data
}

/**
 * Tailor a resume to match a job description
 * Calls the tailor-resume Edge Function
 */
export async function tailorResume(
  resumeId: string,
  jobDescriptionId: string,
  userId?: string
): Promise<TailorResumeResponse> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env.local file.')
  }

  // Use provided userId or fall back to configured default
  const effectiveUserId = resolveUserId(userId)

  const response = await fetch(`${EDGE_FUNCTION_BASE}/tailor-resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({
      userId: effectiveUserId,
      resumeId,
      jobDescriptionId,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error?.message || `Failed to tailor resume: ${response.statusText}`)
  }

  const result = await response.json()
  return result.data
}

/**
 * Generate a downloadable DOCX file from the tailored resume
 * Calls the generate-docx Edge Function
 */
export async function generateDocx(
  tailoredResumeId: string,
  userId?: string
): Promise<Blob> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env.local file.')
  }

  // Use provided userId or fall back to configured default
  const effectiveUserId = resolveUserId(userId)

  const response = await fetch(`${EDGE_FUNCTION_BASE}/generate-docx`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({
      userId: effectiveUserId,
      tailoredResumeId,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error?.message || `Failed to generate DOCX: ${response.statusText}`)
  }

  return response.blob()
}

/**
 * Get available resume templates (served by backend)
 */
export async function getTemplates(): Promise<TemplateOption[]> {
  const response = await fetch(`${BACKEND_URL}/api/templates`)
  if (!response.ok) {
    const errText = await response.text().catch(() => "")
    throw new Error(`Failed to load templates: ${response.status} ${errText}`)
  }
  const data = await response.json().catch(() => ({}))
  return data.templates || []
}

/**
 * Generate a PDF using a selected template
 */
export async function generatePdf(
  tailoredResumeId: string,
  templateId: string,
  tailoredData: TailoredResumeData,
  userId?: string
): Promise<Blob> {
  const response = await fetch(`${BACKEND_URL}/api/generate-pdf`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      tailored_resume_id: tailoredResumeId,
      template_id: templateId,
      user_id: userId,
      tailored_data: tailoredData,
    }),
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => "")
    throw new Error(`Failed to generate PDF: ${response.status} ${errText}`)
  }

  return response.blob()
}

/**
 * Calculate ATS match score between resume and job description
 * Calls the calculate-ats-score Edge Function
 */
export async function calculateATSScore(
  resumeId: string,
  jobDescriptionId: string,
  userId?: string
): Promise<{
  score: number
  breakdown: {
    keywordMatch: number
    skillMatch: number
    experienceMatch: number
    educationMatch: number
  }
  missingKeywords: string[]
  matchedKeywords: string[]
}> {
  if (!isSupabaseConfigured) {
    throw new Error('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in your .env.local file.')
  }

  // Use provided userId or fall back to configured default
  const effectiveUserId = resolveUserId(userId)

  const response = await fetch(`${EDGE_FUNCTION_BASE}/calculate-ats-score`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${supabaseAnonKey}`,
    },
    body: JSON.stringify({
      userId: effectiveUserId,
      resumeId,
      jobDescriptionId,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error?.message || `Failed to calculate ATS score: ${response.statusText}`)
  }

  const result = await response.json()
  return result.data
}

