/**
 * Checks that tailor-related tables exist (PostgREST).
 * Loads ../../.env.local when env vars are missing (simple KEY=VAL parser).
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadEnvLocal() {
  const envPath = path.join(__dirname, "..", ".env.local");
  if (!fs.existsSync(envPath)) return;
  const text = fs.readFileSync(envPath, "utf8");
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq === -1) continue;
    const k = t.slice(0, eq).trim();
    let v = t.slice(eq + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    if (!(k in process.env) || process.env[k] === "") {
      process.env[k] = v;
    }
  }
}

loadEnvLocal();

const url = process.env.VITE_SUPABASE_URL;
const service = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!url || !service) {
  console.error(
    "Set VITE_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (in env or ui/.env.local).",
  );
  process.exit(1);
}

const base = url.replace(/\/$/, "");
const tables = ["resumes", "job_descriptions", "tailored_resumes", "profiles"];

async function checkTable(table) {
  const res = await fetch(`${base}/rest/v1/${table}?select=id&limit=1`, {
    headers: {
      apikey: service,
      Authorization: `Bearer ${service}`,
      Accept: "application/json",
    },
  });
  const ok = res.ok;
  let body = "";
  try {
    body = await res.text();
  } catch {
    body = "";
  }
  return { table, status: res.status, ok, snippet: body.slice(0, 240) };
}

const results = [];
for (const t of tables) {
  results.push(await checkTable(t));
}

let failed = false;
for (const r of results) {
  console.log(`${r.table}: HTTP ${r.status} ${r.ok ? "OK" : "FAIL"}`);
  if (!r.ok) {
    failed = true;
    console.error(r.snippet);
  }
}

if (failed) {
  console.error(
    "\nIf tables are missing, open Supabase Dashboard → SQL Editor → paste ui/supabase/migrations/001_agentception_resume_tables.sql → Run.",
  );
  process.exit(1);
}

console.log("\nAll checked tables responded successfully (schema is present).");
