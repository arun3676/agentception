import { describe, expect, it } from "vitest";
import { validateSearchInput } from "./SearchForm";

describe("validateSearchInput", () => {
  it("requires an explicit role", () => {
    expect(validateSearchInput("San Francisco, CA", "")).toBe("Choose a role to search.");
  });

  it("requires a location", () => {
    expect(validateSearchInput("", "Backend Engineer")).toBe("Enter a location to search.");
  });

  it("accepts complete anonymous discovery input", () => {
    expect(validateSearchInput("San Francisco, CA", "Backend Engineer")).toBeNull();
  });
});
