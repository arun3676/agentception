import { describe, expect, it } from "vitest";

import { normalizeJobCard, type RawCompanyData } from "./jobCardNormalization";

describe("truthful job-card normalization", () => {
  it("uses only facts returned for the listing", () => {
    const card = normalizeJobCard({
      company_name: "Example Systems",
      job_title: "Backend Engineer",
      job_url: "https://jobs.example.com/roles/123",
      job_location: "Remote — United States",
      blurb: "Build and operate the public API.",
      salary: "$150,000–$180,000",
    });

    expect(card).toEqual({
      displayTitle: "Backend Engineer",
      displayCompany: "Example Systems",
      displayLocation: "Remote — United States",
      snippet: "Build and operate the public API.",
      sourceDomain: "jobs.example.com",
      sourceLabel: "Source unavailable",
      applyUrl: "https://jobs.example.com/roles/123",
      salary: "$150,000–$180,000",
      observedAt: undefined,
      descriptionOrigin: "unavailable",
      remotePolicy: "unknown",
      listingDataQuality: "unknown",
    });
  });

  it("labels absent facts instead of inferring them from the URL or search", () => {
    const card = normalizeJobCard({
      job_url: "https://jobs.lever.co/example-company/role-id",
    });

    expect(card.displayTitle).toBe("Title unavailable");
    expect(card.displayCompany).toBe("Company unavailable");
    expect(card.displayLocation).toBe("Location unavailable");
    expect(card.snippet).toBe("Description unavailable");
  });

  it("does not treat the search city as the listing location", () => {
    const input = {
      city: "San Francisco, CA",
      job_title: "Platform Engineer",
      job_url: "https://example.com/job",
    } as RawCompanyData & { city: string };

    expect(normalizeJobCard(input).displayLocation).toBe("Location unavailable");
  });

  it("does not expose legacy match, trust, résumé, or hiring fields", () => {
    const input = {
      job_title: "Platform Engineer",
      job_url: "https://example.com/job",
      trust_score: 99,
      resume_match_score: 95,
      hiring_badge: "Hiring",
    } as RawCompanyData & Record<string, unknown>;

    const card = normalizeJobCard(input);
    expect(card).not.toHaveProperty("trustScore");
    expect(card).not.toHaveProperty("resumeMatchScore");
    expect(card).not.toHaveProperty("matchInfo");
    expect(card).not.toHaveProperty("matchScore");
    expect(card).not.toHaveProperty("hiringBadge");
  });

  it("preserves backend order when cards are mapped", () => {
    const input: RawCompanyData[] = [
      { company_name: "First", job_url: "https://first.example/job" },
      { company_name: "Second", job_url: "https://second.example/job" },
    ];

    expect(input.map(normalizeJobCard).map((card) => card.displayCompany)).toEqual(["First", "Second"]);
  });
});
