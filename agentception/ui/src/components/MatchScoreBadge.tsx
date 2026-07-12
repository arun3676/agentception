import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CircleHelp, Flame, Scale, TrendingUp } from "lucide-react";

export type MatchBand = "strong" | "possible" | "stretch" | "unknown";

interface MatchScoreBadgeProps {
  band?: MatchBand | null;
  /** Calibrated P(genuine fit), 0-1. Not the raw score. */
  probability?: number | null;
  explanation?: string | null;
  /** Raw hybrid score, shown only in the tooltip for the curious. */
  rawScore?: number | null;
}

/**
 * Shows a *band*, not a number.
 *
 * The old badge rendered the raw hybrid score as "44%", which reads as "you are 44%
 * qualified" — a claim the score never supported. Raw scores also cluster in a narrow
 * range (34-55 on our labelled set), so fixed 80/60 thresholds painted almost every
 * job red regardless of fit.
 *
 * The band comes from a calibrated probability fitted on labelled resume/JD pairs,
 * and "unknown" is a real, displayable outcome — better than inventing a score.
 */
const STYLES: Record<MatchBand, { label: string; className: string; Icon: typeof Flame }> = {
  strong: {
    label: "Strong fit",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
    Icon: Flame,
  },
  possible: {
    label: "Possible fit",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
    Icon: Scale,
  },
  stretch: {
    label: "A stretch",
    className: "bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300",
    Icon: TrendingUp,
  },
  unknown: {
    label: "Not assessed",
    className: "bg-muted text-muted-foreground",
    Icon: CircleHelp,
  },
};

export const MatchScoreBadge = ({
  band,
  probability,
  explanation,
  rawScore,
}: MatchScoreBadgeProps) => {
  const style = STYLES[band ?? "unknown"];
  const { Icon } = style;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge className={`flex cursor-help items-center gap-1 px-2 py-1 text-xs ${style.className}`}>
          <Icon className="h-3 w-3" />
          <span>{style.label}</span>
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs space-y-1.5">
        <p className="text-sm">{explanation || "No explanation available."}</p>
        {probability != null && (
          <p className="text-xs text-muted-foreground">
            Calibrated likelihood of a genuine fit: {Math.round(probability * 100)}%
            {rawScore != null && ` · raw score ${rawScore.toFixed(1)}`}
          </p>
        )}
      </TooltipContent>
    </Tooltip>
  );
};
