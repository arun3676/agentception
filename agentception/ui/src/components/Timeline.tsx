import { useEffect, useRef, useState } from "react";
import { AlertCircle, Check, ChevronDown, Circle, Loader2, Search } from "lucide-react";
import { createTimelineStream, type TimelineEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TimelineProps {
  runId: string | null;
  onComplete?: (completedRunId: string) => void;
  onFailed?: (failedRunId: string) => void;
}

interface TimelineStep {
  id: string;
  icon: "search" | "review" | "complete" | "error";
  message: string;
  status: "completed" | "active" | "failed";
}

type TimelinePresentation = Pick<TimelineStep, "icon" | "message">;

const SAFE_STAGE_LABELS: Record<string, TimelinePresentation> = {
  queued: { message: "Search queued.", icon: "search" },
  searching: { message: "Checking listing sources.", icon: "search" },
  discovery: { message: "Checking additional listing sources.", icon: "search" },
  enrichment: { message: "Reviewing returned listing details.", icon: "review" },
  finalizing: { message: "Preparing returned listings.", icon: "review" },
  succeeded: { message: "Search processing succeeded.", icon: "complete" },
  failed: { message: "Search processing failed.", icon: "error" },
};

/**
 * Convert persisted server events into a small, non-sensitive stage vocabulary.
 * Counts, ranks, match claims, identifiers, URLs, and arbitrary provider text
 * are never echoed into the page.
 */
export function presentTimelineEvent(event: TimelineEvent): TimelinePresentation {
  if (event.level?.toLowerCase() === "error") return SAFE_STAGE_LABELS.failed;

  const explicitStage = (event.stage || event.type || "").toLowerCase().replace(/[^a-z_]/g, "");
  if (SAFE_STAGE_LABELS[explicitStage]) return SAFE_STAGE_LABELS[explicitStage];

  const message = (event.message || "").toLowerCase();
  if (/search complete|finished|\bdone\b/.test(message)) return SAFE_STAGE_LABELS.succeeded;
  if (/search failed|timeline update failed|\berror\b/.test(message)) return SAFE_STAGE_LABELS.failed;
  if (/enrich|job information|job description|full job/.test(message)) return SAFE_STAGE_LABELS.enrichment;
  if (/rank|filter|deduplic|merg|built|caching/.test(message)) return SAFE_STAGE_LABELS.finalizing;
  if (/phase 1|discover|candidate|additional role/.test(message)) return SAFE_STAGE_LABELS.discovery;
  if (/starting|phase 0|direct search|searching/.test(message)) return SAFE_STAGE_LABELS.searching;
  return { message: "Search update received.", icon: "review" };
}

const IconMap = {
  search: Search,
  review: Circle,
  complete: Check,
  error: AlertCircle,
};

export const Timeline = ({ runId, onComplete, onFailed }: TimelineProps) => {
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [terminalStatus, setTerminalStatus] = useState<"running" | "succeeded" | "failed">("running");
  const [showAll, setShowAll] = useState(false);
  const seenMessages = useRef(new Set<string>());

  useEffect(() => {
    setSteps([]);
    setTerminalStatus("running");
    setShowAll(false);
    seenMessages.current.clear();

    if (!runId) return;

    const eventSource = createTimelineStream(
      runId,
      (event) => {
        const presentation = presentTimelineEvent(event);
        if (seenMessages.current.has(presentation.message)) return;
        seenMessages.current.add(presentation.message);

        setSteps((previous) => [
          ...previous.map((step) => step.status === "active" ? { ...step, status: "completed" as const } : step),
          {
            id: `${runId}-${previous.length}`,
            ...presentation,
            status: presentation.icon === "error" ? "failed" : "active",
          },
        ]);
      },
      () => {
        setSteps((previous) => previous.map((step) => ({ ...step, status: "completed" as const })));
        setTerminalStatus("succeeded");
        onComplete?.(runId);
      },
      () => {
        setSteps((previous) => previous.map((step) => step.status === "active"
          ? { ...step, status: "failed" as const }
          : step));
        setTerminalStatus("failed");
        onFailed?.(runId);
      },
    );

    return () => eventSource.close();
  }, [runId, onComplete, onFailed]);

  if (!runId) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />
        <span>Ready to search</span>
      </div>
    );
  }

  const visibleSteps = showAll ? steps : steps.slice(-4);
  const hiddenCount = steps.length - visibleSteps.length;

  return (
    <div className="py-2" aria-live="polite">
      {hiddenCount > 0 && !showAll && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mb-3 flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
          <span>{hiddenCount} previous updates</span>
        </button>
      )}

      {visibleSteps.length === 0 && terminalStatus === "running" && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Waiting for the first search update…
        </div>
      )}

      <div className="space-y-3">
        {visibleSteps.map((step) => {
          const Icon = IconMap[step.icon];
          return (
            <div key={step.id} className="flex items-start gap-3">
              <div className={cn(
                "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                step.status === "active" && "bg-foreground",
                step.status === "completed" && "bg-muted",
                step.status === "failed" && "bg-destructive/10 text-destructive",
              )}>
                {step.status === "active" ? (
                  <Loader2 className="h-3 w-3 animate-spin text-background" aria-hidden="true" />
                ) : (
                  <Icon className="h-3 w-3" aria-hidden="true" />
                )}
              </div>
              <span className={cn(
                "pt-0.5 text-sm",
                step.status === "active" ? "font-medium text-foreground" : "text-muted-foreground",
                step.status === "failed" && "text-destructive",
              )}>
                {step.message}
              </span>
            </div>
          );
        })}
      </div>

      {terminalStatus === "succeeded" && (
        <div className="mt-4 flex items-center gap-2 border-t border-border pt-3" role="status">
          <Check className="h-4 w-4 text-green-600" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">Search succeeded. Retrieving returned listings.</span>
        </div>
      )}
      {terminalStatus === "failed" && (
        <p role="alert" className="mt-4 border-t border-border pt-3 text-sm text-destructive">
          Search ended without a successful terminal event. No results or completion were assumed.
        </p>
      )}
    </div>
  );
};
