# Agentception Frontend

Modern React + Vite frontend for the Agentception job search assistant.

## Tech Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - Component library
- **React Router** - Routing
- **TanStack Query** - Data fetching (ready for future use)

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file (optional, defaults to `http://localhost:8000`):
```env
VITE_BACKEND_URL=http://localhost:8000
```

### Supabase Resume Tailoring Setup

The Tailor Resume flow talks directly to Supabase Edge Functions. To let those functions write to Postgres, supply your Supabase credentials **and** a valid user id that already exists under `auth.users`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_SUPABASE_DEFAULT_USER_ID=00000000-0000-0000-0000-000000000000
```

Optional (new API key model): keep `VITE_SUPABASE_PUBLISHABLE_KEY` alongside the legacy anon JWT.  
Server-only: `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_SECRET_API_KEY`.

`VITE_SUPABASE_DEFAULT_USER_ID` should point to an actual user created in Supabase Auth (copy the UUID from Dashboard → Authentication → Users).  
If you have your own auth layer, pass `userId` into the helper functions instead of relying on the default.

Apply the database objects once per project: open `supabase/migrations/001_agentception_resume_tables.sql` in Dashboard → SQL Editor (or use a `sbp_` personal access token with the Supabase CLI).  
Then verify with `npm run verify:supabase-schema`.

Without tables + a valid user id, uploads will fail with `resumes_user_id_fkey` because the database enforces `user_id → auth.users`.

See also `ui/.env.example` for Next.js-style `NEXT_PUBLIC_SUPABASE_*` variables.

3. Start development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:8080`

## Backend Connection

The frontend connects to the FastAPI backend running on port 8000. Make sure the backend is running before starting the frontend.

The backend URL can be configured via:
- Environment variable: `VITE_BACKEND_URL`
- Default: `http://localhost:8000`

## Project Structure

```
src/
├── components/          # React components
│   ├── SearchForm.tsx   # Job search form
│   ├── Timeline.tsx     # Real-time progress timeline
│   ├── JobCard.tsx      # Job listing card
│   ├── EmailCard.tsx    # Generated email card
│   └── ui/             # shadcn/ui components
├── lib/
│   ├── api.ts          # Backend API utilities
│   └── jobCardNormalization.ts  # Job card normalization logic
├── pages/
│   └── Index.tsx       # Main page
└── hooks/
    └── use-toast.ts    # Toast notification hook
```

## Features

- **Job Search**: Search for jobs by location and role
- **Resume Upload**: Upload PDF resume for role detection
- **Real-time Timeline**: SSE-based progress updates
- **Job Cards**: Normalized job listings with match scores
- **Email Generation**: Generate personalized outreach emails
- **Pagination**: Load more results incrementally

## API Integration

All API calls are centralized in `src/lib/api.ts`:

- `uploadResume()` - Upload PDF resume
- `searchCompanies()` - Start job search
- `getResults()` - Get search results with pagination
- `generateEmails()` - Generate outreach emails
- `createTimelineStream()` - SSE stream for timeline events

## Build

```bash
npm run build
```

Production build will be in `dist/` directory.

## Development

The Vite dev server includes:
- Hot Module Replacement (HMR)
- TypeScript support
- Path aliases (`@/` → `src/`)
- Proxy for backend API (optional, via `/api` prefix)

