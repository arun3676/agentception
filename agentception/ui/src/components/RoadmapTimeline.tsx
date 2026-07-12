import { useEffect, useMemo, useState } from "react";
import { BookOpen, Check, Clock, ExternalLink, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { LearningPath } from "@/lib/api";

/**
 * Visual roadmap: a progress meter, three stat tiles, and a connected milestone
 * timeline. Completion is tracked client-side (localStorage) so the meter and the
 * "% complete" tile reflect real user progress rather than a fabricated number.
 *
 * Color: one accent hue for done/active vs muted for pending — a magnitude/state
 * encoding of a single series, so no categorical palette is involved.
 */

type Milestone = LearningPath["milestones"][number];

const storageKey = (pathId: string) => `agentception:roadmap:${pathId}`;

function useCompletion(pathId: string, count: number) {
  const [done, setDone] = useState<Set<number>>(new Set());

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey(pathId));
      setDone(raw ? new Set(JSON.parse(raw)) : new Set());
    } catch {
      setDone(new Set());
    }
  }, [pathId]);

  const toggle = (index: number) => {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      try {
        localStorage.setItem(storageKey(pathId), JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  // The first not-yet-done milestone is "up next"
  const activeIndex = useMemo(() => {
    for (let i = 0; i < count; i++) if (!done.has(i)) return i;
    return count; // all done
  }, [done, count]);

  return { done, toggle, activeIndex };
}

const StatTile = ({ value, label }: { value: string; label: string }) => (
  <div className="rounded-xl border border-border bg-card p-4">
    <p className="text-2xl font-bold tracking-tight tabular-nums">{value}</p>
    <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
  </div>
);

/** Segmented journey meter — one segment per milestone, width proportional to its
 * hours, filled when complete. 2px gaps keep adjacent fills visually separate. */
const JourneyMeter = ({
  milestones,
  done,
  activeIndex,
}: {
  milestones: Milestone[];
  done: Set<number>;
  activeIndex: number;
}) => {
  const totalHours = milestones.reduce((sum, m) => sum + (m.estimated_hours || 1), 0) || 1;
  return (
    <div className="flex gap-0.5" role="img" aria-label="Roadmap progress by milestone">
      {milestones.map((m, i) => {
        const pct = ((m.estimated_hours || 1) / totalHours) * 100;
        const state = done.has(i) ? "done" : i === activeIndex ? "active" : "pending";
        return (
          <div
            key={m.title}
            title={`${m.title} · ${m.estimated_hours}h`}
            style={{ width: `${pct}%` }}
            className={[
              "h-2.5 rounded-full transition-colors first:rounded-l-full last:rounded-r-full",
              state === "done" && "bg-accent",
              state === "active" && "bg-accent/40",
              state === "pending" && "bg-secondary",
            ]
              .filter(Boolean)
              .join(" ")}
          />
        );
      })}
    </div>
  );
};

export const RoadmapTimeline = ({ path }: { path: LearningPath }) => {
  const milestones = path.milestones || [];
  const { done, toggle, activeIndex } = useCompletion(path.id, milestones.length);

  const completedHours = milestones.reduce(
    (sum, m, i) => (done.has(i) ? sum + (m.estimated_hours || 0) : sum),
    0,
  );
  const pctComplete = milestones.length
    ? Math.round((done.size / milestones.length) * 100)
    : 0;

  return (
    <div className="space-y-8">
      {/* Header + meter */}
      <div className="card-clean p-6">
        <p className="eyebrow mb-2">Your roadmap</p>
        <h2 className="text-2xl font-bold tracking-tight">{path.title}</h2>
        {path.description && (
          <p className="mt-1 text-base text-muted-foreground">{path.description}</p>
        )}

        <div className="mt-5 grid grid-cols-3 gap-3">
          <StatTile value={`${pctComplete}%`} label="complete" />
          <StatTile value={`${done.size}/${milestones.length}`} label="milestones" />
          <StatTile value={`${completedHours}/${path.total_hours}h`} label="hours done" />
        </div>

        <div className="mt-5">
          <JourneyMeter milestones={milestones} done={done} activeIndex={activeIndex} />
          <p className="mt-2 text-xs text-muted-foreground">
            {activeIndex >= milestones.length
              ? "Roadmap complete — every milestone is done."
              : `Up next: ${milestones[activeIndex]?.title}`}
          </p>
        </div>
      </div>

      {/* Connected timeline */}
      <ol className="relative space-y-4">
        {/* the vertical track behind the nodes */}
        <span
          aria-hidden
          className="absolute left-5 top-3 bottom-3 w-px bg-border"
        />
        {milestones.map((milestone, index) => {
          const isDone = done.has(index);
          const isActive = index === activeIndex;
          return (
            <li key={milestone.title} className="relative pl-14">
              {/* node */}
              <button
                onClick={() => toggle(index)}
                aria-label={isDone ? "Mark milestone incomplete" : "Mark milestone complete"}
                className={[
                  "absolute left-0 top-1 z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                  isDone
                    ? "border-accent bg-accent text-accent-foreground"
                    : isActive
                      ? "border-accent bg-background text-accent"
                      : "border-border bg-background text-muted-foreground hover:border-accent/60",
                ].join(" ")}
              >
                {isDone ? <Check className="h-5 w-5" /> : <span className="text-sm font-semibold">{index + 1}</span>}
              </button>

              <div
                className={[
                  "card-clean p-5 transition-colors",
                  isActive && "border-accent/40 ring-1 ring-accent/20",
                  isDone && "opacity-75",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className={`text-base font-semibold ${isDone ? "line-through decoration-muted-foreground/40" : ""}`}>
                      {milestone.title}
                    </h3>
                    <p className="mt-1 text-sm text-muted-foreground">{milestone.description}</p>
                  </div>
                  <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    {milestone.estimated_hours}h
                  </span>
                </div>

                {milestone.skills_gained && milestone.skills_gained.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {milestone.skills_gained.map((skill) => (
                      <span
                        key={skill}
                        className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )}

                {milestone.resources && milestone.resources.length > 0 && (
                  <div className="mt-4">
                    <p className="mb-2 flex items-center gap-2 text-sm font-medium">
                      <BookOpen className="h-4 w-4" />
                      Resources
                    </p>
                    <ul className="space-y-1.5">
                      {milestone.resources.map((resource) => (
                        <li key={resource.url}>
                          <a
                            href={resource.url}
                            target="_blank"
                            rel="noreferrer"
                            className="group flex items-start gap-2 text-sm text-foreground/90 hover:text-accent"
                          >
                            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                            <span className="break-words">{resource.title}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <Button
                  variant={isDone ? "outline" : "default"}
                  size="sm"
                  onClick={() => toggle(index)}
                  className="mt-4 gap-1.5 rounded-lg text-xs"
                >
                  {isDone ? (
                    <>
                      <Circle className="h-3.5 w-3.5" />
                      Mark as not done
                    </>
                  ) : (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      Mark complete
                    </>
                  )}
                </Button>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
};
