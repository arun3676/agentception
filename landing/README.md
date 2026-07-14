# Agentception — landing page

A self-contained production-scope page with no build step. Its copy is intentionally limited to the current public product: anonymous role/location search, per-result source status, and explicit unavailable states for personal workflows.

```
landing/
  index.html    markup
  styles.css    design tokens mirrored from the app (ui/src/index.css)
  script.js     navigation, reduced-motion-aware reveals, and CTA wiring
```

## Run locally

```bash
cd landing
python -m http.server 4321
# http://localhost:4321
```

On `localhost`, every "Open the app" or "Search roles" CTA points at
`http://localhost:8080` (the Vite dev server). On other hosts it uses the
production URL.

## Before deploying

Set your production app URL at the top of `script.js`:

```js
var APP_URL = ... : "https://agentception.vercel.app";
```

All `[data-app-link]` anchors are pointed there on load, so there is exactly one
place to change.

## Deploy

Deployment is manual. On Vercel, configure `landing/` as the project root with
no build command; the directory is served as-is.

The landing page does not call the application API, so it does not require a
CORS entry.

## Notes

- The hero checklist is an explanatory guide and is explicitly labeled as not
  live data.
- Do not add résumé, tailoring, saved-application, outcome, or personalized
  learning claims until those authenticated workflows are implemented and
  approved for production.
- Animations and delayed reveals are skipped under `prefers-reduced-motion`.
