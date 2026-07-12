import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Bookmark, BookmarkCheck, ExternalLink, LogIn, Wallet } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { useAuth } from "@/auth/AuthProvider";
import { JobCard as JobCardType } from "@/lib/jobCardNormalization";
import { createApplication } from "@/lib/api";
import { trackFailure, trackIntent } from "@/lib/trackOutcome";
import { MatchScoreBadge } from "./MatchScoreBadge";
import { GapReport } from "./GapReport";
import { TailorJobButton } from "./TailorJobButton";
import { CompanyIntel } from "./CompanyIntel";

interface JobCardProps extends JobCardType {
  onOpen?: (url: string) => void;
  resumeToken?: string | null;
  resumeId?: string | null;
  runId?: string | null;
}

export const JobCard = ({
  displayTitle,
  displayCompany,
  displayLocation,
  snippet,
  sourceDomain,
  applyUrl,
  matchScore,
  matchBand,
  matchProbability,
  matchExplanation,
  missingSkills,
  salary,
  resumeToken,
  resumeId,
  runId,
  onOpen,
}: JobCardProps) => {
  const [tracked, setTracked] = useState(false);
  const [tracking, setTracking] = useState(false);
  const { session } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const signedIn = Boolean(session);

  // Matches RequireAuth/Login's convention, so the user lands back here afterwards.
  const goSignIn = () => navigate("/login", { state: { from: location } });

  const handleOpen = () => {
    if (onOpen) {
      onOpen(applyUrl);
    } else {
      window.open(applyUrl, "_blank", "noopener,noreferrer");
    }
  };

  // Clean location string (fixes encoding issues)
  const cleanLocation = (loc: string) => {
    return loc?.replace(/[^\x20-\x7E]/g, ' ').replace(/\s+/g, ' ').trim() || '';
  };

  // Smart company name logic
  const isTitleSameAsCompany = displayTitle.toLowerCase() === displayCompany.toLowerCase();
  const aggregators = ["indeed", "glassdoor", "ziprecruiter", "linkedin", "google", "simplyhired"];
  const isAggregator = aggregators.some(agg => displayCompany.toLowerCase().includes(agg));

  let finalCompany = displayCompany;
  if (isTitleSameAsCompany) {
    finalCompany = sourceDomain ? `via ${sourceDomain}` : "Company";
  } else if (isAggregator) {
    finalCompany = `via ${displayCompany}`;
  }

  // Only a real company name is worth researching or filing under
  const isRealCompany = !isTitleSameAsCompany && !isAggregator && Boolean(displayCompany);

  const handleTrack = async () => {
    if (tracked || tracking) return;

    // Signed out: go somewhere useful. Firing a request we know will be rejected,
    // then reporting it as a generic failure, is how the old code told people to
    // "try again" at something that could never succeed.
    if (trackIntent(signedIn) === "sign-in") {
      goSignIn();
      return;
    }

    setTracking(true);
    try {
      await createApplication({
        company_name: isRealCompany ? displayCompany : sourceDomain || "Unknown",
        job_title: displayTitle,
        job_url: applyUrl,
        application_status: "applied",
      });
      setTracked(true);
      toast({
        title: "Added to your applications",
        description: `${displayTitle} — track its outcome from the Applications page.`,
      });
    } catch (error) {
      // The session can expire between render and click, so a signed-in user can
      // still land in the sign-in case here.
      const failure = trackFailure(error);
      toast({
        title: failure.title,
        description: failure.description,
        variant: "destructive",
      });
      if (failure.kind === "sign-in") goSignIn();
    } finally {
      setTracking(false);
    }
  };

  // Format source label (e.g., "greenhouse.io" -> "Greenhouse")
  const formatSource = (domain: string) => {
    if (!domain) return null;
    const name = domain.replace(/^(jobs\.|job-boards\.|boards\.)|(\.(io|com|co))$/g, '');
    return name.charAt(0).toUpperCase() + name.slice(1);
  };

  const sourceLabel = formatSource(sourceDomain);
  const cleanedLocation = displayLocation ? cleanLocation(displayLocation) : null;

  return (
    <div className="group rounded-3xl border border-border/70 bg-card/80 p-5 shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/10">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        {/* Left: Job Info */}
        <div className="min-w-0 flex-1 space-y-3">
          {/* Title + Salary + Match Score */}
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <h3 className="min-w-0 truncate text-base font-semibold text-foreground sm:text-lg">
              {displayTitle}
            </h3>
            {salary && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                <Wallet className="h-3.5 w-3.5" />
                {salary}
              </span>
            )}
            {resumeToken && matchBand && (
              <MatchScoreBadge
                band={matchBand}
                probability={matchProbability}
                explanation={matchExplanation}
                rawScore={matchScore}
              />
            )}
          </div>

          {/* Company • Location • Source */}
          <p className="text-sm leading-6 text-muted-foreground">
            <span className="font-medium text-foreground/80">{finalCompany}</span>
            {cleanedLocation && (
              <>
                <span className="mx-2 text-muted-foreground/50">•</span>
                <span>{cleanedLocation}</span>
              </>
            )}
            {sourceLabel && (
              <>
                <span className="mx-2 text-muted-foreground/50">•</span>
                <span className="text-muted-foreground/60">via {sourceLabel}</span>
              </>
            )}
          </p>

          {/* Gap Report — each missing skill opens curated study material */}
          {missingSkills && missingSkills.length > 0 && (
            <div className="pt-1">
              <GapReport
                missingSkills={missingSkills}
                role={displayTitle}
                company={isRealCompany ? displayCompany : undefined}
              />
            </div>
          )}

          {snippet && (
            <p className="line-clamp-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              {snippet}
            </p>
          )}

          {isRealCompany && <CompanyIntel company={displayCompany} />}
        </div>

        {/* Right: Actions */}
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center sm:opacity-70 sm:transition-opacity sm:group-hover:opacity-100">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleTrack}
            disabled={tracked || tracking}
            title={signedIn ? undefined : "Sign in to save roles to your applications"}
            className="justify-center gap-1.5 rounded-2xl text-muted-foreground hover:text-foreground"
          >
            {tracked ? (
              <BookmarkCheck className="h-3.5 w-3.5" />
            ) : signedIn ? (
              <Bookmark className="h-3.5 w-3.5" />
            ) : (
              <LogIn className="h-3.5 w-3.5" />
            )}
            {tracked ? "Tracked" : signedIn ? "Track" : "Sign in to track"}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleOpen}
            className="justify-center gap-1.5 rounded-2xl text-muted-foreground hover:text-foreground"
          >
            View
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>

          {runId && (
            <TailorJobButton
              jobUrl={applyUrl}
              jobSnippet={snippet}
              jobTitle={displayTitle}
              company={finalCompany}
              resumeId={resumeId}
              resumeToken={resumeToken}
              runId={runId}
            />
          )}
        </div>
      </div>
    </div>
  );
};
