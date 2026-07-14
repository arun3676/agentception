import { describe, expect, it } from "vitest";

import { presentTimelineEvent } from "./Timeline";

const event = (message: string, extra: Record<string, string> = {}) => ({
  run_id: "synthetic-run",
  agent: "Search",
  message,
  ...extra,
});

describe("timeline event presentation", () => {
  it("uses an explicit persisted stage when one is available", () => {
    expect(presentTimelineEvent(event("provider response omitted", { stage: "enrichment" }))).toEqual({
      message: "Reviewing returned listing details.",
      icon: "review",
    });
  });

  it("does not turn internal counts into match, rank, or opportunity claims", () => {
    const presentation = presentTimelineEvent(
      event("Ranked 37 companies; built 12 hiring opportunities; caching under secret-key"),
    );

    expect(presentation.message).toBe("Preparing returned listings.");
    expect(presentation.message).not.toMatch(/37|12|rank|hiring|opportunit|secret/i);
  });

  it("does not echo arbitrary provider text, URLs, or identifiers", () => {
    const presentation = presentTimelineEvent(
      event("Provider body https://example.test/?token=private run_id=abc123"),
    );

    expect(presentation.message).toBe("Search update received.");
    expect(presentation.message).not.toMatch(/example|token|abc123/i);
  });

  it("maps error-level events to a safe failure state", () => {
    expect(presentTimelineEvent(event("raw exception details", { level: "error" }))).toEqual({
      message: "Search processing failed.",
      icon: "error",
    });
  });
});
