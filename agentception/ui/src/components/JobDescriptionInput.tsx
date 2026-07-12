import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { parseJobDescription, type ParsedJobData, type Keyword } from "@/lib/supabase";
import { 
  FileText, 
  Search, 
  Loader2, 
  AlertCircle, 
  CheckCircle2,
  Building2,
  Clock,
  Tags,
  Target,
  ArrowLeft
} from "lucide-react";

interface JobDescriptionInputProps {
  onParseComplete: (jobDescriptionId: string, data: ParsedJobData, keywords: Keyword[]) => void;
  onBack?: () => void;
  prefilledText?: string;
  prefilledTitle?: string;
  prefilledCompany?: string;
  prefilledUrl?: string;
}

export const JobDescriptionInput = ({ 
  onParseComplete, 
  onBack,
  prefilledText = "",
  prefilledTitle = "",
  prefilledCompany = "",
  prefilledUrl = ""
}: JobDescriptionInputProps) => {
  const [jobDescription, setJobDescription] = useState(prefilledText);
  const [jobTitle, setJobTitle] = useState(prefilledTitle);
  const [companyName, setCompanyName] = useState(prefilledCompany);
  const [jobUrl, setJobUrl] = useState(prefilledUrl);
  
  const [isParsing, setIsParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parsedData, setParsedData] = useState<ParsedJobData | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  
  // Update text when prefilled text loads (e.g. from background fetch)
  useEffect(() => {
    if (prefilledText && prefilledText.length > jobDescription.length + 50) {
      setJobDescription(prefilledText);
    }
  }, [prefilledText, jobDescription.length]);
  const [error, setError] = useState<string | null>(null);

  const handleParse = async () => {
    if (!jobDescription.trim()) {
      setError("Please enter a job description");
      return;
    }

    if (jobDescription.trim().length < 100) {
      setError("Job description seems too short. Please paste the full job posting.");
      return;
    }

    setIsParsing(true);
    setError(null);
    setParseProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setParseProgress((prev) => {
          if (prev >= 80) {
            clearInterval(progressInterval);
            return 80;
          }
          return prev + 15;
        });
      }, 400);

      const result = await parseJobDescription(jobDescription, undefined, {
        jobTitle: jobTitle || undefined,
        companyName: companyName || undefined,
        jobUrl: jobUrl || undefined,
      });

      clearInterval(progressInterval);
      setParseProgress(100);

      setParsedData(result.parsedData);
      setKeywords(result.keywords);
      
      // Auto-fill company name if detected
      if (!companyName && result.parsedData.company?.name) {
        setCompanyName(result.parsedData.company.name);
      }

      onParseComplete(result.jobDescriptionId, result.parsedData, result.keywords);
    } catch (err) {
      console.error("Parse error:", err);
      setError(err instanceof Error ? err.message : "Failed to parse job description");
      setParseProgress(0);
    } finally {
      setIsParsing(false);
    }
  };

  const handleClear = () => {
    setJobDescription("");
    setJobTitle("");
    setCompanyName("");
    setJobUrl("");
    setParsedData(null);
    setKeywords([]);
    setError(null);
    setParseProgress(0);
  };

  const getKeywordsByCategory = (category: string) => {
    return keywords.filter((k) => k.category === category);
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case "technical":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300";
      case "tool":
        return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300";
      case "soft":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300";
      case "methodology":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300";
    }
  };

  return (
    <div className="space-y-6">
      {/* Input Section */}
      {!parsedData && (
        <>
          {/* Optional Metadata */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="jobTitle">Job Title (Optional)</Label>
              <Input
                id="jobTitle"
                placeholder="e.g., Senior Software Engineer"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                disabled={isParsing}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="companyName">Company Name (Optional)</Label>
              <Input
                id="companyName"
                placeholder="e.g., Google"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                disabled={isParsing}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="jobUrl">Job Posting URL (Optional)</Label>
            <Input
              id="jobUrl"
              placeholder="https://..."
              value={jobUrl}
              onChange={(e) => setJobUrl(e.target.value)}
              disabled={isParsing}
            />
          </div>

          {/* Job Description Textarea */}
          <div className="space-y-2">
            <Label htmlFor="jobDescription">
              Job Description <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="jobDescription"
              placeholder="Paste the full job description here...

Include:
• Job requirements and qualifications
• Responsibilities
• Required skills and technologies
• Benefits (optional)"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              className="min-h-[250px] font-mono text-sm"
              disabled={isParsing}
            />
            <p className="text-xs text-muted-foreground">
              {jobDescription.length} characters
              {jobDescription.length > 0 && jobDescription.length < 100 && (
                <span className="text-yellow-600 dark:text-yellow-400"> (minimum 100 recommended)</span>
              )}
            </p>
          </div>

          {/* Parse Progress */}
          {isParsing && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Analyzing job description...</span>
                <span className="font-medium">{parseProgress}%</span>
              </div>
              <Progress value={parseProgress} className="h-2" />
              <p className="text-xs text-muted-foreground">
                {parseProgress < 30
                  ? "Extracting text..."
                  : parseProgress < 60
                  ? "Identifying keywords..."
                  : parseProgress < 90
                  ? "Categorizing requirements..."
                  : "Finalizing analysis..."}
              </p>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 text-destructive">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-4">
            {onBack && (
              <Button variant="outline" onClick={onBack} disabled={isParsing}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}
            <Button 
              onClick={handleParse} 
              disabled={isParsing || !jobDescription.trim()}
              className="flex-1"
            >
              {isParsing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Analyze Job Description
                </>
              )}
            </Button>
          </div>
        </>
      )}

      {/* Parsed Results */}
      {parsedData && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Job description analyzed!</span>
          </div>

          {/* Summary Cards */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Company Info */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Job Details
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                <p><span className="text-muted-foreground">Company:</span> {parsedData.company?.name || companyName || "Unknown"}</p>
                <p><span className="text-muted-foreground">Title:</span> {jobTitle || "Not specified"}</p>
                <p><span className="text-muted-foreground">Location:</span> {
                  parsedData.company?.location?.city 
                    ? `${parsedData.company.location.city}${parsedData.company.location.remote ? " (Remote)" : ""}`
                    : parsedData.remote ? "Remote" : "Not specified"
                }</p>
              </CardContent>
            </Card>

            {/* Requirements Summary */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Requirements
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-1">
                <p><span className="text-muted-foreground">Experience:</span> {
                  parsedData.requirements.experience.minYears 
                    ? `${parsedData.requirements.experience.minYears}${parsedData.requirements.experience.maxYears ? `-${parsedData.requirements.experience.maxYears}` : "+"} years`
                    : parsedData.requirements.experience.level || "Not specified"
                }</p>
                <p><span className="text-muted-foreground">Education:</span> {parsedData.requirements.education.degreeLevel || "Not specified"}</p>
                <p><span className="text-muted-foreground">Skills Required:</span> {parsedData.requirements.skills.required?.length || 0}</p>
              </CardContent>
            </Card>
          </div>

          {/* Keywords Section */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Tags className="h-4 w-4" />
                ATS Keywords ({keywords.length} found)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Required Keywords */}
              {keywords.filter(k => k.context === "required").length > 0 && (
                <div>
                  <p className="text-xs font-medium text-destructive mb-2 flex items-center gap-1">
                    <Target className="h-3 w-3" />
                    Required ({keywords.filter(k => k.context === "required").length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {keywords.filter(k => k.context === "required").slice(0, 15).map((keyword, idx) => (
                      <span
                        key={idx}
                        className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor(keyword.category)}`}
                      >
                        {keyword.text}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Preferred Keywords */}
              {keywords.filter(k => k.context === "preferred").length > 0 && (
                <div>
                  <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400 mb-2">
                    Preferred ({keywords.filter(k => k.context === "preferred").length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {keywords.filter(k => k.context === "preferred").slice(0, 15).map((keyword, idx) => (
                      <span
                        key={idx}
                        className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor(keyword.category)}`}
                      >
                        {keyword.text}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Other Keywords */}
              {keywords.filter(k => k.context === "nice-to-have" || !k.context).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-2">
                    Nice to Have ({keywords.filter(k => k.context === "nice-to-have" || !k.context).length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {keywords.filter(k => k.context === "nice-to-have" || !k.context).slice(0, 10).map((keyword, idx) => (
                      <span
                        key={idx}
                        className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor(keyword.category)}`}
                      >
                        {keyword.text}
                      </span>
                    ))}
                    {keywords.filter(k => k.context === "nice-to-have" || !k.context).length > 10 && (
                      <span className="text-xs text-muted-foreground">
                        +{keywords.filter(k => k.context === "nice-to-have" || !k.context).length - 10} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Category Legend */}
              <div className="flex flex-wrap gap-2 pt-2 border-t">
                <span className="text-xs text-muted-foreground">Categories:</span>
                <span className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor("technical")}`}>Technical</span>
                <span className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor("tool")}`}>Tools</span>
                <span className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor("soft")}`}>Soft Skills</span>
                <span className={`px-2 py-0.5 rounded-full text-xs ${getCategoryColor("methodology")}`}>Methodology</span>
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <Button variant="outline" onClick={handleClear} className="w-full">
            Analyze Different Job
          </Button>
        </div>
      )}
    </div>
  );
};

