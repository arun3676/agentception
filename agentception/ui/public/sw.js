const CACHE_NAME = "agentception-v1";
const ASSETS = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  
  // Skip API calls, Supabase Edge Functions, and backend requests
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/functions/v1/") ||
    url.pathname.startsWith("/rag/") ||
    url.pathname.startsWith("/upload/") ||
    url.pathname.startsWith("/results/") ||
    url.pathname.startsWith("/timeline/") ||
    url.pathname.startsWith("/writer/") ||
    url.pathname.startsWith("/save/") ||
    url.pathname.startsWith("/outcomes/") ||
    url.pathname.startsWith("/debug/") ||
    url.pathname.startsWith("/cohort/") ||
    url.pathname.startsWith("/trust-profile/") ||
    url.pathname.startsWith("/portfolio/") ||
    url.pathname.startsWith("/test/") ||
    url.pathname.startsWith("/health")
  ) {
    return; // Let the browser handle it normally (no caching)
  }
  
  // Only cache GET requests for static assets
  if (event.request.method !== "GET") {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});
