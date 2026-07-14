import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, createTimelineStream, fetchResources, searchCompanies } from "./api";

const jsonResponse = (body: unknown) =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  } as Response);

describe("production API contracts", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("starts anonymous discovery with role and location only", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({ run_id: "run_1" }));

    await searchCompanies({ city: "San Francisco, CA", role: "Backend Engineer", depth: "standard" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/rag/companies",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ city: "San Francisco, CA", role: "Backend Engineer", depth: "standard" }),
      }),
    );
  });

  it("keeps public study resources available", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(await jsonResponse({ items: [], count: 0 }));

    await fetchResources({ q: "system design", limit: 10 });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8000/api/v1/resources?q=system+design&limit=10",
    );
  });

  it("preserves the safe API error envelope for retry decisions", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers({ "x-request-id": "request-from-header" }),
      json: () => Promise.resolve({
        error: {
          code: "service_not_ready",
          message: "Service is not ready",
          retryable: true,
          request_id: "request-from-body",
        },
      }),
    } as Response);

    await expect(fetchResources({ limit: 1 })).rejects.toMatchObject<ApiRequestError>({
      code: "service_not_ready",
      message: "Service is not ready",
      retryable: true,
      requestId: "request-from-body",
      status: 503,
    });
  });

  it("fails a timeline that never reports a terminal event", () => {
    vi.useFakeTimers();
    const nativeClose = vi.fn();
    class FakeEventSource {
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      close = nativeClose;
      addEventListener = vi.fn();
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    const onError = vi.fn();

    createTimelineStream("synthetic-run", vi.fn(), vi.fn(), onError, 50);
    vi.advanceTimersByTime(51);

    expect(nativeClose).toHaveBeenCalledOnce();
    expect(onError).toHaveBeenCalledOnce();
  });
});
