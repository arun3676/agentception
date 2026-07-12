import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { matchCohort, type CohortMatchResponse } from "@/lib/api";

const splitList = (value: string) =>
  value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

export default function Cohort() {
  const [username, setUsername] = useState("arun");
  const [targetRole, setTargetRole] = useState("AI Engineer");
  const [skills, setSkills] = useState("RAG, FastAPI, React");
  const [cohort, setCohort] = useState<CohortMatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleMatch = async () => {
    setError(null);
    try {
      const skillList = splitList(skills);
      const data = await matchCohort({
        target_profile: {
          username,
          target_role: targetRole,
          timezone: "America/Los_Angeles",
          skills: skillList,
          level: "intermediate",
          weekly_goal: "Ship one proof project",
        },
        candidates: [
          { username: "maya", target_role: targetRole, timezone: "America/Los_Angeles", skills: ["RAG", "Python"], level: "intermediate" },
          { username: "dev", target_role: "Full-Stack Developer", timezone: "America/New_York", skills: ["React", "FastAPI"], level: "intermediate" },
          { username: "sam", target_role: targetRole, timezone: "America/Los_Angeles", skills: ["Evaluation", "FastAPI"], level: "beginner" },
        ],
        cohort_size: 4,
      });
      setCohort(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to match cohort");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">Cohort</h1>
          <p className="text-base text-muted-foreground mt-1">
            Peer cohort matching and mock interview network.
          </p>
        </div>

        <div className="card-clean p-6 mb-8">
          <h3 className="text-base font-semibold mb-4">Match your cohort</h3>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label className="text-sm">Username</Label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} className="h-10 rounded-lg text-sm" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">Target role</Label>
              <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="h-10 rounded-lg text-sm" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">Skills</Label>
              <Input value={skills} onChange={(e) => setSkills(e.target.value)} className="h-10 rounded-lg text-sm" />
            </div>
          </div>
          <Button onClick={handleMatch} size="default" className="mt-4 rounded-lg text-sm">
            Match cohort
          </Button>
          {error && <p className="text-sm text-destructive mt-3">{error}</p>}
        </div>

        {cohort && (
          <div className="grid gap-5 md:grid-cols-2">
            <div className="card-clean p-6">
              <h3 className="text-base font-semibold mb-3">{cohort.cohort_id}</h3>
              <p className="text-sm text-muted-foreground mb-4">{cohort.size} members</p>
              <div className="space-y-3">
                {cohort.members.map((member) => (
                  <div key={member.username} className="flex items-center justify-between rounded-lg border border-border p-4">
                    <div>
                      <p className="text-base font-medium">{member.username}</p>
                      <p className="text-sm text-muted-foreground">{member.target_role}</p>
                    </div>
                    <Badge variant="outline" className="text-xs">{member.level}</Badge>
                  </div>
                ))}
              </div>
            </div>

            <div className="card-clean p-6">
              <h3 className="text-base font-semibold mb-1">Mock interview plan</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Provider: {cohort.mock_interview_plan.live_video_provider}
              </p>
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium mb-2">Weekly accountability</p>
                  <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
                    {cohort.weekly_accountability_template.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex flex-wrap gap-2">
                  {cohort.mock_interview_plan.feedback_sections.map((section) => (
                    <Badge key={section} variant="secondary" className="text-xs">{section}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
