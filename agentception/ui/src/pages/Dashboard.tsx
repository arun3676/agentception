import { Link } from "react-router-dom";
import { ArrowRight, FileSearch, LockKeyhole, Search } from "lucide-react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";

const disabledFeatures = [
  "Resume upload and parsing",
  "Resume-to-job fit assessment",
  "Resume tailoring and export",
  "Saved applications and outcomes",
  "Personal learning paths and skill gaps",
];

const Dashboard = () => (
  <div className="min-h-screen bg-background">
    <TopNav />
    <main className="app-main">
      <section className="mx-auto max-w-4xl py-8 sm:py-14" aria-labelledby="workspace-status-title">
        <div className="card-clean overflow-hidden">
          <div className="border-b border-border p-6 sm:p-10">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-3 py-1 text-xs font-semibold text-muted-foreground">
              <LockKeyhole className="h-3.5 w-3.5" aria-hidden="true" />
              Private features paused
            </span>
            <h1 id="workspace-status-title" className="mt-5 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
              Your dashboard will stay empty until accounts protect ownership.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
              Agentception is not storing a resume, applications, progress, or a generated profile for you right now.
              Those features will return after authenticated storage and deletion controls are in place.
            </p>
          </div>

          <div className="grid gap-6 p-6 sm:grid-cols-2 sm:p-10">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-muted-foreground">Unavailable</h2>
              <ul className="mt-4 space-y-3" aria-label="Unavailable private features">
                {disabledFeatures.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm leading-6">
                    <LockKeyhole className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-border bg-secondary/35 p-5">
              <FileSearch className="h-6 w-6 text-accent" aria-hidden="true" />
              <h2 className="mt-4 text-lg font-bold">What works without an account</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Search public job listings by role and location, open their original source, and browse study resources.
              </p>
              <div className="mt-5 flex flex-col gap-2 sm:flex-row">
                <Button asChild>
                  <Link to="/">
                    <Search className="mr-2 h-4 w-4" aria-hidden="true" /> Search roles
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/resources">
                    Browse resources <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
);

export default Dashboard;
