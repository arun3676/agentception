import { useState, useEffect, useCallback, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { SearchForm } from "@/components/SearchForm";
import { Timeline } from "@/components/Timeline";
import { JobCard } from "@/components/JobCard";
import { ResumeViewer } from "@/components/ResumeViewer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  CircleCheck,
  FileCheck2,
  Map,
  Radar,
  Sparkles,
  Target,
} from "lucide-react";
import { getResults, type RAGResults, type ResumeStructured } from "@/lib/api";
import { normalizeJobCard, sortJobCards, groupJobCards, type JobCard as JobCardType } from "@/lib/jobCardNormalization";
import { toast } from "@/hooks/use-toast";
import { TopNav } from "@/components/TopNav";
import { useStudyDrawer } from "@/hooks/use-study-drawer";

interface ResumeInsights {
  role?: string;
  skills?: string[];
  skills_flat?: string[];
  years_experience?: number;
  tech_stack?: string[];
  [key: string]: unknown;
}

const Index = () => {
  const [runId, setRunId] = useState<string | null>(null);
  const [resumeToken, setResumeToken] = useState<string | null>(null);
  const [resumeInsights, setResumeInsights] = useState<ResumeInsights | null>(null);
  const [resumeText, setResumeText] = useState<string | null>(null);
  const [resumeFileName, setResumeFileName] = useState<string | null>(null);
  const [resumeStructured, setResumeStructured] = useState<ResumeStructured | null>(null);
  const [results, setResults] = useState<RAGResults | null>(null);
  const [jobCards, setJobCards] = useState<JobCardType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentOffset, setCurrentOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [detectedRole, setDetectedRole] = useState<string | null>(null);
  const [showTimeline, setShowTimeline] = useState(true);
  const { openStudy, studyDrawer } = useStudyDrawer();

  const loadResults = useCallback(async (offset: number) => {
    if (!runId) return;
    setIsLoading(true);
    try {
      const data = await getResults(runId, offset, 5);
      setResults(data);
      setDetectedRole(data.role || null);
      const normalized = data.companies
        .map((company) => normalizeJobCard(company, data.role))
        .filter((card): card is JobCardType => card !== null);
      const grouped = groupJobCards(sortJobCards(normalized));
      const displayCards = [...grouped.directRoles, ...grouped.listings];
      setJobCards((previous) => offset > 0 ? [...previous, ...displayCards] : displayCards);
      setHasMore(data.pagination.has_more);
    } catch (error) {
      console.error("[Index] Failed to load results:", error);
      toast({
        title: "Failed to load results",
        description: "Please try again later",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [runId]);

  const handleTimelineComplete = () => {
    window.setTimeout(() => { loadResults(0); }, 1000);
  };

  useEffect(() => {
    if (!runId || currentOffset === 0) return;
    loadResults(currentOffset);
  }, [runId, currentOffset, loadResults]);

  const handleSearchStart = (newRunId: string) => {
    setRunId(newRunId);
    setCurrentOffset(0);
    setJobCards([]);
    setResults(null);
    setHasMore(false);
  };

  const handleResumeUploaded = (token: string, insights?: ResumeInsights, textPreview?: string, fileName?: string, structured?: ResumeStructured) => {
    setResumeToken(token);
    if (insights) setResumeInsights(insights);
    if (textPreview) setResumeText(textPreview);
    if (fileName) setResumeFileName(fileName);
    if (structured) setResumeStructured(structured);
  };

  const handleLoadMore = () => {
    if (!runId || !hasMore || isLoading) return;
    setCurrentOffset((previous) => previous + 5);
  };

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem("agentception:home");
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (parsed.resumeInsights) setResumeInsights(parsed.resumeInsights);
      if (parsed.resumeToken) setResumeToken(parsed.resumeToken);
      if (parsed.resumeText) setResumeText(parsed.resumeText);
      if (parsed.resumeFileName) setResumeFileName(parsed.resumeFileName);
      if (parsed.resumeStructured) setResumeStructured(parsed.resumeStructured);
    } catch (error) {
      console.warn("Failed to restore session", error);
    }
  }, []);

  useEffect(() => {
    const payload = { resumeToken, resumeInsights, resumeText, resumeFileName, resumeStructured };
    try {
      sessionStorage.setItem("agentception:home", JSON.stringify(payload));
    } catch (error) {
      console.warn("Failed to persist session", error);
    }
  }, [resumeToken, resumeInsights, resumeText, resumeFileName, resumeStructured]);

  const roleDisplay = detectedRole || results?.role || "your role";
  const locationDisplay = results?.city || "your city";
  const totalCompanies = results?.pagination.total || 0;
  const companiesWithJobs = jobCards.length;
  const techStack = resumeInsights?.tech_stack || resumeInsights?.skills_flat || [];

  const evidenceStages = [
    {
      title: "Market demand",
      description: runId ? (isLoading ? "Scanning live roles now" : "Live role scan in progress") : "Choose a role and market",
      badge: runId ? "Live" : "Start",
      state: runId ? "complete" : "active",
      icon: Radar,
    },
    {
      title: "Gap identified",
      description: companiesWithJobs > 0 ? `${companiesWithJobs} matched roles ready to review` : "Unlocks from matched role evidence",
      badge: companiesWithJobs > 0 ? "Ready" : "Next",
      state: companiesWithJobs > 0 ? "complete" : runId ? "active" : "locked",
      icon: Target,
    },
    {
      title: "Learning path",
      description: "Turn a gap into resources and a project sequence",
      badge: "Roadmap",
      state: companiesWithJobs > 0 ? "active" : "locked",
      icon: Map,
    },
    {
      title: "Evidence",
      description: "Build a scoped output you can show in applications",
      badge: "Build",
      state: "locked",
      icon: FileCheck2,
    },
    {
      title: "Next move",
      description: "Tailor, apply, log the result, and improve",
      badge: "Loop",
      state: "locked",
      icon: CircleCheck,
    },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <TopNav />
      <main className="app-main">
        <section className="app-hero">
          <div className="app-hero-copy">
            <span className="inline-status">Career evidence workspace</span>
            <h1 className="app-hero-title">Your next role<br /><span>has a blueprint.</span></h1>
            <p className="app-hero-summary">
              Search live roles, compare them with your resume evidence, and turn the most important gap into a focused learning and application plan.
            </p>
          </div>
          <aside className="app-pulse" aria-label="Current career workspace status">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="section-label">Workspace pulse</p>
                <h2 className="mt-2 text-lg font-extrabold tracking-[-0.035em]">Your current signal</h2>
              </div>
              <span className="mt-1 h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_0_5px_hsl(var(--accent)/0.12)]" />
            </div>
            <dl className="app-pulse-grid">
              <div><dt>Resume</dt><dd>{resumeToken ? "Ready" : "Optional"}</dd></div>
              <div><dt>Search</dt><dd>{runId ? (isLoading ? "Scanning" : "Active") : "Ready"}</dd></div>
              <div><dt>Matches</dt><dd>{companiesWithJobs || "—"}</dd></div>
            </dl>
            <p className="mt-4 text-xs leading-5 text-muted-foreground">Every completed stage sharpens the next move.</p>
          </aside>
        </section>

        <div className="workspace-grid">
          <div className="space-y-5">
            <section className="workspace-panel overflow-hidden">
              <div className="workspace-panel-head">
                <div>
                  <p className="section-label">Start with market demand</p>
                  <h2 className="mt-2 text-xl font-extrabold tracking-[-0.04em] sm:text-2xl">Find roles worth your time.</h2>
                </div>
                <p className="max-w-sm text-xs leading-5 text-muted-foreground sm:text-right">Resume evidence improves ranking, but you can search without it.</p>
              </div>
              <div className="workspace-panel-body">
                <SearchForm onSearchStart={handleSearchStart} onResumeUploaded={handleResumeUploaded} />
              </div>
            </section>

            {runId && (
              <section className="workspace-panel overflow-hidden">
                <div className="workspace-panel-head flex-row items-center">
                  <div><p className="section-label">Live timeline</p><h2 className="mt-2 text-lg font-extrabold tracking-[-0.03em]">Research in motion</h2></div>
                  <Button variant="ghost" size="sm" className="shrink-0 gap-1.5 rounded-lg text-xs" onClick={() => setShowTimeline((value) => !value)}>
                    {showTimeline ? "Hide" : "Show"}<ChevronDown className={`h-4 w-4 transition-transform ${showTimeline ? "" : "-rotate-90"}`} />
                  </Button>
                </div>
                <div className={`${showTimeline ? "block" : "hidden"} p-4 sm:p-6`}>
                  <Timeline runId={runId} onComplete={handleTimelineComplete} />
                </div>
              </section>
            )}

            {(jobCards.length > 0 || isLoading) && (
              <section className="pt-2">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="section-label">Role evidence</p>
                    <h2 className="mt-2 text-xl font-extrabold tracking-[-0.04em] sm:text-2xl">Matched roles</h2>
                    <p className="mt-1.5 text-xs leading-5 text-muted-foreground sm:text-sm">
                      {companiesWithJobs > 0 && <>Showing {companiesWithJobs} of {totalCompanies || companiesWithJobs} roles for {roleDisplay} in {locationDisplay}{resumeToken && <span> matched to your resume</span>}</>}
                    </p>
                  </div>
                  {hasMore && <Button variant="outline" onClick={handleLoadMore} disabled={isLoading} className="w-full rounded-lg text-xs sm:w-auto">{isLoading ? "Loading..." : "Load more"}</Button>}
                </div>

                {resumeToken && (
                  <div className="mb-4 flex flex-col gap-2 rounded-xl border border-accent/25 bg-accent/10 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-2 text-sm font-semibold"><CircleCheck className="h-4 w-4 text-accent" /> Results ranked against your resume evidence.</div>
                    <span className="text-xs font-medium text-muted-foreground">{resumeInsights?.role || "Resume ready"}</span>
                  </div>
                )}

                {isLoading && jobCards.length === 0 ? (
                  <div className="grid gap-4">{[1, 2, 3].map((item) => <div key={item} className="card-clean animate-pulse p-6"><div className="mb-3 h-6 w-3/4 rounded bg-muted" /><div className="h-4 w-1/2 rounded bg-muted" /></div>)}</div>
                ) : (
                  <div className="grid gap-4">{jobCards.map((job, index) => <JobCard key={index} {...job} resumeToken={resumeToken} runId={runId} />)}</div>
                )}
              </section>
            )}

            <section className="workspace-panel p-5 sm:p-6">
              <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.1em] text-accent"><Sparkles className="h-3.5 w-3.5" /> Application move</div>
                  <h3 className="text-lg font-extrabold tracking-[-0.03em]">Turn a saved role into a tailored application package.</h3>
                  <p className="max-w-xl text-sm leading-6 text-muted-foreground">Generate ATS keywords, focused bullets, and a resume version that matches the job you are applying to.</p>
                </div>
                <Link to="/tailor-resume" className="w-full sm:w-auto"><Button className="w-full gap-2 rounded-lg text-xs sm:w-auto">Tailor my resume <ArrowUpRight className="h-4 w-4" /></Button></Link>
              </div>
            </section>
          </div>

          <aside className="space-y-5 xl:sticky xl:top-8">
            <section className="evidence-ledger" aria-label="Career evidence ledger">
              <div className="evidence-ledger-head">
                <div><p className="section-label">Career evidence ledger</p><h2 className="mt-1.5 text-base font-extrabold tracking-[-0.03em]">One connected loop</h2></div>
                <span className="flex items-center gap-1.5 text-[10px] font-bold text-accent"><span className="h-1.5 w-1.5 rounded-full bg-accent" /> Live</span>
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
                <Link to="/learning-paths" className="flex items-center justify-between rounded-lg bg-secondary/60 px-3 py-2.5 text-xs font-bold hover:bg-secondary">Open roadmap <Map className="h-3.5 w-3.5" /></Link>
                <Link to="/applications" className="flex items-center justify-between rounded-lg bg-secondary/60 px-3 py-2.5 text-xs font-bold hover:bg-secondary">Log outcome <ArrowUpRight className="h-3.5 w-3.5" /></Link>
              </div>
            </section>

            {resumeText && (
              <ResumeViewer
                text={resumeText}
                structured={resumeStructured || undefined}
                fileName={resumeFileName || undefined}
                insights={resumeInsights}
                onClose={() => {
                  setResumeText(null);
                  setResumeToken(null);
                  setResumeInsights(null);
                  setResumeFileName(null);
                  setResumeStructured(null);
                }}
              />
            )}

            {techStack.length > 0 && (
              <section className="workspace-panel p-5">
                <div className="flex items-center justify-between gap-3">
                  <div><p className="section-label">Resume evidence</p><h2 className="mt-1.5 text-base font-extrabold tracking-[-0.03em]">Your stack</h2></div>
                  <BookOpen className="h-5 w-5 text-accent" />
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">Detected from your resume. Tap any skill to find study material.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {techStack.slice(0, 12).map((skill) => (
                    <button key={skill} onClick={() => openStudy(skill, { role: resumeInsights?.role || detectedRole || undefined })}>
                      <Badge variant="outline" className="cursor-pointer rounded-full bg-background text-[11px] font-medium hover:border-accent/60 hover:text-accent">{skill}</Badge>
                    </button>
                  ))}
                </div>
              </section>
            )}

            <section className="workspace-panel p-5">
              <p className="section-label">Next destinations</p>
              <nav className="mt-3 divide-y divide-border">
                {[
                  ["Study resources", "/resources"],
                  ["Generate a roadmap", "/learning-paths"],
                  ["Analyze skill gaps", "/skill-gaps"],
                  ["Track applications", "/applications"],
                ].map(([label, href]) => (
                  <Link key={href} to={href} className="flex items-center justify-between py-3 text-sm font-semibold transition-colors hover:text-accent">{label}<ArrowUpRight className="h-4 w-4" /></Link>
                ))}
              </nav>
            </section>
          </aside>
        </div>

        <footer className="mt-8 flex flex-col gap-3 border-t border-border py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>Agentception — market evidence, learning, and outcomes connected.</p>
          <div className="flex flex-wrap gap-4"><Link to="/resources" className="hover:text-foreground">Study</Link><Link to="/learning-paths" className="hover:text-foreground">Roadmap</Link><Link to="/applications" className="hover:text-foreground">Applications</Link></div>
        </footer>
      </main>
      {studyDrawer}
    </div>
  );
};

export default Index;
