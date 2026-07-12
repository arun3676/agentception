import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useStudyDrawer } from "@/hooks/use-study-drawer";
import { listPillars, fetchResources, type Pillar, type AIResource } from "@/lib/api";
import { ArrowUpRight, Search, Sparkles } from "lucide-react";

/** Study — search any topic or browse the 12 career pillars. Both routes open
 * the same drawer of curated videos, articles, courses and docs. */
const Study = () => {
  const [query, setQuery] = useState("");
  const [pillars, setPillars] = useState<Pillar[]>([]);
  const [tools, setTools] = useState<AIResource[]>([]);
  const { openStudy, studyDrawer } = useStudyDrawer();

  useEffect(() => {
    listPillars()
      .then((data) => setPillars(data.pillars))
      .catch(() => setPillars([]));
    fetchResources({ featured: true, limit: 6 })
      .then((data) => setTools(data.items))
      .catch(() => setTools([]));
  }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    openStudy(query);
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="card-clean mb-8 p-8">
          <p className="eyebrow mb-3">Study</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Learn exactly what the <span className="text-muted-foreground">job asks for.</span>
          </h1>
          <p className="mt-4 max-w-3xl text-base text-muted-foreground">
            Search any skill and get the best videos, articles, courses and docs for it — curated per role and
            experience level, not generic search results.
          </p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search a skill (e.g., LangGraph, RAG, vector databases, Kubernetes)"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-11 rounded-lg pl-11 text-sm"
              />
            </div>
            <Button type="submit" disabled={!query.trim()} className="h-11 rounded-lg text-sm">
              Find material
            </Button>
          </form>
        </div>

        {/* Career pillars */}
        <section className="mb-10">
          <h2 className="mb-1 text-lg font-semibold">Browse by career track</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Twelve pillars, each with hand-picked channels and sites per level.
          </p>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {pillars.map((pillar) => (
              <button
                key={pillar.key}
                onClick={() => openStudy(pillar.label, { role: pillar.label })}
                className="card-clean group p-5 text-left transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-md"
              >
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-secondary transition-colors group-hover:bg-accent/10">
                  <Sparkles className="h-4 w-4" />
                </div>
                <h3 className="text-base font-semibold leading-6">{pillar.label}</h3>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {pillar.keywords.slice(0, 4).map((kw) => (
                    <Badge key={kw} variant="outline" className="text-[11px] font-normal">
                      {kw}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Featured tools from the resource library */}
        {tools.length > 0 && (
          <section>
            <h2 className="mb-1 text-lg font-semibold">Tools worth knowing</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Frameworks and platforms that show up across job descriptions.
            </p>

            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {tools.map((resource) => (
                <div key={resource.id} className="card-clean overflow-hidden p-5">
                  <h3 className="text-base font-semibold leading-6">{resource.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{resource.category || "resource"}</p>
                  <p className="mt-3 line-clamp-3 text-sm text-muted-foreground">{resource.description}</p>
                  <div className="flex flex-col gap-3 pt-4 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <a
                      href={resource.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 font-medium hover:underline"
                    >
                      Visit
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </a>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-lg text-xs"
                      onClick={() => openStudy(resource.title)}
                    >
                      Study this
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      {studyDrawer}
    </div>
  );
};

export default Study;
