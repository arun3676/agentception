import { describe, expect, it } from "vitest";
import { toSafeExternalUrl } from "./safeUrl";

describe("toSafeExternalUrl", () => {
  it("allows source links over HTTP and HTTPS", () => {
    expect(toSafeExternalUrl("https://jobs.example.org/role?id=1")).toBe("https://jobs.example.org/role?id=1");
    expect(toSafeExternalUrl("http://example.org/jobs")).toBe("http://example.org/jobs");
  });

  it("rejects executable, credentialed, relative, and malformed links", () => {
    expect(toSafeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(toSafeExternalUrl("data:text/html,hello")).toBeNull();
    expect(toSafeExternalUrl("https://user:secret@example.org/job")).toBeNull();
    expect(toSafeExternalUrl("/jobs/1")).toBeNull();
    expect(toSafeExternalUrl("not a url")).toBeNull();
  });
});
