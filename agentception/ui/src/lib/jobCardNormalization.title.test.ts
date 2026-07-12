/**
 * Titles on an ATS.
 *
 * Live production shipped every card titled "roles at Greenhouse":
 *   - the employer was read from the DOMAIN (job-boards.greenhouse.io -> the ATS
 *     vendor) instead of the PATH (/anthropic/ -> the actual employer), and
 *   - a real title, "Job Application for Staff Engineer at Anthropic", was
 *     classified as noise *before* the code that strips "Job Application for"
 *     ever ran, so it was discarded in favour of that bad guess.
 *
 * These strings are copied from real /results payloads.
 */

import { describe, expect, it } from "vitest";

import { normalizeJobCard } from "./jobCardNormalization";

const anthropic = {
  company_name: "Anthropic",
  job_url: "https://job-boards.greenhouse.io/anthropic/jobs/8611081002",
  job_title:
    "Job Application for Staff+ Software Engineer, Full-stack at Anthropic. San Francisco, CA | New York City, NY | Seattle, WA.",
  blurb: "Job Application for Staff+ Software Engineer, Full-stack at Anthropic.",
  job_location: "San Francisco",
};

describe("ATS job titles", () => {
  it("recovers the real role instead of naming the ATS vendor", () => {
    const card = normalizeJobCard(anthropic, "");
    expect(card).not.toBeNull();
    // The bug: "roles at Greenhouse"
    expect(card!.title.toLowerCase()).not.toContain("greenhouse");
    expect(card!.title.toLowerCase()).not.toMatch(/^roles at/);
    expect(card!.title.toLowerCase()).toContain("software engineer");
  });

  it("drops the location tail and the trailing 'at <Company>'", () => {
    const card = normalizeJobCard(anthropic, "");
    expect(card!.title).not.toMatch(/San Francisco|Seattle|\|/);
    expect(card!.title.toLowerCase()).not.toMatch(/at anthropic$/);
  });

  it("falls back to the employer from the URL path, never the ATS host", () => {
    const card = normalizeJobCard(
      {
        // No usable title at all — forces the fallback path.
        company_name: "",
        job_url: "https://jobs.lever.co/hophr/9e92ee57-64d5-493d-8f7d-42ac429ca826",
        job_title: "Application",
        blurb: "",
      },
      "",
    );
    expect(card).not.toBeNull();
    expect(card!.title.toLowerCase()).not.toContain("lever");
    expect(card!.title.toLowerCase()).toContain("hophr");
  });

  it("does not emit a bare 'roles at ...' when no role was requested", () => {
    const card = normalizeJobCard(
      { company_name: "Pilothq", job_url: "https://job-boards.greenhouse.io/pilothq/jobs/1", job_title: "Application", blurb: "" },
      "", // user searched without specifying a role
    );
    expect(card!.title).not.toMatch(/^\s*roles\s+at/i);
  });
});
