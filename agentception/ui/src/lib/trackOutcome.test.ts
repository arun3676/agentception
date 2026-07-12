/**
 * The "Track" button, signed out.
 *
 * Live on this branch: search is public, so Track is clickable while signed out.
 * `createApplication` threw "Sign in to manage applications." — and `handleTrack`
 * caught it with a bare `catch {}` and rendered:
 *
 *     "Could not save this application — Please try again."
 *
 * Retrying can never work when the problem is that you have no session. The user
 * was handed confident, useless advice. These tests pin the invariant.
 */

import { describe, expect, it } from "vitest";

import { AuthRequiredError } from "./api";
import { trackFailure, trackIntent } from "./trackOutcome";

describe("Track: what should happen", () => {
  it("sends a signed-out user to sign in, instead of firing a doomed request", () => {
    expect(trackIntent(false)).toBe("sign-in");
  });

  it("saves when there is a session", () => {
    expect(trackIntent(true)).toBe("save");
  });
});

describe("Track: how a failure is reported", () => {
  it("THE BUG: a signed-out user is never told to retry", () => {
    const failure = trackFailure(new AuthRequiredError());

    expect(failure.kind).toBe("sign-in");
    // The exact regression. "Please try again" is a lie here.
    expect(failure.description).not.toMatch(/try again/i);
    expect(`${failure.title} ${failure.description}`).toMatch(/sign in/i);
  });

  it("still tells the truth about a genuine failure — retrying may actually work", () => {
    const failure = trackFailure(new Error("500 Internal Server Error"));

    expect(failure.kind).toBe("retry");
    expect(failure.description).toMatch(/try again/i);
    // ...and must NOT send a signed-in user off to a pointless login screen.
    expect(failure.title).not.toMatch(/sign in|session/i);
  });

  it("classifies by type, not by message text", () => {
    // A server error that happens to mention signing in must NOT be mistaken for
    // a missing session. String-matching error messages is what we're avoiding.
    const failure = trackFailure(new Error("could not sign in to upstream provider"));
    expect(failure.kind).toBe("retry");
  });

  it("treats a non-Error throw as a genuine failure rather than crashing", () => {
    expect(trackFailure("boom").kind).toBe("retry");
    expect(trackFailure(undefined).kind).toBe("retry");
  });
});
