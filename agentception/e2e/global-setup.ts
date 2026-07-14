const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

function requireLocalHttpUrl(raw: string, variable: string): void {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error(`${variable} must be a valid local HTTP URL`);
  }

  if (url.protocol !== "http:" || !LOCAL_HOSTS.has(url.hostname) || url.username || url.password) {
    throw new Error(
      `${variable} must point to localhost. Containment E2E must never run against a deployed service.`,
    );
  }
}

export default function globalSetup(): void {
  requireLocalHttpUrl(
    process.env.E2E_FRONTEND_URL ?? "http://127.0.0.1:18080",
    "E2E_FRONTEND_URL",
  );
  requireLocalHttpUrl(
    process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:18000",
    "E2E_BACKEND_URL",
  );
}
