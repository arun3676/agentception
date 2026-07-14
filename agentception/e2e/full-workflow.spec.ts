import { expect, test as base, type Page } from "@playwright/test";

const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:18000";

type BrowserMonitor = {
  failures: string[];
};

const test = base.extend<{ browserMonitor: BrowserMonitor }>({
  browserMonitor: async ({ page }, use) => {
    const failures: string[] = [];
    const monitoredResourceTypes = new Set([
      "document",
      "script",
      "stylesheet",
      "xhr",
      "fetch",
      "eventsource",
    ]);

    // The UI's remote fonts are decorative. Stub them so an unrelated CDN or
    // offline CI worker cannot make a product-flow test flaky.
    await page.route("https://fonts.googleapis.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/css", body: "" }),
    );

    page.on("console", (message) => {
      if (message.type() === "error") failures.push(`console: ${message.text()}`);
    });
    page.on("pageerror", (error) => failures.push(`page: ${error.message}`));
    page.on("requestfailed", (request) => {
      if (monitoredResourceTypes.has(request.resourceType())) {
        failures.push(
          `request: ${request.method()} ${request.url()} (${request.failure()?.errorText ?? "failed"})`,
        );
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && monitoredResourceTypes.has(response.request().resourceType())) {
        failures.push(`response: ${response.status()} ${response.request().method()} ${response.url()}`);
      }
    });

    await use({ failures });
    expect(failures, "The page emitted browser, console, or network errors").toEqual([]);
  },
});

async function expectAccessiblePageShell(page: Page, heading: RegExp | string) {
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  await expect(page.locator("h1")).toHaveCount(1);

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(horizontalOverflow, "The page must not overflow horizontally at this viewport").toBeLessThanOrEqual(1);
}

async function mockPublicSearch(page: Page) {
  await page.route("**/rag/companies", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ run_id: "synthetic-search-run" }),
    });
  });

  await page.route("**/timeline/synthetic-search-run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-cache" },
      body:
        'data: {"run_id":"synthetic-search-run","agent":"Search","message":"Found 1 results"}\n\n' +
        'event: end\ndata: {"status":"succeeded"}\n\n',
    });
  });

  await page.route("**/results/synthetic-search-run?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "synthetic-search-run",
        city: "Austin, TX",
        role: "Backend Engineer",
        companies: [
          {
            company_name: "Example Systems",
            homepage_url: "https://example.org",
            job_title: "Backend Engineer",
            job_url: "https://jobs.example.org/backend-engineer",
            job_location: "Austin, TX",
            job_source: "Tavily",
            blurb: "A synthetic source-linked listing used only for deterministic browser testing.",
            observed_at: "2026-07-13T00:00:00Z",
            description_origin: "provider_snippet",
            remote_policy: "unknown",
            listing_data_quality: "complete",
          },
        ],
        pagination: { offset: 0, limit: 5, total: 1, has_more: false },
      }),
    });
  });
}

test.describe("production containment", () => {
  test("public health exposes readiness only, never provider or key details", async ({ request }) => {
    const response = await request.get(`${BACKEND_URL}/health`);
    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    expect(response.headers()["content-security-policy"]).toContain("default-src 'none'");
    expect(response.headers()["x-content-type-options"]).toBe("nosniff");
    expect(response.headers()["access-control-allow-credentials"]).toBeUndefined();

    const serialized = (await response.body()).toString("utf8").toLowerCase();
    expect(serialized).not.toMatch(/api.?key|key.?prefix|provider|tavily|exa|openai|deepseek|usage|cost/);
  });

  test("anonymous search sends only the role/location contract and renders a source", async ({
    page,
    browserMonitor: _browserMonitor,
  }) => {
    await mockPublicSearch(page);
    await page.goto("/");

    await expectAccessiblePageShell(page, /Find job listings/i);
    await expect(page.getByLabel("Location")).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Desired role" })).toBeVisible();
    await expect(page.locator('input[type="file"]')).toHaveCount(0);

    await page.getByLabel("Location").fill("Austin, TX");
    await page.getByRole("combobox", { name: "Desired role" }).click();
    await page.getByRole("option", { name: "Backend Engineer", exact: true }).click();

    const searchRequest = page.waitForRequest(
      (request) => request.method() === "POST" && new URL(request.url()).pathname === "/rag/companies",
    );
    await page.getByRole("button", { name: "Search Jobs" }).click();

    const request = await searchRequest;
    expect(request.postDataJSON()).toEqual({
      city: "Austin, TX",
      role: "Backend Engineer",
      depth: "standard",
    });
    expect(request.headers()["authorization"]).toBeUndefined();

    await expect(page.getByRole("heading", { name: "Source listings" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Backend Engineer", level: 3 })).toBeVisible();
    await expect(page.getByRole("button", { name: /Open Backend Engineer.* listing/ })).toBeEnabled();
    await expect(page.getByText("Tavily", { exact: true })).toBeVisible();
    await expect(page.getByText("Jul 13, 2026", { exact: true })).toBeVisible();
    await expect(page.getByText(/Public role search does not collect resume data/i)).toBeVisible();
  });

  test("successful empty discovery is explicit and creates no placeholder listing", async ({
    page,
    browserMonitor: _browserMonitor,
  }) => {
    await page.route("**/rag/companies", (route) => route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ run_id: "synthetic-empty-run", status: "queued" }),
    }));
    await page.route("**/timeline/synthetic-empty-run", (route) => route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'event: end\ndata: {"status":"succeeded"}\n\n',
    }));
    await page.route("**/results/synthetic-empty-run?*", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "synthetic-empty-run",
        city: "Austin, TX",
        role: "Backend Engineer",
        companies: [],
        pagination: { offset: 0, limit: 5, total: 0, has_more: false },
      }),
    }));

    await page.goto("/");
    await page.getByLabel("Location").fill("Austin, TX");
    await page.getByRole("combobox", { name: "Desired role" }).click();
    await page.getByRole("option", { name: "Backend Engineer", exact: true }).click();
    await page.getByRole("button", { name: "Search Jobs" }).click();

    await expect(page.getByText(/No listing entries were returned/i)).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(0);
  });

  test("failed terminal event never becomes a completed result", async ({
    page,
    browserMonitor: _browserMonitor,
  }) => {
    await page.route("**/rag/companies", (route) => route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ run_id: "synthetic-failed-run", status: "queued" }),
    }));
    await page.route("**/timeline/synthetic-failed-run", (route) => route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'event: end\ndata: {"status":"failed"}\n\n',
    }));

    await page.goto("/");
    await page.getByLabel("Location").fill("Austin, TX");
    await page.getByRole("combobox", { name: "Desired role" }).click();
    await page.getByRole("option", { name: "Backend Engineer", exact: true }).click();
    await page.getByRole("button", { name: "Search Jobs" }).click();

    await expect(page.getByText(/did not report a successful terminal state/i)).toBeVisible();
    await expect(
      page.getByRole("complementary", { name: "Current search status" }).getByText("Failed", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Backend Engineer", level: 3 })).toHaveCount(0);
  });

  test("public resources remain source-linked and explain their limits", async ({
    page,
    browserMonitor: _browserMonitor,
  }) => {
    await page.route("**/api/v1/study/pillars", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ pillars: [{ key: "backend", label: "Backend", keywords: ["HTTP", "SQL"] }] }),
      }),
    );
    await page.route("**/api/v1/resources?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          items: [
            {
              id: "synthetic-resource-1",
              title: "HTTP semantics reference",
              description: "A synthetic catalogue entry for browser validation.",
              url: "https://docs.example.org/http",
              category: "Documentation",
            },
          ],
        }),
      }),
    );

    await page.goto("/resources");
    await expectAccessiblePageShell(page, /Browse learning references/i);
    await expect(page.getByLabel("Search the resource catalogue")).toBeVisible();
    await expect(page.getByText(/Inclusion is not an endorsement, ranking, or guarantee/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "HTTP semantics reference" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open source" })).toHaveAttribute(
      "href",
      "https://docs.example.org/http",
    );
  });

  test("private personal-data routes show one explicit unavailable state and no upload control", async ({
    page,
    browserMonitor: _browserMonitor,
  }) => {
    const privateRoutes = [
      ["/tailor-resume", "Resume tailoring"],
      ["/applications", "Application tracking"],
      ["/learning-paths", "Personal learning paths"],
      ["/skill-gaps", "Resume skill analysis"],
    ] as const;

    for (const [path, feature] of privateRoutes) {
      await page.goto(path);
      await expectAccessiblePageShell(page, `${feature} is temporarily unavailable.`);
      await expect(page.getByText(/authentication, private ownership, retention, and deletion controls/i)).toBeVisible();
      await expect(page.locator('input[type="file"]')).toHaveCount(0);
    }
  });

  test("retired beta routes and navigation labels are absent", async ({
    page,
    browserMonitor: _browserMonitor,
  }, testInfo) => {
    const retiredRoutes = [
      "/outreach",
      "/trust-profile",
      "/portfolio",
      "/cohort",
      "/career-reverse-engineer",
      "/audit",
      "/one-thing",
      "/verdict-loop",
      "/system-health",
    ];

    for (const path of retiredRoutes) {
      await page.goto(path);
      await expectAccessiblePageShell(page, "Page not found");
    }

    await page.goto("/");
    const visibleNavigation = page.locator(
      'nav[aria-label="Primary navigation"]:visible, nav[aria-label="Mobile navigation"]:visible',
    );
    await expect(visibleNavigation).toContainText("Search");
    await expect(visibleNavigation).toContainText("Study");
    await expect(visibleNavigation).not.toContainText(
      /Outreach|Trust Profile|Portfolio|Cohort|Reverse Engineer|Audit|One Thing|Verdict|System Health/i,
    );

    if (testInfo.project.name === "mobile-chromium") {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(page.getByRole("dialog", { name: "Navigation" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Close navigation" }).last()).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog", { name: "Navigation" })).toHaveCount(0);
    }
  });
});
