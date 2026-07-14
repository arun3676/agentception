/**
 * Minimal presentation mapping for public job search results.
 *
 * This module deliberately does not infer facts from a search query, URL path,
 * keyword overlap, or neighbouring fields. A missing title, employer,
 * location, or description is shown as unavailable instead of being guessed.
 */

export type JobCard = {
  displayTitle: string;
  displayCompany: string;
  displayLocation: string;
  snippet: string;
  sourceDomain: string;
  sourceLabel: string;
  applyUrl: string;
  salary?: string;
  observedAt?: string;
  descriptionOrigin: string;
  remotePolicy: string;
  listingDataQuality: string;
};

export type RawCompanyData = {
  company_name?: string | null;
  job_title?: string | null;
  job_url?: string | null;
  job_location?: string | null;
  job_source?: string | null;
  observed_at?: string | null;
  description_origin?: string | null;
  remote_policy?: string | null;
  listing_data_quality?: string | null;
  blurb?: string | null;
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
  name?: string | null;
  salary?: string | null;
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
};

function firstText(...values: Array<string | null | undefined>): string | undefined {
  for (const value of values) {
    const text = value?.replace(/\s+/g, " ").trim();
    if (text) return text;
  }
  return undefined;
}

function sourceDomain(url: string): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return undefined;
    return parsed.hostname || undefined;
  } catch {
    return undefined;
  }
}

/**
 * Map one backend result to one card without filtering or reordering it.
 * `requestedRole` is intentionally not accepted: search input is not listing
 * evidence and must never be used to fill a missing title or description.
 */
export function normalizeJobCard(company: RawCompanyData): JobCard {
  const posting = company.job_posting;
  const display = company.display_data;
  const applyUrl = firstText(company.job_url, posting?.url) ?? "";

  return {
    displayTitle: firstText(display?.title, company.clean_title, company.job_title, posting?.title)
      ?? "Title unavailable",
    displayCompany: firstText(
      display?.company,
      company.clean_company,
      company.company_name,
      posting?.company,
      company.name,
    ) ?? "Company unavailable",
    // A search city is not proof of a listing's location, so there is no city
    // fallback here. Only fields attached to the returned listing are used.
    displayLocation: firstText(display?.location, company.job_location, posting?.location)
      ?? "Location unavailable",
    snippet: firstText(display?.summary, company.clean_snippet, company.blurb, posting?.snippet)
      ?? "Description unavailable",
    sourceDomain: sourceDomain(applyUrl) ?? firstText(display?.source_tag) ?? "Source unavailable",
    sourceLabel: firstText(company.job_source, posting?.source, display?.source_tag)
      ?? "Source unavailable",
    applyUrl,
    salary: firstText(company.salary, posting?.salary),
    observedAt: firstText(company.observed_at, posting?.observed_at),
    descriptionOrigin: firstText(company.description_origin, posting?.description_origin)
      ?? "unavailable",
    remotePolicy: firstText(company.remote_policy, posting?.remote_policy) ?? "unknown",
    listingDataQuality: firstText(
      company.listing_data_quality,
      posting?.listing_data_quality,
    ) ?? "unknown",
  };
}
