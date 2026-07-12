import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createApplication, listApplications, refreshApplicationListings, updateApplicationStatus, type ApplicationRecord } from "@/lib/api";
import { PlusCircle, ExternalLink, Bookmark, RefreshCw } from "lucide-react";
import { useEffect } from "react";

const statusColors: Record<string, string> = {
  applied: "bg-slate-100 text-slate-700",
  screening: "bg-amber-50 text-amber-700",
  interview: "bg-sky-50 text-sky-700",
  offer: "bg-emerald-50 text-emerald-700",
  saved: "bg-slate-100 text-slate-700",
};

const pipelineStages = [
  { key: "applied", label: "Applied", color: "bg-slate-100" },
  { key: "screening", label: "Screening", color: "bg-amber-50" },
  { key: "interview", label: "Interview", color: "bg-sky-50" },
  { key: "offer", label: "Offer", color: "bg-emerald-50" },
];

const Applications = () => {
  const [companyName, setCompanyName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [bookmarked, setBookmarked] = useState<Set<string>>(new Set());
  const [listingChecks, setListingChecks] = useState<Record<string, "open" | "closed" | "unknown">>({});
  const [refreshingListings, setRefreshingListings] = useState(false);

  const loadApplications = async () => {
    setLoading(true);
    try {
      const data = await listApplications();
      setApplications(data.items || []);
    } catch {
      setApplications([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!companyName || !jobTitle || !jobUrl) return;
    await createApplication({
      company_name: companyName,
      job_title: jobTitle,
      job_url: jobUrl,
      application_status: "saved",
    });
    setCompanyName("");
    setJobTitle("");
    setJobUrl("");
    loadApplications();
  };

  const refreshListings = async () => {
    setRefreshingListings(true);
    try {
      const result = await refreshApplicationListings();
      setListingChecks(Object.fromEntries(result.items.map((item) => [item.id, item.status])));
    } finally {
      setRefreshingListings(false);
    }
  };

  const updateStatus = async (applicationId: string, status: string) => {
    const updated = await updateApplicationStatus(applicationId, status);
    setApplications((current) => current.map((application) => application.id === applicationId ? updated : application));
  };

  useEffect(() => {
    loadApplications();
  }, []);

  const statusCount = (statuses: string[]) =>
    applications.filter((application) =>
      statuses.includes((application.application_status || "saved").toLowerCase()),
    ).length;
  const totalApps = applications.length;
  const screening = statusCount(["screening", "phone_screen", "recruiter_screen"]);
  const interviews = statusCount(["interview", "onsite", "technical_interview"]);
  const offers = statusCount(["offer", "accepted"]);
  const callbackCount = screening + interviews + offers;
  const callbackRate = totalApps > 0 ? Math.round((callbackCount / totalApps) * 100) : 0;
  const pipelineData = {
    applied: statusCount(["saved", "applied"]),
    screening,
    interview: interviews,
    offer: offers,
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Applications</h1>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-8">
          <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 w-full justify-start gap-4 sm:gap-8 overflow-x-auto">
            {["overview", "all", "analytics", "insights"].map((tab) => (
              <TabsTrigger
                key={tab}
                value={tab}
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 py-3 text-sm sm:text-base capitalize whitespace-nowrap shrink-0"
              >
                {tab === "all" ? "All" : tab}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* Stats */}
        {(activeTab === "overview" || activeTab === "analytics") && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Applications", value: totalApps },
            { label: "Interviews", value: interviews },
            { label: "Offers", value: offers },
            { label: "Callback Rate", value: `${callbackRate}%` },
          ].map((stat) => (
            <div key={stat.label} className="card-clean p-5 text-center">
              <p className="text-2xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground mt-1">{stat.label}</p>
            </div>
          ))}
        </div>
        )}

        {/* Pipeline */}
        {(activeTab === "overview" || activeTab === "analytics") && (
        <div className="card-clean p-6 mb-8">
          <h3 className="text-base font-semibold mb-5">Application Pipeline</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {pipelineStages.map((stage) => (
              <div key={stage.key} className={`${stage.color} rounded-lg p-5 text-center`}>
                <p className="text-sm text-muted-foreground mb-2">{stage.label}</p>
                <p className="text-2xl font-bold">
                  {pipelineData[stage.key as keyof typeof pipelineData]}
                </p>
              </div>
            ))}
          </div>
        </div>
        )}

        {/* Add Application */}
        {(activeTab === "overview" || activeTab === "all") && (
        <div className="card-clean p-6 mb-8">
          <h3 className="text-base font-semibold mb-4 flex items-center gap-2.5">
            <PlusCircle className="h-5 w-5" />
            Add an application
          </h3>
          <div className="grid gap-4 md:grid-cols-4">
            <Input
              placeholder="Company"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="h-11 rounded-lg text-base"
            />
            <Input
              placeholder="Job title"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="h-11 rounded-lg text-base"
            />
            <Input
              placeholder="Job URL"
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              className="h-11 rounded-lg text-base"
            />
            <Button onClick={handleAdd} size="default" className="h-11 rounded-lg text-sm">
              Save application
            </Button>
          </div>
        </div>
        )}

        {activeTab === "insights" && (
          <div className="grid gap-4 md:grid-cols-3 mb-8">
            {[
              "Attach two proof projects before applying to stretch roles.",
              "Prioritize roles where your resume match is above 70%.",
              "Follow up three business days after recruiter screens.",
            ].map((insight) => (
              <div key={insight} className="card-clean p-5">
                <p className="text-sm text-muted-foreground">{insight}</p>
              </div>
            ))}
          </div>
        )}

        {/* Recent Applications */}
        {(activeTab === "overview" || activeTab === "all") && (
        <div className="card-clean p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-base font-semibold">Application command center</h3>
              <p className="mt-1 text-xs text-muted-foreground">Refresh checks whether the public job post is still live. Update recruiter stages when you hear from them.</p>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" className="text-sm rounded-lg" onClick={refreshListings} disabled={refreshingListings}>
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${refreshingListings ? "animate-spin" : ""}`} />
                {refreshingListings ? "Checking" : "Check roles"}
              </Button>
              <Button variant="ghost" size="sm" className="text-sm rounded-lg" onClick={() => setActiveTab("all")}>View all</Button>
            </div>
          </div>
          <div className="space-y-3">
            {applications.map((app: any, index: number) => {
              const appKey = app.id || `${app.company_name || app.company}-${app.job_title || app.role}`;
              const appUrl = app.job_url || app.url;
              const isBookmarked = bookmarked.has(appKey);
              return (
              <div
                key={app.id || index}
                className="flex items-center justify-between rounded-lg border border-border p-4"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-base font-bold">
                    {app.company_name?.[0] || app.company?.[0] || "?"}
                  </div>
                  <div>
                    <p className="text-base font-medium">{app.company_name || app.company}</p>
                    <p className="text-sm text-muted-foreground">{app.job_title || app.role}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${
                      statusColors[app.application_status || app.status] || statusColors.saved
                    }`}
                  >
                    {app.application_status || app.status}
                  </span>
                  {app.id && listingChecks[app.id] && (
                    <span className={`hidden rounded-full px-2 py-1 text-xs font-medium sm:inline ${listingChecks[app.id] === "open" ? "bg-emerald-50 text-emerald-700" : listingChecks[app.id] === "closed" ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600"}`}>
                      {listingChecks[app.id] === "open" ? "Posting live" : listingChecks[app.id] === "closed" ? "Posting closed" : "Couldn’t verify"}
                    </span>
                  )}
                  {app.id && (
                    <select
                      aria-label={`Update ${app.company_name || app.company} application stage`}
                      value={app.application_status || app.status || "saved"}
                      onChange={(event) => updateStatus(app.id, event.target.value)}
                      className="h-8 rounded-md border border-border bg-background px-2 text-xs font-medium"
                    >
                      <option value="saved">Saved</option><option value="applied">Applied</option><option value="screening">Screening</option><option value="phone_screen">Phone screen</option><option value="interview">Interview</option><option value="onsite">Onsite</option><option value="offer">Offer</option><option value="rejected">Rejected</option><option value="ghosted">Ghosted</option>
                    </select>
                  )}
                  <span className="text-xs text-muted-foreground hidden sm:inline">
                    {app.date || ""}
                  </span>
                  {appUrl && (
                    <Button asChild variant="ghost" size="icon" className="h-8 w-8 rounded-lg" title="Open job">
                      <a href={appUrl} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-lg"
                    title={isBookmarked ? "Remove bookmark" : "Bookmark application"}
                    onClick={() =>
                      setBookmarked((current) => {
                        const next = new Set(current);
                        if (next.has(appKey)) next.delete(appKey);
                        else next.add(appKey);
                        return next;
                      })
                    }
                  >
                    <Bookmark className={`h-4 w-4 ${isBookmarked ? "fill-current" : ""}`} />
                  </Button>
                </div>
              </div>
            )})}
            {!loading && applications.length === 0 && (
              <div className="rounded-lg border border-dashed border-border p-8 text-center">
                <p className="text-sm font-medium">No applications tracked yet.</p>
                <p className="mt-1 text-sm text-muted-foreground">Add a role above to start measuring your pipeline.</p>
              </div>
            )}
          </div>
        </div>
        )}
      </main>
    </div>
  );
};

export default Applications;
