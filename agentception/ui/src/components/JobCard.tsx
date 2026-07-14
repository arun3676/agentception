import { Button } from "@/components/ui/button";
import { ExternalLink, Wallet } from "lucide-react";
import type { JobCard as JobCardType } from "@/lib/jobCardNormalization";
import { toSafeExternalUrl } from "@/lib/safeUrl";

interface JobCardProps extends JobCardType {
  onOpen?: (url: string) => void;
}

export const JobCard = ({
  displayTitle,
  displayCompany,
  displayLocation,
  snippet,
  sourceDomain,
  sourceLabel,
  applyUrl,
  salary,
  observedAt,
  descriptionOrigin,
  remotePolicy,
  listingDataQuality,
  onOpen,
}: JobCardProps) => {
  const safeApplyUrl = toSafeExternalUrl(applyUrl);

  const handleOpen = () => {
    if (!safeApplyUrl) return;
    if (onOpen) onOpen(safeApplyUrl);
    else window.open(safeApplyUrl, "_blank", "noopener,noreferrer");
  };

  const cleanLocation = (location: string) =>
    location?.replace(/\s+/g, " ").trim() || "Location unavailable";

  const formatSource = (domain: string) => {
    if (!domain) return null;
    const name = domain.replace(/^(jobs\.|job-boards\.|boards\.)|(\.(io|com|co))$/g, "");
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  const domainLabel = sourceDomain === "Source unavailable" ? null : formatSource(sourceDomain);
  const cleanedLocation = cleanLocation(displayLocation);
  const observedDate = observedAt && !Number.isNaN(Date.parse(observedAt))
    ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(observedAt))
    : null;

  return (
    <article className="group rounded-3xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/10">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <h3 className="min-w-0 truncate text-base font-semibold text-foreground sm:text-lg">{displayTitle}</h3>
            {salary && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                <Wallet className="h-3.5 w-3.5" />
                {salary}
              </span>
            )}
          </div>

          <p className="text-sm leading-6 text-muted-foreground">
            <span className="font-medium text-foreground/80">{displayCompany}</span>
            <><span className="mx-2 text-muted-foreground/50">&middot;</span><span>{cleanedLocation}</span></>
            {domainLabel && <><span className="mx-2 text-muted-foreground/50">&middot;</span><span className="text-muted-foreground/60">via {domainLabel}</span></>}
          </p>

          {snippet && <p className="line-clamp-3 max-w-3xl text-sm leading-6 text-muted-foreground">{snippet}</p>}
          <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <div><dt className="inline font-medium text-foreground/70">Discovery source:</dt> <dd className="inline">{sourceLabel}</dd></div>
            <div><dt className="inline font-medium text-foreground/70">Observed:</dt> <dd className="inline">{observedDate || "Unavailable"}</dd></div>
            <div><dt className="inline font-medium text-foreground/70">Listing data:</dt> <dd className="inline">{listingDataQuality}</dd></div>
            <div><dt className="inline font-medium text-foreground/70">Description origin:</dt> <dd className="inline">{descriptionOrigin}</dd></div>
            <div><dt className="inline font-medium text-foreground/70">Remote policy:</dt> <dd className="inline">{remotePolicy}</dd></div>
          </dl>
        </div>

        <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center sm:opacity-70 sm:transition-opacity sm:group-hover:opacity-100">
          <Button
            variant="outline"
            size="sm"
            onClick={handleOpen}
            disabled={!safeApplyUrl}
            aria-label={safeApplyUrl ? `Open ${displayTitle} listing` : "Job listing URL unavailable"}
            className="justify-center gap-1.5 rounded-2xl text-muted-foreground hover:text-foreground"
          >
            {safeApplyUrl ? "View source" : "Source unavailable"}
            {safeApplyUrl && <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />}
          </Button>
        </div>
      </div>
    </article>
  );
};
