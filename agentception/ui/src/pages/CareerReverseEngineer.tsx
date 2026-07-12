import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { reverseEngineerCareer, type CareerReverseEngineerResponse } from "@/lib/api";

const splitList = (value: string) =>
  value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

export default function CareerReverseEngineer() {
  const [targetRole, setTargetRole] = useState("AI Engineer");
  const [city, setCity] = useState("San Francisco, CA");
  const [companies, setCompanies] = useState("OpenAI, Anthropic, Scale AI");
  const [skills, setSkills] = useState("Python, React, FastAPI");
  const [jobDescriptions, setJobDescriptions] = useState(
    "AI Engineer roles mention RAG, LLM evaluation, vector databases, FastAPI, Python, embeddings, observability, and product thinking.",
  );
  const [result, setResult] = useState<CareerReverseEngineerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reverseEngineerCareer({
        target_role: targetRole,
        city,
        dream_companies: splitList(companies),
        current_skills: splitList(skills),
        job_descriptions: jobDescriptions.trim() ? [jobDescriptions] : [],
        weeks: 12,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate roadmap");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
          Back to job search
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>Career Reverse Engineer</CardTitle>
            <CardDescription>
              Phase 1 turns target roles and job-description evidence into a 12-week proof roadmap without Supabase.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Target role</Label>
              <Input value={targetRole} onChange={(event) => setTargetRole(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>City</Label>
              <Input value={city} onChange={(event) => setCity(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Dream companies</Label>
              <Input value={companies} onChange={(event) => setCompanies(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Current skills</Label>
              <Input value={skills} onChange={(event) => setSkills(event.target.value)} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>JD evidence</Label>
              <Textarea value={jobDescriptions} onChange={(event) => setJobDescriptions(event.target.value)} />
            </div>
            <Button onClick={handleGenerate} disabled={loading} className="md:col-span-2">
              {loading ? "Generating..." : "Generate roadmap"}
            </Button>
            {error && <p className="text-sm text-destructive md:col-span-2">{error}</p>}
          </CardContent>
        </Card>

        {result && (
          <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <Card>
              <CardHeader>
                <CardTitle>Skill graph</CardTitle>
                <CardDescription>
                  {result.source_summary.job_descriptions_analyzed} JD source(s), {result.skill_graph.gaps.length} gaps
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {result.skill_graph.hard_skills.map((skill) => (
                    <Badge key={skill}>{skill}</Badge>
                  ))}
                </div>
                <div>
                  <p className="mb-2 text-sm font-medium">Gap priorities</p>
                  <div className="flex flex-wrap gap-2">
                    {result.skill_graph.gaps.map((skill) => (
                      <Badge key={skill} variant="outline">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              {result.roadmap.map((week) => (
                <Card key={week.week}>
                  <CardHeader>
                    <CardTitle className="text-lg">
                      Week {week.week}: {week.theme}
                    </CardTitle>
                    <CardDescription>{week.learning_module}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="font-medium">{week.micro_project}</p>
                    <p className="text-sm text-muted-foreground">{week.measurable_output}</p>
                    <div className="flex flex-wrap gap-2">
                      {week.skills.map((skill) => (
                        <Badge key={`${week.week}-${skill}`} variant="secondary">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
