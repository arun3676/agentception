import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { listPillars, fetchResources, type Pillar, type AIResource } from "@/lib/api";
import { toSafeExternalUrl } from "@/lib/safeUrl";
import { ArrowUpRight, Search } from "lucide-react";

const Resources = () => {
  const [query, setQuery] = useState("");
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [resources, setResources] = useState<AIResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadResources = async (q?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchResources(q ? { q, limit: 18 } : { featured: true, limit: 18 });
      setResources(data.items);
    } catch {
      setResources([]);
      setError("The resource catalogue is unavailable right now. Try again later.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadResources();
    listPillars()
      .then((data) => setPillars(data.pillars))
      .catch(() => setPillars([]));
  }, []);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void loadResources(query.trim());
  };

  const choosePillar = (pillar: Pillar) => {
    setQuery(pillar.label);
    void loadResources(pillar.label);
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <section className="card-clean mb-8 p-6 sm:p-8">
          <p className="eyebrow mb-3">Resource catalogue</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Browse learning references by <span className="text-muted-foreground">topic or career track.</span>
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-muted-foreground">
            These links come from the maintained catalogue. Inclusion is not an endorsement, ranking, or guarantee of
            current accuracy; review each source and its publication date before relying on it.
          </p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <label htmlFor="resource-search" className="sr-only">Search the resource catalogue</label>
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input
                id="resource-search"
                placeholder="Search a topic, such as Kubernetes or system design"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-11 rounded-lg pl-11 text-sm"
              />
            </div>
            <Button type="submit" disabled={loading} className="h-11 rounded-lg text-sm">
              {loading ? "Loading…" : "Search catalogue"}
            </Button>
          </form>
        </section>

        {pillars.length > 0 && (
          <section className="mb-10" aria-labelledby="career-tracks-heading">
            <h2 id="career-tracks-heading" className="mb-1 text-lg font-semibold">Browse by career track</h2>
            <p className="mb-4 text-sm text-muted-foreground">Track labels narrow the same catalogue; they do not create a personal learning plan.</p>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {pillars.map((pillar) => (
                <button
                  key={pillar.key}
                  type="button"
                  onClick={() => choosePillar(pillar)}
                  className="card-clean p-5 text-left transition-colors hover:border-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <h3 className="text-base font-semibold leading-6">{pillar.label}</h3>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {pillar.keywords.slice(0, 4).map((keyword) => (
                      <Badge key={keyword} variant="outline" className="text-[11px] font-normal">{keyword}</Badge>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}

        <section aria-labelledby="resources-heading" aria-live="polite">
          <h2 id="resources-heading" className="mb-1 text-lg font-semibold">Catalogue results</h2>
          <p className="mb-4 text-sm text-muted-foreground">Open a source to evaluate its author, date, scope, and relevance.</p>

          {error && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</p>}
          {!loading && !error && resources.length === 0 && (
            <p className="rounded-lg border border-border p-6 text-sm text-muted-foreground">No catalogue entries matched this topic.</p>
          )}
          {loading && <p role="status" className="rounded-lg border border-border p-6 text-sm text-muted-foreground">Loading catalogue entries…</p>}

          {!loading && resources.length > 0 && (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {resources.map((resource) => {
                const safeUrl = toSafeExternalUrl(resource.url);
                return (
                  <article key={resource.id} className="card-clean overflow-hidden p-5">
                    <h3 className="text-base font-semibold leading-6">{resource.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{resource.category || "Resource"}</p>
                    {resource.description && <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted-foreground">{resource.description}</p>}
                    {safeUrl ? (
                      <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium hover:underline">
                        Open source <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    ) : (
                      <p className="mt-4 text-xs text-muted-foreground">Source URL unavailable.</p>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default Resources;
