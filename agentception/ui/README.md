# Agentception frontend

React 18, TypeScript, Vite, Tailwind, and shadcn/ui frontend for Agentception.

## Current routes

- `/` - anonymous role/location discovery
- `/resources` - public study resources
- `/dashboard` - honest feature-availability status
- Personal routes render an unavailable state until authenticated ownership and
  private APIs are complete.

Removed experimental routes and outreach code are not part of the production
bundle.

## Setup

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Required production variables:

```text
VITE_BACKEND_URL
```

The production build fails when the backend URL is missing. Authentication is
intentionally absent from this containment UI; Supabase browser variables return
only in the reviewed account-foundation change. Never put a Supabase secret/service
key, provider key, shared user ID, or personal data in a `VITE_*` variable.

## Validation

```powershell
npm test
npx tsc --noEmit -p tsconfig.app.json
npm run lint
npm run build
npm run check:bundle
npm audit --omit=dev --audit-level=moderate
```

Generated screenshots, video, traces, and reports are retained only for failed
synthetic tests and are never committed.

Vercel applies the security headers in `vercel.json`. Because static Vercel
configuration cannot substitute `VITE_BACKEND_URL` into a response header, the
containment CSP allows HTTPS API connections by scheme. Replace that scheme
source with the exact stable API origin once deployment metadata is available;
do not guess or add wildcard Railway domains.
