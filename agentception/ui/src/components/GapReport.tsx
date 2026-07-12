import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Lightbulb, Sparkles } from "lucide-react";
import { useStudyDrawer } from "@/hooks/use-study-drawer";

interface GapReportProps {
  missingSkills?: string[];
  suggestions?: string[];
  onTailor?: () => void;
  /** Job title, so study results are scoped to the role this gap came from */
  role?: string;
  company?: string;
}

export const GapReport = ({
  missingSkills = [],
  suggestions = [],
  onTailor,
  role,
  company,
}: GapReportProps) => {
  const { openStudy, studyDrawer } = useStudyDrawer();

  if (!missingSkills.length && !suggestions.length) return null;

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Lightbulb className="h-4 w-4" />
        Gap report
      </div>
      {missingSkills.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">
            Missing keywords <span className="text-muted-foreground/60">— click one to study it</span>
          </p>
          <div className="flex flex-wrap gap-1">
            {missingSkills.slice(0, 10).map((skill, idx) => (
              <button key={idx} type="button" onClick={() => openStudy(skill, { role, company })} className="group">
                <Badge
                  variant="outline"
                  className="cursor-pointer text-xs transition-colors group-hover:border-accent/60 group-hover:text-accent"
                >
                  <Sparkles className="mr-1 h-2.5 w-2.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  {skill}
                </Badge>
              </button>
            ))}
          </div>
        </div>
      )}
      {suggestions.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Suggestions</p>
          <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
            {suggestions.slice(0, 3).map((s, idx) => (
              <li key={idx}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {onTailor && (
        <Button size="sm" variant="outline" className="text-xs" onClick={onTailor}>
          Tailor resume to close this gap
        </Button>
      )}

      {studyDrawer}
    </div>
  );
};
