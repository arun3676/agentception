import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { useStudyDrawer } from "@/hooks/use-study-drawer";
import { analyzeSkillGaps, type AIResource, type SkillGapAnalysis } from "@/lib/api";
import { BarChart3, BookOpen, Sparkles, Target } from "lucide-react";

const SkillGaps = () => {
  const [resumeText, setResumeText] = useState("");
  const [jobText, setJobText] = useState("");
  const [targetRole, setTargetRole] = useState("AI Engineer");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<SkillGapAnalysis | null>(null);
  const [recommendations, setRecommendations] = useState<Record<string, AIResource[]>>({});
  const { openStudy, studyDrawer } = useStudyDrawer();

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const result = await analyzeSkillGaps({
        resume_text: resumeText,
        job_text: jobText || undefined,
        target_role: targetRole || undefined,
      });
      setAnalysis(result.analysis);
      setRecommendations(result.recommendations);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="card-clean p-8 mb-8">
          <p className="eyebrow mb-3">Verified skills</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Close the gaps before <span className="text-muted-foreground">you apply.</span>
          </h1>
          <p className="mt-4 max-w-3xl text-base text-muted-foreground">
            Compare your resume with target roles and get resource recommendations that feed back into your roadmap.
          </p>
        </div>

        <div className="card-clean p-6 mb-8">
          <h3 className="text-base font-semibold mb-1 flex items-center gap-2.5">
            <Target className="h-5 w-5" />
            Analyze your skill gaps
          </h3>
          <p className="text-sm text-muted-foreground mb-5">Paste your resume and a job description or target role.</p>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Target role</label>
              <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="h-10 rounded-lg text-sm" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Resume text</label>
              <Textarea
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                placeholder="Paste your resume text here..."
                rows={6}
                className="rounded-lg text-sm"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Job description (optional)</label>
              <Textarea
                value={jobText}
                onChange={(e) => setJobText(e.target.value)}
                placeholder="Paste job description to get more precise gaps..."
                rows={6}
                className="rounded-lg text-sm"
              />
            </div>
            <Button onClick={handleAnalyze} disabled={loading} className="h-10 rounded-lg text-sm">
              {loading ? "Analyzing..." : "Analyze gaps"}
            </Button>
          </div>
        </div>

        {analysis && (
          <div className="grid gap-5 md:grid-cols-2">
            <div className="card-clean p-6">
              <h3 className="text-base font-semibold mb-1 flex items-center gap-2.5">
                <BarChart3 className="h-5 w-5" />
                Missing skills
              </h3>
              <p className="text-sm text-muted-foreground mb-4">Focus on these to close the gap.</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                {(analysis.missing_skills || []).length === 0 && <p>No gaps found.</p>}
                {(analysis.missing_skills || []).map((skill: string) => (
                  <div
                    key={skill}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border bg-secondary/50 px-4 py-2.5"
                  >
                    <span>{skill}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openStudy(skill, { role: targetRole || undefined })}
                      className="h-7 shrink-0 gap-1 px-2 text-xs text-muted-foreground hover:text-accent"
                    >
                      <Sparkles className="h-3 w-3" />
                      Learn this
                    </Button>
                  </div>
                ))}
              </div>
            </div>
            <div className="card-clean p-6">
              <h3 className="text-base font-semibold mb-1 flex items-center gap-2.5">
                <BookOpen className="h-5 w-5" />
                Recommended resources
              </h3>
              <p className="text-sm text-muted-foreground mb-4">Start learning with curated links.</p>
              <div className="space-y-5 text-sm text-muted-foreground">
                {Object.entries(recommendations).map(([skill, resources]) => (
                  <div key={skill}>
                    <p className="font-medium text-foreground mb-1.5">{skill}</p>
                    <ul className="list-disc pl-5 space-y-1">
                      {resources.map((resource) => (
                        <li key={resource.id}>
                          <a
                            href={resource.url}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:underline"
                          >
                            {resource.title}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {studyDrawer}
    </div>
  );
};

export default SkillGaps;
