import { useEffect, useState, useRef } from "react";
import { Check, Loader2, Search, Filter, Brain, Sparkles, ChevronDown } from "lucide-react";
import { TimelineEvent, createTimelineStream } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TimelineProps {
  runId: string | null;
  onComplete?: () => void;
}

interface TimelineStep {
  id: string;
  icon: "search" | "filter" | "brain" | "complete";
  message: string;
  status: "completed" | "active" | "pending";
}

let _stepIdCounter = 0;
function nextStepId(): string {
  _stepIdCounter += 1;
  return `step-${_stepIdCounter}-${Date.now()}`;
}

// Map technical logs to user-friendly messages
const humanizeMessage = (raw: string): { message: string; icon: TimelineStep["icon"] } | null => {
  const lower = raw.toLowerCase();
  
  // Skip noise
  if (lower.includes("run_id=") || lower.includes("caching under")) return null;
  if (lower.includes("discovered 0") || lower.includes("re-ranking 0")) return null;
  if (lower.includes("skipping")) return null;
  if (lower === "system:" || !raw.trim()) return null;

  // Phase mappings
  if (lower.includes("starting rag") || lower.includes("phase 0: direct")) {
    const roleMatch = raw.match(/role=([^,]+)/);
    const locMatch = raw.match(/location=([^,]+)/);
    const role = roleMatch ? roleMatch[1] : "jobs";
    const loc = locMatch ? locMatch[1] : "";
    return { 
      message: `Searching for ${role}${loc ? ` in ${loc}` : ""}...`, 
      icon: "search" 
    };
  }
  
  if (lower.includes("direct search found") || lower.includes("found") && lower.includes("results")) {
    const countMatch = raw.match(/(\d+)\s*(local|results|remote)/i);
    const count = countMatch ? countMatch[1] : "several";
    return { message: `Found ${count} potential matches`, icon: "search" };
  }

  if (lower.includes("computing rank") || lower.includes("re-ranking") || lower.includes("filtering")) {
    return { message: "Analyzing and ranking results...", icon: "filter" };
  }

  if (lower.includes("ranked") && lower.includes("companies")) {
    const countMatch = raw.match(/ranked\s*(\d+)/i);
    const count = countMatch ? countMatch[1] : "";
    return { message: `Ranked ${count} companies by relevance`, icon: "brain" };
  }

  if (lower.includes("built") && lower.includes("hiring")) {
    const countMatch = raw.match(/built\s*(\d+)/i);
    const count = countMatch ? countMatch[1] : "";
    return { message: `${count} opportunities ready`, icon: "complete" };
  }

  if (lower.includes("complete") || lower.includes("done") || lower.includes("finished")) {
    return { message: "Search complete", icon: "complete" };
  }

  if (lower.includes("merged") || lower.includes("enriched")) {
    return { message: "Enriching company data...", icon: "brain" };
  }

  // Generic fallback - clean up the message
  const cleaned = raw
    .replace(/^(RAG|System|Writer):\s*/i, "")
    .replace(/phase\s*\d+(\.\d+)?:\s*/i, "")
    .replace(/^[^\w\s:,-]+/u, "")
    .trim();
  
  if (cleaned.length < 5) return null;
  return { message: cleaned, icon: "search" };
};

const IconMap = {
  search: Search,
  filter: Filter,
  brain: Brain,
  complete: Sparkles,
};

export const Timeline = ({ runId, onComplete }: TimelineProps) => {
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const seenMessages = useRef(new Set<string>());

  useEffect(() => {
    if (!runId) {
      setSteps([]);
      setIsComplete(false);
      seenMessages.current.clear();
      return;
    }

    const eventSource = createTimelineStream(
      runId,
      (event: TimelineEvent) => {
        const result = humanizeMessage(event.message || "");
        if (!result) return;
        
        // Deduplicate
        if (seenMessages.current.has(result.message)) return;
        seenMessages.current.add(result.message);

        setSteps(prev => {
          // Mark previous active step as completed
          const updated = prev.map(s => 
            s.status === "active" ? { ...s, status: "completed" as const } : s
          );
          
          return [...updated, {
            id: nextStepId(),
            icon: result.icon,
            message: result.message,
            status: "active" as const,
          }];
        });
      },
      () => {
        setSteps(prev => prev.map(s => ({ ...s, status: "completed" as const })));
        setIsComplete(true);
        onComplete?.();
      }
    );

    return () => eventSource.close();
  }, [runId, onComplete]);

  if (!runId) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />
        <span>Ready to search</span>
      </div>
    );
  }

  const visibleSteps = showAll ? steps : steps.slice(-4);
  const hiddenCount = steps.length - visibleSteps.length;

  return (
    <div className="py-2">
      {/* Collapsed history */}
      {hiddenCount > 0 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mb-3 transition-colors"
        >
          <ChevronDown className="h-3 w-3" />
          <span>{hiddenCount} previous steps</span>
        </button>
      )}

      {/* Timeline spine */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[9px] top-2 bottom-2 w-px bg-border" />

        {/* Steps */}
        <div className="space-y-3">
          {visibleSteps.map((step, idx) => {
            const Icon = IconMap[step.icon];
            const isLast = idx === visibleSteps.length - 1;
            
            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-start gap-3 relative animate-in fade-in slide-in-from-bottom-2 duration-300",
                  step.status === "completed" && !isLast && "opacity-50"
                )}
              >
                {/* Icon */}
                <div className={cn(
                  "relative z-10 flex h-5 w-5 items-center justify-center rounded-full",
                  step.status === "active" && "bg-foreground",
                  step.status === "completed" && "bg-muted",
                )}>
                  {step.status === "active" ? (
                    <Loader2 className="h-3 w-3 animate-spin text-background" />
                  ) : (
                    <Icon className="h-3 w-3 text-muted-foreground" />
                  )}
                </div>

                {/* Message */}
                <span className={cn(
                  "text-sm pt-0.5",
                  step.status === "active" ? "text-foreground font-medium" : "text-muted-foreground"
                )}>
                  {step.message}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Completion state */}
      {isComplete && steps.length > 0 && (
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border">
          <Check className="h-4 w-4 text-green-500" />
          <span className="text-sm text-muted-foreground">
            Search complete
          </span>
        </div>
      )}
    </div>
  );
};
