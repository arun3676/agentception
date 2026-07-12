import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createProjectBrief,
  createSkillReceipt,
  createTrustProfile,
  getApplicationRecommendations,
  matchCohort,
  reverseEngineerCareer,
} from "./api";

const jsonResponse = (body: unknown) =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  } as Response);

describe("Agentception 2.0 API contracts", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the career reverse-engineer endpoint with the expected payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      await jsonResponse({ roadmap: [], skill_graph: { hard_skills: [] } }),
    );

    await reverseEngineerCareer({ target_role: "AI Engineer", current_skills: ["Python"] });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v2/career/reverse-engineer",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ target_role: "AI Engineer", current_skills: ["Python"] }),
      }),
    );
  });

  it("keeps portfolio, profile, application, and cohort endpoints wired", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(await jsonResponse({ id: "brief_1", title: "Brief" }))
      .mockResolvedValueOnce(await jsonResponse({ id: "receipt_1", verification_score: 90 }))
      .mockResolvedValueOnce(await jsonResponse({ username: "arun", trust_score: 80 }))
      .mockResolvedValueOnce(await jsonResponse({ recommendations: ["Attach proof"] }))
      .mockResolvedValueOnce(await jsonResponse({ cohort_id: "cohort_1", members: [] }));

    await createProjectBrief({ target_role: "AI Engineer" });
    await createSkillReceipt({ project_title: "RAG proof" });
    await createTrustProfile({ username: "arun", name: "Arun", target_role: "AI Engineer" });
    await getApplicationRecommendations([]);
    await matchCohort({ target_profile: { username: "arun", target_role: "AI Engineer" } });

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/api/v2/portfolio/project-brief",
      "http://localhost:8000/api/v2/portfolio/skill-receipt",
      "http://localhost:8000/api/v2/profile/trust",
      "http://localhost:8000/api/v2/applications/recommendations",
      "http://localhost:8000/api/v2/cohort/match",
    ]);
  });
});
