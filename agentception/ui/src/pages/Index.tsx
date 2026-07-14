import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Map, Radar, Target } from "lucide-react";

import { JobCard } from "@/components/JobCard";
import { SearchForm } from "@/components/SearchForm";
import { Timeline } from "@/components/Timeline";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { getResults, type RAGResults } from "@/lib/api";
import { normalizeJobCard, type JobCard as JobCardType } from "@/lib/jobCardNormalization";

type SearchStatus = "idle" | "running" | "succeeded" | "failed";

const STATUS_LABEL: Record<SearchStatus, string> = {
  idle: "Ready",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
};

const Index = () => {
  const [runId, setRunId] = useState<string | null>(null);
  const [searchStatus, setSearchStatus] = useState<SearchStatus>("idle");
  const [results, setResults] = useState<RAGResults | null>(null);
  const [jobCards, setJobCards] = useState<JobCardType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [failedOffset, setFailedOffset] = useState<number | null>(null);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [showTimeline, setShowTimeline] = useState(true);

  const activeRunRef = useRef<string | null>(null);
  const timelineRef = useRef<HTMLElement>(null);
  const resultsRef = useRef<HTMLElement>(null);
  const scrolledToResults = useRef(false);

  const revealResults = useCallback(() => {
    if (scrolledToResults.current) return;
    scrolledToResults.current = true;
    requestAnimationFrame(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  const loadResults = useCallback(async (targetRunId: string, offset: number) => {
    setIsLoading(true);
    setResultsError(null);
    setFailedOffset(null);
    if (offset === 0) setSearchStatus("running");

    try {
      const data = await getResults(targetRunId, offset, 5);
      if (activeRunRef.current !== targetRunId) return;

      // Mapping is one-to-one and intentionally preserves backend source order.
      const returnedCards = data.companies.map((company) => normalizeJobCard(company));
      setResults(data);
      setJobCards((previous) => offset > 0 ? [...previous, ...returnedCards] : returnedCards);
      setHasMore(data.pagination.has_more);

      if (offset === 0) {
        setSearchStatus("succeeded");
        // A successful empty response is still a visible, meaningful state.
        revealResults();
      }
    } catch {
      if (activeRunRef.current !== targetRunId) return;
      const message = "Returned listings could not be retrieved. No results were assumed.";
      setResultsError(message);
      setFailedOffset(offset);
      if (offset === 0) {
        setSearchStatus("failed");
        revealResults();
      }
      toast({ title: "Failed to load results", description: message, variant: "destructive" });
    } finally {
      if (activeRunRef.current === targetRunId) setIsLoading(false);
    }
  }, [revealResults]);

  const handleTimelineComplete = useCallback((completedRunId: string) => {
    if (activeRunRef.current === completedRunId) void loadResults(completedRunId, 0);
  }, [loadResults]);

  const handleTimelineFailed = useCallback((failedRunId: string) => {
    if (activeRunRef.current !== failedRunId) return;
    setSearchStatus("failed");
    setIsLoading(false);
    setFailedOffset(null);
    setResultsError("The search did not report a successful terminal state. No results were assumed.");
    revealResults();
  }, [revealResults]);

  useEffect(() => {
    if (!runId || currentOffset === 0) return;
    void loadResults(runId, currentOffset);
  }, [runId, currentOffset, loadResults]);

  const handleSearchStart = (newRunId: string) => {
    activeRunRef.current = newRunId;
    setRunId(newRunId);
    setSearchStatus("running");
    setCurrentOffset(0);
    setJobCards([]);
    setResults(null);
    setResultsError(null);
    setFailedOffset(null);
    setHasMore(false);
    setShowTimeline(true);
    scrolledToResults.current = false;
    requestAnimationFrame(() => {
      timelineRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const handleLoadMore = () => {
    if (!runId || !hasMore || isLoading || searchStatus !== "succeeded") return;
    setCurrentOffset((previous) => previous + 5);
  };

  const roleDisplay = results?.role || "role unavailable";
  const locationDisplay = results?.city || "location unavailable";
  const totalCompanies = results?.pagination.total || 0;
  const companiesWithJobs = jobCards.length;

  const evidenceStages = [
    {
      title: "Public search",
      description: searchStatus === "succeeded"
        ? "Search finished and the result response was retrieved"
        : searchStatus === "failed"
          ? "Search or result retrieval did not finish successfully"
          : searchStatus === "running"
            ? "Waiting for search events and a terminal state"
            : "Choose a role and location",
      badge: STATUS_LABEL[searchStatus],
      state: searchStatus === "succeeded" ? "complete" : searchStatus === "failed" ? "locked" : "active",
      icon: Radar,
    },
    {
      title: "Role evidence",
      description: searchStatus === "succeeded"
        ? companiesWithJobs > 0
          ? `${companiesWithJobs} source listing${companiesWithJobs === 1 ? "" : "s"} returned`
          : "No source listings were returned"
        : searchStatus === "failed"
          ? "Unavailable because the search did not succeed"
          : "Appears after a successful result response",
      badge: searchStatus === "succeeded" ? (companiesWithJobs > 0 ? "Available" : "Empty") : "Waiting",
      state: searchStatus === "succeeded" ? "complete" : searchStatus === "running" ? "active" : "locked",
      icon: Target,
    },
    {
      title: "Private workspace",
      description: "Resume, saving, and tailoring stay off until secure accounts are ready",
      badge: "Unavailable",
      state: "locked",
      icon: Map,
    },
  ];

  const showResultsSection = jobCards.length > 0
    || isLoading
    || searchStatus === "succeeded"
    || (searchStatus === "failed" && Boolean(resultsError));

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <TopNav />
      <main className="app-main">
        <section className="app-hero">
          <div className="app-hero-copy">
            <span className="inline-status">Career evidence workspace</span>
            <h1 className="app-hero-title">Find job listings.<br /><span>Keep the source in view.</span></h1>
            <p className="app-hero-summary">
              Search by role and location, review the returned source, and use cited study resources while private account features are rebuilt.
            </p>
          </div>
          <aside className="app-pulse" aria-label="Current search status">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="section-label">Workspace status</p>
                <h2 className="mt-2 text-lg font-extrabold tracking-[-0.035em]">Current session</h2>
              </div>
              <span className="mt-1 h-2.5 w-2.5 rounded-full bg-accent" />
            </div>
            <dl className="app-pulse-grid">
              <div><dt>Personal data</dt><dd>Off</dd></div>
              <div><dt>Search</dt><dd>{STATUS_LABEL[searchStatus]}</dd></div>
              <div><dt>Listings</dt><dd>{searchStatus === "succeeded" ? companiesWithJobs : "—"}</dd></div>
            </dl>
            <p className="mt-4 text-xs leading-5 text-muted-foreground">Counts describe returned entries only; they are not fit or hiring predictions.</p>
          </aside>
        </section>

        <div className="workspace-grid">
          <div className="space-y-5">
            <section className="workspace-panel overflow-hidden">
              <div className="workspace-panel-head">
                <div>
                  <p className="section-label">Start a public search</p>
                  <h2 className="mt-2 text-xl font-extrabold tracking-[-0.04em] sm:text-2xl">Find source-linked roles.</h2>
                </div>
                <p className="max-w-sm text-xs leading-5 text-muted-foreground sm:text-right">Choose both a role and location. Results link back to their returned source.</p>
              </div>
              <div className="workspace-panel-body"><SearchForm onSearchStart={handleSearchStart} /></div>
            </section>

            {runId && (
              <section ref={timelineRef} className="workspace-panel scroll-mt-6 overflow-hidden">
                <div className="workspace-panel-head flex-row items-center">
                  <div><p className="section-label">Search timeline</p><h2 className="mt-2 text-lg font-extrabold tracking-[-0.03em]">Search updates</h2></div>
                  <Button variant="ghost" size="sm" className="shrink-0 gap-1.5 rounded-lg text-xs" onClick={() => setShowTimeline((value) => !value)}>
                    {showTimeline ? "Hide" : "Show"}<ChevronDown className={`h-4 w-4 transition-transform ${showTimeline ? "" : "-rotate-90"}`} />
                  </Button>
                </div>
                <div className={`${showTimeline ? "block" : "hidden"} p-4 sm:p-6`}>
                  <Timeline runId={runId} onComplete={handleTimelineComplete} onFailed={handleTimelineFailed} />
                </div>
              </section>
            )}

            {showResultsSection && (
              <section ref={resultsRef} className="scroll-mt-6 pt-2">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="section-label">Role evidence</p>
                    <h2 className="mt-2 text-xl font-extrabold tracking-[-0.04em] sm:text-2xl">Source listings</h2>
                    <p className="mt-1.5 text-xs leading-5 text-muted-foreground sm:text-sm">
                      {isLoading && "Retrieving the result response."}
                      {!isLoading && searchStatus === "succeeded" && companiesWithJobs > 0 && `Showing ${companiesWithJobs} of ${totalCompanies || companiesWithJobs} returned listings for ${roleDisplay} in ${locationDisplay}.`}
                      {!isLoading && searchStatus === "succeeded" && companiesWithJobs === 0 && "The search succeeded, but returned no listings."}
                      {!isLoading && searchStatus === "failed" && "Listings are unavailable because the search or result request failed."}
                    </p>
                  </div>
                  {hasMore && searchStatus === "succeeded" && (
                    <Button variant="outline" onClick={handleLoadMore} disabled={isLoading} className="w-full rounded-lg text-xs sm:w-auto">
                      {isLoading ? "Loading…" : "Load more"}
                    </Button>
                  )}
                </div>

                {resultsError && (
                  <div role="alert" className="mb-4 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                    <p>{resultsError}</p>
                    {failedOffset !== null && (
                      <Button variant="outline" size="sm" className="mt-3" onClick={() => runId && void loadResults(runId, failedOffset)} disabled={isLoading}>
                        Retry result retrieval
                      </Button>
                    )}
                  </div>
                )}

                {isLoading && jobCards.length === 0 ? (
                  <div className="grid gap-4">{[1, 2, 3].map((item) => <div key={item} className="card-clean animate-pulse p-6"><div className="mb-3 h-6 w-3/4 rounded bg-muted" /><div className="h-4 w-1/2 rounded bg-muted" /></div>)}</div>
                ) : searchStatus === "succeeded" && jobCards.length === 0 ? (
                  <div className="card-clean p-6 text-sm text-muted-foreground" role="status">
                    No listing entries were returned. Try a different role or location; no placeholder listings were created.
                  </div>
                ) : jobCards.length > 0 ? (
                  <div className="grid gap-4">{jobCards.map((job, index) => <JobCard key={`${job.applyUrl || "unavailable"}-${index}`} {...job} />)}</div>
                ) : null}
              </section>
            )}

            <section className="workspace-panel p-5 sm:p-6" role="status">
              <p className="section-label">Private workspace</p>
              <h3 className="mt-2 text-lg font-extrabold tracking-[-0.03em]">Resume and application actions are unavailable.</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                Upload, tailoring, saving, and outcome tracking will return only after accounts can enforce private ownership. Public role search does not collect resume data.
              </p>
            </section>
          </div>

          <aside className="space-y-5 xl:sticky xl:top-8">
            <section className="evidence-ledger" aria-label="Workflow status">
              <div className="evidence-ledger-head">
                <div><p className="section-label">Workflow status</p><h2 className="mt-1.5 text-base font-extrabold tracking-[-0.03em]">Available steps</h2></div>
                <span className="flex items-center gap-1.5 text-[10px] font-bold text-accent"><span className="h-1.5 w-1.5 rounded-full bg-accent" /> {STATUS_LABEL[searchStatus]}</span>
              </div>
              <ol className="evidence-ledger-list">
                {evidenceStages.map((stage, index) => (
                  <li key={stage.title} className="evidence-stage" data-state={stage.state} style={{ "--stage": index } as CSSProperties}>
                    <span className="evidence-stage-icon"><stage.icon className="h-4 w-4" /></span>
                    <div><h3>{stage.title}</h3><p>{stage.description}</p></div>
                    <span className="evidence-stage-badge">{stage.badge}</span>
                  </li>
                ))}
              </ol>
              <div className="grid grid-cols-2 gap-2 border-t border-border p-3">
                <Link to="/resources" className="flex items-center justify-between rounded-lg bg-secondary/60 px-3 py-2.5 text-xs font-bold hover:bg-secondary">Study resources <Map className="h-3.5 w-3.5" /></Link>
                <Link to="/dashboard" className="flex items-center justify-between rounded-lg bg-secondary/60 px-3 py-2.5 text-xs font-bold hover:bg-secondary">Feature status <ArrowUpRight className="h-3.5 w-3.5" /></Link>
              </div>
            </section>

            <section className="workspace-panel p-5">
              <p className="section-label">Next destinations</p>
              <nav className="mt-3 divide-y divide-border">
                {[["Study resources", "/resources"], ["Private feature status", "/dashboard"]].map(([label, href]) => (
                  <Link key={href} to={href} className="flex items-center justify-between py-3 text-sm font-semibold transition-colors hover:text-accent">{label}<ArrowUpRight className="h-4 w-4" /></Link>
                ))}
              </nav>
            </section>
          </aside>
        </div>

        <footer className="mt-8 flex flex-col gap-3 border-t border-border py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>Agentception &mdash; source-linked role discovery.</p>
          <div className="flex flex-wrap gap-4"><Link to="/resources" className="hover:text-foreground">Study</Link><Link to="/dashboard" className="hover:text-foreground">Feature status</Link></div>
        </footer>
      </main>
    </div>
  );
};

export default Index;
