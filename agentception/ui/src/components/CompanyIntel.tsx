import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Building2, ChevronDown, ExternalLink } from "lucide-react";
import { getCompanyBrief, type CompanyBrief } from "@/lib/api";

/** Expandable "what is this company?" panel. Fetches lazily on first open so a
 * results page of 20 cards costs nothing until the user actually asks. */
export const CompanyIntel = ({ company }: { company: string }) => {
  const [open, setOpen] = useState(false);
  const [brief, setBrief] = useState<CompanyBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !brief && !loading && !failed) {
      setLoading(true);
      getCompanyBrief(company)
        .then(setBrief)
        .catch(() => setFailed(true))
        .finally(() => setLoading(false));
    }
  };

  return (
    <div className="pt-1">
      <Button
        variant="ghost"
        size="sm"
        onClick={toggle}
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
      >
        <Building2 className="h-3.5 w-3.5" />
        Company intel
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </Button>

      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-border bg-secondary/30 p-3">
          {loading && (
            <>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </>
          )}

          {failed && <p className="text-xs text-muted-foreground">Couldn't load company details.</p>}

          {brief && (
            <>
              {brief.overview && (
                <p className="text-xs leading-5 text-muted-foreground">{brief.overview}</p>
              )}

              {brief.recent_news.length > 0 && (
                <div className="space-y-1 pt-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Recent news
                  </p>
                  {brief.recent_news.map((n) => (
                    <a
                      key={n.url}
                      href={n.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-start gap-1.5 text-xs text-foreground/80 hover:text-accent"
                    >
                      <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-50" />
                      <span className="line-clamp-1">{n.title}</span>
                    </a>
                  ))}
                </div>
              )}

              {!brief.overview && brief.recent_news.length === 0 && (
                <p className="text-xs text-muted-foreground">No details found for this company.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
