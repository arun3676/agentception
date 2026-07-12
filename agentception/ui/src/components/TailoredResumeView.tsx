import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { 
  type ParsedResumeData, 
  type TailorResumeResponse,
  type Keyword
} from "@/lib/supabase";
import { 
  CheckCircle2, 
  AlertCircle, 
  TrendingUp, 
  FileText,
  Sparkles,
  Target,
  ArrowRight,
  Plus,
  Minus,
  Copy,
  Check
} from "lucide-react";

interface TailoredResumeViewProps {
  originalResume: ParsedResumeData;
  tailoredData: TailorResumeResponse;
  keywords: Keyword[];
}

export const TailoredResumeView = ({ 
  originalResume, 
  tailoredData, 
  keywords 
}: TailoredResumeViewProps) => {
  const [activeTab, setActiveTab] = useState("overview");
  const [copied, setCopied] = useState(false);

  const { matchScore, scoreBreakdown, changes, tailoredData: tailoredResume } = tailoredData;

  // Calculate which keywords were matched
  const matchedKeywords = changes.addedKeywords || [];
  const missingKeywords = keywords
    .filter(k => k.context === "required")
    .filter(k => !matchedKeywords.some(mk => 
      mk.toLowerCase() === k.text.toLowerCase()
    ))
    .map(k => k.text);

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-600 dark:text-green-400";
    if (score >= 60) return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400";
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 80) return "bg-green-100 dark:bg-green-900/30";
    if (score >= 60) return "bg-yellow-100 dark:bg-yellow-900/30";
    return "bg-red-100 dark:bg-red-900/30";
  };

  const resumeText = useMemo(() => {
    const lines: string[] = [];
    const contact = tailoredResume.contact;
    
    // Professional format: Name on its own line (fixes overlapping)
    lines.push(contact.name || "Candidate Name");
    
    // Target job title if available (professional checklist requirement)
    const targetJobTitle = (tailoredResume as any).target_job_title || (tailoredResume as any).targetJobTitle;
    if (targetJobTitle) {
      lines.push(targetJobTitle);
    }
    
    // Contact info: clean, easy to scan (professional checklist)
    const contactParts: string[] = [];
    const locationParts = [
      contact.city,
      contact.state || contact.country
    ].filter(Boolean);
    if (locationParts.length) {
      contactParts.push(locationParts.join(", "));
    }
    if (contact.email) contactParts.push(contact.email);
    if (contact.phone) contactParts.push(contact.phone);
    
    if (contactParts.length) {
      lines.push(contactParts.join(" | "));
    }
    
    // Links on separate line
    const links: string[] = [];
    if (contact.github) links.push(`GitHub: ${contact.github}`);
    if (contact.linkedin) links.push(`LinkedIn: ${contact.linkedin}`);
    if (contact.website) links.push(`Portfolio: ${contact.website}`);
    
    if (links.length) {
      lines.push(links.join(" | "));
    }
    
    lines.push(""); // Blank line after header

    // Summary: 2-4 lines format (professional checklist)
    if (tailoredResume.summary) {
      lines.push("PROFESSIONAL SUMMARY");
      // Limit to 2-3 sentences for professional 2-4 line format
      const summarySentences = tailoredResume.summary.split('. ').filter(s => s.trim());
      const summaryText = summarySentences.slice(0, 3).join('. ').trim();
      lines.push(summaryText + (summaryText && !summaryText.endsWith('.') ? '.' : ''));
      lines.push(""); // Blank line after summary
    }

    // Skills
    const skills = tailoredResume.skills || {};
    const skillSections: Array<[string, string[] | undefined]> = [
      ["Technical", skills.technical],
      ["Soft", skills.soft],
      ["Languages", skills.languages],
      ["Industry", skills.industry],
    ];
    const skillLines: string[] = [];
    skillSections.forEach(([label, arr]) => {
      if (arr && arr.length) {
        skillLines.push(`${label}: ${arr.join(", ")}`);
      }
    });
    if (skillLines.length) {
      lines.push("");
      lines.push("SKILLS");
      lines.push(...skillLines);
    }

    // Experience
    if (tailoredResume.experience && tailoredResume.experience.length) {
      lines.push("");
      lines.push("EXPERIENCE");
      tailoredResume.experience.forEach((exp) => {
        const headerParts = [
          exp.position,
          exp.company,
          exp.location,
          `${exp.duration.start} – ${exp.duration.end}`.replace("present", "Present"),
        ].filter(Boolean);
        lines.push(headerParts.join(" | "));
        if (exp.description) lines.push(`- ${exp.description}`);
        exp.achievements?.forEach((ach) => lines.push(`- ${ach}`));
        if (exp.technologies?.length) {
          lines.push(`  Tech: ${exp.technologies.join(", ")}`);
        }
        lines.push("");
      });
    }

    // Education
    if (tailoredResume.education && tailoredResume.education.length) {
      lines.push("EDUCATION");
      tailoredResume.education.forEach((edu) => {
        const eduParts = [
          edu.degree,
          edu.field,
          edu.institution,
          edu.location,
          `${edu.duration.start} – ${edu.duration.end}`.replace("present", "Present"),
        ].filter(Boolean);
        lines.push(eduParts.join(" | "));
        if (edu.honors?.length) lines.push(`- Honors: ${edu.honors.join(", ")}`);
        if (edu.gpa) lines.push(`- GPA: ${edu.gpa}`);
        lines.push("");
      });
    }

    // Certifications
    if (tailoredResume.certifications && tailoredResume.certifications.length) {
      lines.push("CERTIFICATIONS");
      tailoredResume.certifications.forEach((cert) => {
        const certParts = [
          cert.name,
          cert.issuer,
          cert.dateObtained,
          cert.credentialId,
        ].filter(Boolean);
        lines.push(certParts.join(" | "));
      });
    }

    return lines.join("\n").trim();
  }, [tailoredResume]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(resumeText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy resume text", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Success Header */}
      <div className="flex items-center gap-3 p-4 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
        <CheckCircle2 className="h-6 w-6 shrink-0" />
        <div>
          <p className="font-medium">Resume tailored successfully!</p>
          <p className="text-sm opacity-80">
            Your resume has been optimized to match the job requirements.
          </p>
        </div>
      </div>

      {/* Score Overview Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            ATS Match Score
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            {/* Main Score Circle */}
            <div className={`relative flex items-center justify-center w-32 h-32 rounded-full ${getScoreBgColor(matchScore)}`}>
              <div className="text-center">
                <p className={`text-4xl font-bold ${getScoreColor(matchScore)}`}>
                  {matchScore}%
                </p>
                <p className="text-xs text-muted-foreground">Match Score</p>
              </div>
            </div>

            {/* Score Breakdown */}
            <div className="flex-1 space-y-3">
              {Object.entries(scoreBreakdown).map(([key, value]) => (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize text-muted-foreground">
                      {key.replace(/([A-Z])/g, " $1").trim()}
                    </span>
                    <span className={`font-medium ${getScoreColor(value)}`}>
                      {value}%
                    </span>
                  </div>
                  <Progress value={value} className="h-2" />
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs for Details */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">
            <TrendingUp className="h-4 w-4 mr-2" />
            Changes
          </TabsTrigger>
          <TabsTrigger value="keywords">
            <Sparkles className="h-4 w-4 mr-2" />
            Keywords
          </TabsTrigger>
          <TabsTrigger value="comparison">
            <FileText className="h-4 w-4 mr-2" />
            Preview
          </TabsTrigger>
        </TabsList>

        {/* Changes Tab */}
        <TabsContent value="overview" className="mt-4 space-y-4">
          {/* Changes Summary */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Optimization Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Added Keywords */}
              {matchedKeywords.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Plus className="h-4 w-4 text-green-600 dark:text-green-400" />
                    <p className="text-sm font-medium">
                      Keywords Added ({matchedKeywords.length})
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {matchedKeywords.map((keyword, idx) => (
                      <Badge key={idx} variant="secondary" className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                        {keyword}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Modified Sections */}
              {changes.modifiedSections && changes.modifiedSections.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <ArrowRight className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <p className="text-sm font-medium">
                      Sections Modified ({changes.modifiedSections.length})
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {changes.modifiedSections.map((section, idx) => (
                      <Badge key={idx} variant="outline" className="capitalize">
                        {section}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Reordered Sections */}
              {changes.reorderedSections && changes.reorderedSections.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    <p className="text-sm font-medium">
                      Sections Reordered for Relevance
                    </p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {changes.reorderedSections.join(" → ")}
                  </p>
                </div>
              )}

              {/* Optimized Bullets */}
              {changes.optimizedBullets > 0 && (
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                  <p className="text-sm">
                    <span className="font-medium">{changes.optimizedBullets}</span> bullet points optimized with keywords
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recommendations */}
          {missingKeywords.length > 0 && (
            <Card className="border-yellow-200 dark:border-yellow-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2 text-yellow-700 dark:text-yellow-400">
                  <AlertCircle className="h-4 w-4" />
                  Missing Required Keywords
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-2">
                  These keywords couldn't be naturally added. Consider adding relevant experience or skills:
                </p>
                <div className="flex flex-wrap gap-1">
                  {missingKeywords.slice(0, 10).map((keyword, idx) => (
                    <Badge key={idx} variant="outline" className="border-yellow-200 dark:border-yellow-800 text-yellow-700 dark:text-yellow-400">
                      {keyword}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Keywords Tab */}
        <TabsContent value="keywords" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Keyword Coverage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Matched Keywords */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-green-700 dark:text-green-400">
                    <CheckCircle2 className="h-4 w-4 inline mr-1" />
                    Matched ({matchedKeywords.length})
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {matchedKeywords.map((keyword, idx) => (
                    <Badge 
                      key={idx} 
                      className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                    >
                      {keyword}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Missing Keywords */}
              {missingKeywords.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-red-700 dark:text-red-400">
                      <Minus className="h-4 w-4 inline mr-1" />
                      Missing ({missingKeywords.length})
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {missingKeywords.map((keyword, idx) => (
                      <Badge 
                        key={idx} 
                        variant="outline"
                        className="border-red-200 dark:border-red-800 text-red-700 dark:text-red-400"
                      >
                        {keyword}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Coverage Stats */}
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Overall Keyword Coverage</span>
                  <span className="font-medium">
                    {keywords.length > 0 
                      ? Math.round((matchedKeywords.length / keywords.filter(k => k.context === "required").length) * 100) || 0
                      : 0}%
                  </span>
                </div>
                <Progress 
                  value={keywords.length > 0 
                    ? (matchedKeywords.length / keywords.filter(k => k.context === "required").length) * 100 
                    : 0} 
                  className="h-2 mt-2" 
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Comparison/Preview Tab */}
        <TabsContent value="comparison" className="mt-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Original Resume Preview */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Original Resume
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <div>
                  <p className="font-medium">{originalResume.contact.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {originalResume.contact.email}
                  </p>
                </div>
                {originalResume.summary && (
                  <p className="text-xs text-muted-foreground line-clamp-3">
                    {originalResume.summary}
                  </p>
                )}
                <div>
                  <p className="text-xs font-medium">Skills:</p>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {originalResume.skills.technical?.slice(0, 8).join(", ")}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Tailored Resume Preview */}
            <Card className="border-green-200 dark:border-green-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-green-700 dark:text-green-400 flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  Tailored Resume
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <div>
                  <p className="font-medium">{tailoredResume.contact.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {tailoredResume.contact.email}
                  </p>
                </div>
                {tailoredResume.summary && (
                  <p className="text-xs text-muted-foreground line-clamp-3">
                    {tailoredResume.summary}
                  </p>
                )}
                <div>
                  <p className="text-xs font-medium">Skills:</p>
                  <div className="flex flex-wrap gap-1">
                    {tailoredResume.skills.technical?.slice(0, 8).map((skill, idx) => {
                      const isNew = !originalResume.skills.technical?.includes(skill);
                      return (
                        <span 
                          key={idx} 
                          className={`text-xs px-1 rounded ${
                            isNew 
                              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" 
                              : ""
                          }`}
                        >
                          {skill}
                        </span>
                      );
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground text-center mt-4">
            Copy the tailored resume below and paste it into your ATS or doc editor.
          </p>

          {/* Copy-paste tailored resume */}
          <Card className="mt-4 border-green-200 dark:border-green-800">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium text-green-700 dark:text-green-400 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Copy Tailored Resume
              </CardTitle>
              <Button size="sm" variant="outline" onClick={handleCopy} className="gap-2">
                {copied ? (
                  <>
                    <Check className="h-4 w-4" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-xs md:text-sm leading-relaxed bg-muted/50 p-4 rounded-lg border border-border">
                {resumeText}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

