/**
 * Ownership comes from the token, never from the browser.
 *
 * Two things are pinned here:
 *
 *  1. A request that needs a session and hasn't got one fails with a *typed*
 *     AuthRequiredError, so callers can distinguish "sign in" from "retry"
 *     without string-matching an error message.
 *
 *  2. No user-owned endpoint sends a client-supplied `user_id`. `GET
 *     /learning-paths?user_id=<someone-else>` used to be a valid, unauthenticated
 *     request that returned that person's data.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: { getSession: () => getSession() } },
}));

import {
  AuthRequiredError,
  createApplication,
  createLearningPath,
  listApplications,
  listLearningPaths,
} from "./api";

const signedOut = () => getSession.mockResolvedValue({ data: { session: null } });
const signedIn = () =>
  getSession.mockResolvedValue({ data: { session: { access_token: "tok_abc123" } } });

const okJson = (body: unknown) =>
  ({ ok: true, json: () => Promise.resolve(body) }) as Response;

beforeEach(() => {
  getSession.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("no session", () => {
  it("createApplication rejects with a typed AuthRequiredError, and never calls the API", async () => {
    signedOut();
    const fetchMock = vi.spyOn(globalThis, "fetch");

    await expect(
      createApplication({
        company_name: "Anthropic",
        job_title: "Staff Engineer",
        job_url: "https://job-boards.greenhouse.io/anthropic/jobs/1",
      }),
    ).rejects.toBeInstanceOf(AuthRequiredError);

    // A request we know will 401 is not worth sending.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("listApplications and listLearningPaths reject the same way", async () => {
    signedOut();
    await expect(listApplications()).rejects.toBeInstanceOf(AuthRequiredError);

    signedOut();
    await expect(listLearningPaths()).rejects.toBeInstanceOf(AuthRequiredError);
  });
});

describe("with a session, ownership travels in the token", () => {
  it("listLearningPaths sends the bearer token and NO user_id", async () => {
    signedIn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(okJson({ paths: [] }));

    await listLearningPaths();

    const [url, init] = fetchMock.mock.calls[0];
    // The hole: ?user_id=<victim> let anyone read anyone's paths.
    expect(String(url)).toBe("http://localhost:8000/api/v1/learning-paths");
    expect(String(url)).not.toContain("user_id");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok_abc123");
  });

  it("createLearningPath authenticates and does not name its own owner", async () => {
    signedIn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(okJson({ id: "lp_1" }));

    await createLearningPath({
      topic: "RAG",
      expertise_level: "advanced",
      learning_style: "project",
      time_commitment: "5h",
      goals: ["ship an eval"],
    });

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok_abc123");
    expect(String(init?.body)).not.toContain("user_id");
  });

  it("createApplication authenticates and does not name its own owner", async () => {
    signedIn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(okJson({ id: "app_1" }));

    await createApplication({
      company_name: "Anthropic",
      job_title: "Staff Engineer",
      job_url: "https://job-boards.greenhouse.io/anthropic/jobs/1",
    });

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok_abc123");
    expect(String(init?.body)).not.toContain("user_id");
  });
});
