-- Agentception UI — resume tailoring persistence (matches Edge Function pattern: user_id FK to auth.users)
-- Run in Supabase Dashboard → SQL Editor for project ref hikfndkbqdwxfxesfgdb
-- Safe to re-run: uses IF NOT EXISTS / ON CONFLICT

create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Optional app profile row (mirror of auth.users for future RLS)
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists on_auth_user_created on auth.users;

create or replace function public.handle_new_user ()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user ();

comment on table public.profiles is 'Thin profile row keyed by auth.users; optional for MVP.';

-- Parsed resumes (upload + parse pipeline)
create table if not exists public.resumes (
  id uuid primary key default gen_random_uuid (),
  user_id uuid not null references auth.users (id) on delete cascade,
  storage_object_path text,
  file_name text,
  mime_type text,
  raw_text text,
  ats_text text,
  structured_data jsonb not null default '{}'::jsonb,
  parsing_confidence double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists resumes_user_id_created_at_idx
  on public.resumes (user_id, created_at desc);

comment on table public.resumes is 'Parsed resumes; aligns with frontend ParseResumeResponse (resumeId + structured JSON + texts).';

-- Parsed job postings / JD payloads
create table if not exists public.job_descriptions (
  id uuid primary key default gen_random_uuid (),
  user_id uuid not null references auth.users (id) on delete cascade,
  source_text text not null,
  job_title text,
  company_name text,
  job_url text,
  parsed_data jsonb not null default '{}'::jsonb,
  keywords jsonb not null default '[]'::jsonb,
  parsing_confidence double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists job_descriptions_user_id_created_at_idx
  on public.job_descriptions (user_id, created_at desc);

comment on table public.job_descriptions is 'Parsed job descriptions keyed to auth user; aligns with tailor flow inputs.';

-- Tailored artifacts (persisted GPT output et al.)
create table if not exists public.tailored_resumes (
  id uuid primary key default gen_random_uuid (),
  user_id uuid not null references auth.users (id) on delete cascade,
  resume_id uuid not null references public.resumes (id) on delete cascade,
  job_description_id uuid not null references public.job_descriptions (id) on delete cascade,
  tailored_data jsonb not null default '{}'::jsonb,
  match_score double precision,
  score_breakdown jsonb not null default '{}'::jsonb,
  change_summary jsonb not null default '{}'::jsonb,
  tailoring_confidence double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists tailored_resumes_user_id_created_at_idx
  on public.tailored_resumes (user_id, created_at desc);

comment on table public.tailored_resumes is 'Tailored resume output used by DOCX/PDF regeneration Edge Functions.';

-- Row Level Security defaults (clients use Edge Functions/service role → bypass ok; anon cannot read/write without policies)
alter table public.profiles enable row level security;
alter table public.resumes enable row level security;
alter table public.job_descriptions enable row level security;
alter table public.tailored_resumes enable row level security;

-- Authenticated users can manage their own rows (future-proof if you call PostgREST from the browser)
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid () = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid () = id);

drop policy if exists "resumes_select_own" on public.resumes;
create policy "resumes_select_own" on public.resumes
  for select using (auth.uid () = user_id);

drop policy if exists "resumes_insert_own" on public.resumes;
create policy "resumes_insert_own" on public.resumes
  for insert with check (auth.uid () = user_id);

drop policy if exists "resumes_update_own" on public.resumes;
create policy "resumes_update_own" on public.resumes
  for update using (auth.uid () = user_id);

drop policy if exists "resumes_delete_own" on public.resumes;
create policy "resumes_delete_own" on public.resumes
  for delete using (auth.uid () = user_id);

drop policy if exists "job_descriptions_select_own" on public.job_descriptions;
create policy "job_descriptions_select_own" on public.job_descriptions
  for select using (auth.uid () = user_id);

drop policy if exists "job_descriptions_insert_own" on public.job_descriptions;
create policy "job_descriptions_insert_own" on public.job_descriptions
  for insert with check (auth.uid () = user_id);

drop policy if exists "job_descriptions_update_own" on public.job_descriptions;
create policy "job_descriptions_update_own" on public.job_descriptions
  for update using (auth.uid () = user_id);

drop policy if exists "job_descriptions_delete_own" on public.job_descriptions;
create policy "job_descriptions_delete_own" on public.job_descriptions
  for delete using (auth.uid () = user_id);

drop policy if exists "tailored_resumes_select_own" on public.tailored_resumes;
create policy "tailored_resumes_select_own" on public.tailored_resumes
  for select using (auth.uid () = user_id);

drop policy if exists "tailored_resumes_insert_own" on public.tailored_resumes;
create policy "tailored_resumes_insert_own" on public.tailored_resumes
  for insert with check (auth.uid () = user_id);

drop policy if exists "tailored_resumes_update_own" on public.tailored_resumes;
create policy "tailored_resumes_update_own" on public.tailored_resumes
  for update using (auth.uid () = user_id);

drop policy if exists "tailored_resumes_delete_own" on public.tailored_resumes;
create policy "tailored_resumes_delete_own" on public.tailored_resumes
  for delete using (auth.uid () = user_id);

-- Storage bucket for binary uploads (Edge Functions should use service role / secret key)
insert into storage.buckets (id, name, public)
values ('resume-files', 'resume-files', false)
on conflict (id) do nothing;

-- Keep objects private; Edge Functions can still read/write with service credentials
drop policy if exists "resume_files_no_direct_anon_read" on storage.objects;
create policy "resume_files_no_direct_anon_read"
on storage.objects for select
to anon
using (bucket_id = 'resume-files' and false);

drop policy if exists "resume_files_no_direct_anon_write" on storage.objects;
create policy "resume_files_no_direct_anon_write"
on storage.objects for insert
to anon
with check (bucket_id = 'resume-files' and false);

drop policy if exists "resume_files_auth_read_own" on storage.objects;
create policy "resume_files_auth_read_own"
on storage.objects for select
to authenticated
using (bucket_id = 'resume-files' and owner = auth.uid ());

drop policy if exists "resume_files_auth_write_own" on storage.objects;
create policy "resume_files_auth_write_own"
on storage.objects for insert
to authenticated
with check (bucket_id = 'resume-files' and owner = auth.uid ());

drop policy if exists "resume_files_auth_update_own" on storage.objects;
create policy "resume_files_auth_update_own"
on storage.objects for update
to authenticated
using (bucket_id = 'resume-files' and owner = auth.uid ());

drop policy if exists "resume_files_auth_delete_own" on storage.objects;
create policy "resume_files_auth_delete_own"
on storage.objects for delete
to authenticated
using (bucket_id = 'resume-files' and owner = auth.uid ());
