/**
 * What the "Track" button should do, as data.
 *
 * Job search is public — the search page is deliberately not behind RequireAuth —
 * so Track is reachable while signed out. The original code called the API anyway,
 * caught *everything* with a bare `catch {}`, and told the user:
 *
 *     "Could not save this application — Please try again."
 *
 * Trying again could never work. The user isn't signed in; no number of retries
 * fixes that. The failure was classified wrong, and the wrong classification was
 * then rendered as confident advice.
 *
 * So the classification lives here, on its own, as pure functions. It needs no DOM
 * to test, and the one invariant that matters is enforced by a test:
 *
 *     a signed-out user is NEVER told to retry.
 */

import { AuthRequiredError } from "./api";

export type TrackIntent = "sign-in" | "save";

/** Clicking Track while signed out should send you to sign in, not fire a doomed request. */
export function trackIntent(signedIn: boolean): TrackIntent {
  return signedIn ? "save" : "sign-in";
}

export interface TrackFailure {
  /** "sign-in" -> route the user to /login. "retry" -> retrying is genuinely worth a shot. */
  kind: "sign-in" | "retry";
  title: string;
  description: string;
}

/**
 * Classify a failed save.
 *
 * The session can expire between render and click, so even a signed-in user can
 * land here needing a sign-in — that case must not be reported as a retry either.
 */
export function trackFailure(error: unknown): TrackFailure {
  if (error instanceof AuthRequiredError) {
    return {
      kind: "sign-in",
      title: "Your session expired",
      description: "Sign in again to track this role.",
    };
  }

  // A genuine failure — network, 5xx, a bad payload. Here "try again" is honest,
  // because trying again might actually work.
  return {
    kind: "retry",
    title: "Could not save this application",
    description: "Something went wrong saving it. Please try again.",
  };
}
