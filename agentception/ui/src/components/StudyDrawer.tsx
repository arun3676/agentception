import { useEffect, useRef, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BookOpen,
  ExternalLink,
  FileText,
  GraduationCap,
  MessagesSquare,
  PlayCircle,
  Sparkles,
  Star,
} from "lucide-react";
import {
  searchStudyMaterials,
  getInterviewPrep,
  type StudyResults,
  type StudyItem,
  type InterviewPrep,
} from "@/lib/api";

export interface StudyDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The skill or topic to study, e.g. "LangChain" */
  topic: string;
  /** Job title providing context, e.g. "AI Engineer" — scopes results to the role */
  role?: string;
  /** Company name — enables the Interview tab */
  company?: string;
  level?: "beginner" | "intermediate" | "advanced";
}

const LEVELS = ["beginner", "intermediate", "advanced"] as const;

const hostnameOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};

const ResourceRow = ({ item }: { item: StudyItem }) => (
  <a
    href={item.url}
    target="_blank"
    rel="noopener noreferrer"
    className="group block rounded-lg border border-border p-3 transition-colors hover:border-accent/50 hover:bg-secondary/50"
  >
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{item.title}</p>
        {item.snippet && (
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.snippet}</p>
        )}
        <p className="mt-1.5 truncate text-[11px] text-muted-foreground/70">{hostnameOf(item.url)}</p>
      </div>
      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </div>
  </a>
);

const VideoCard = ({ item }: { item: StudyItem }) => (
  <a
    href={item.url}
    target="_blank"
    rel="noopener noreferrer"
    className="group overflow-hidden rounded-lg border border-border transition-colors hover:border-accent/50"
  >
    <div className="relative aspect-video overflow-hidden bg-secondary">
      {item.thumbnail && (
        <img
          src={item.thumbnail}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition-transform group-hover:scale-105"
        />
      )}
      <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100">
        <PlayCircle className="h-10 w-10 text-white drop-shadow" />
      </div>
    </div>
    {/* Padding lives on the wrapper: it breaks -webkit-box clamping if applied to the <p> */}
    <div className="p-2.5">
      <p className="line-clamp-2 text-xs font-medium leading-5 text-foreground">{item.title}</p>
    </div>
  </a>
);

const EmptyState = ({ label }: { label: string }) => (
  <p className="py-10 text-center text-sm text-muted-foreground">No {label} found for this topic.</p>
);

const LoadingGrid = () => (
  <div className="space-y-3">
    {[0, 1, 2].map((i) => (
      <Skeleton key={i} className="h-20 w-full rounded-lg" />
    ))}
  </div>
);

/** The four content buckets the backend returns, in display order. */
const CONTENT_TABS = [
  { key: "videos", label: "Videos", Icon: PlayCircle },
  { key: "articles", label: "Articles", Icon: FileText },
  { key: "courses", label: "Courses", Icon: GraduationCap },
  { key: "docs", label: "Docs", Icon: BookOpen },
] as const;

type ContentKey = (typeof CONTENT_TABS)[number]["key"];

export const StudyDrawer = ({
  open,
  onOpenChange,
  topic,
  role,
  company,
  level: initialLevel = "intermediate",
}: StudyDrawerProps) => {
  const [level, setLevel] = useState<(typeof LEVELS)[number]>(initialLevel);
  const [data, setData] = useState<StudyResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [prep, setPrep] = useState<InterviewPrep | null>(null);
  const [prepLoading, setPrepLoading] = useState(false);

  // Skip the request when reopening the drawer on the same topic/role/level
  const fetchedKey = useRef<string | null>(null);

  useEffect(() => {
    if (!open || !topic) return;

    const key = `${topic}|${role ?? ""}|${level}`;
    if (fetchedKey.current === key) return;

    let cancelled = false;
    setLoading(true);
    setError(null);
    searchStudyMaterials({ topic, role, level })
      .then((res) => {
        if (cancelled) return;
        setData(res);
        fetchedKey.current = key;
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Could not load study materials");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, topic, role, level]);

  const loadInterviewPrep = () => {
    if (prep || prepLoading || !role) return;
    setPrepLoading(true);
    getInterviewPrep(role, company)
      .then(setPrep)
      .catch(() => setPrep(null))
      .finally(() => setPrepLoading(false));
  };

  const counts = Object.fromEntries(
    CONTENT_TABS.map(({ key }) => [key, data?.[key].length ?? 0]),
  ) as Record<ContentKey, number>;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 sm:max-w-xl">
        <SheetHeader className="space-y-2 pb-4">
          <SheetTitle className="flex items-center gap-2 text-left">
            <Sparkles className="h-4 w-4 shrink-0 text-accent" />
            <span className="truncate">Learn {topic}</span>
          </SheetTitle>
          <SheetDescription className="text-left">
            {role ? (
              <>
                Curated for <span className="font-medium text-foreground">{role}</span> roles
                {data?.pillar && <> · {data.pillar.label} track</>}
              </>
            ) : (
              "Curated learning material"
            )}
          </SheetDescription>

          <div className="flex gap-1.5 pt-1">
            {LEVELS.map((l) => (
              <button
                key={l}
                onClick={() => setLevel(l)}
                className={[
                  "rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors",
                  level === l
                    ? "bg-foreground text-background"
                    : "bg-secondary text-muted-foreground hover:text-foreground",
                ].join(" ")}
              >
                {l}
              </button>
            ))}
          </div>
        </SheetHeader>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Verified picks: hand-curated, always present, zero API cost */}
        {data && data.curated_picks.length > 0 && (
          <div className="mb-4 rounded-lg border border-border bg-secondary/40 p-3">
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Star className="h-3.5 w-3.5" />
              Verified picks
            </p>
            <div className="flex flex-wrap gap-1.5">
              {data.curated_picks.slice(0, 8).map((pick) => (
                <a key={`${pick.kind}-${pick.title}`} href={pick.url} target="_blank" rel="noopener noreferrer">
                  <Badge
                    variant="outline"
                    className="cursor-pointer bg-background text-xs font-normal hover:border-accent/60"
                  >
                    {pick.kind === "youtube_channel" && <PlayCircle className="mr-1 h-3 w-3" />}
                    {pick.kind === "course" && <GraduationCap className="mr-1 h-3 w-3" />}
                    {pick.kind === "site" && <BookOpen className="mr-1 h-3 w-3" />}
                    {pick.title}
                  </Badge>
                </a>
              ))}
            </div>
          </div>
        )}

        <Tabs defaultValue="videos" className="flex min-h-0 flex-1 flex-col">
          <TabsList className="w-full justify-start overflow-x-auto">
            {CONTENT_TABS.map(({ key, label, Icon }) => (
              <TabsTrigger key={key} value={key} className="gap-1.5">
                <Icon className="h-3.5 w-3.5" /> {label}
                {counts[key] > 0 && <span className="text-muted-foreground">{counts[key]}</span>}
              </TabsTrigger>
            ))}
            {role && (
              <TabsTrigger value="interview" className="gap-1.5" onClick={loadInterviewPrep}>
                <MessagesSquare className="h-3.5 w-3.5" /> Interview
              </TabsTrigger>
            )}
          </TabsList>

          <div className="min-h-0 flex-1 overflow-y-auto pt-4">
            <TabsContent value="videos" className="mt-0">
              {loading ? (
                <LoadingGrid />
              ) : counts.videos === 0 ? (
                <EmptyState label="videos" />
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {data!.videos.map((v) => (
                    <VideoCard key={v.url} item={v} />
                  ))}
                </div>
              )}
            </TabsContent>

            {(["articles", "courses", "docs"] as const).map((key) => (
              <TabsContent key={key} value={key} className="mt-0">
                {loading ? (
                  <LoadingGrid />
                ) : counts[key] === 0 ? (
                  <EmptyState label={key} />
                ) : (
                  <div className="space-y-2">
                    {data![key].map((item) => (
                      <ResourceRow key={item.url} item={item} />
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}

            {role && (
              <TabsContent value="interview" className="mt-0">
                {prepLoading ? (
                  <LoadingGrid />
                ) : !prep || prep.sources.length === 0 ? (
                  <EmptyState label="interview guides" />
                ) : (
                  <div className="space-y-2">
                    <p className="pb-1 text-xs text-muted-foreground">
                      What the {company ? `${company} ` : ""}
                      {role} loop actually looks like.
                    </p>
                    {prep.sources.map((s) => (
                      <ResourceRow key={s.url} item={{ title: s.title, url: s.url, snippet: s.snippet }} />
                    ))}
                  </div>
                )}
              </TabsContent>
            )}
          </div>
        </Tabs>

        {data?.cached && (
          <p className="border-t border-border pt-2 text-[11px] text-muted-foreground">
            Served from cache · refreshed weekly
          </p>
        )}
      </SheetContent>
    </Sheet>
  );
};

