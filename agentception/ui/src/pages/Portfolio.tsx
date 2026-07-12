import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createProjectBrief, createSkillReceipt, type ProjectBrief, type SkillReceipt as SkillReceiptData } from "@/lib/api";
import { Github, ExternalLink, Plus, Check } from "lucide-react";

const splitList = (value: string) =>
  value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

const mockProjects = [
  {
    title: "RAG PDF Assistant",
    description: "RAG system for document question answering",
    tags: ["Python", "FastAPI"],
    live: true,
    github_url: "https://github.com/example/rag-pdf-assistant",
    deployment_url: "https://rag-pdf-assistant.example.com",
  },
  {
    title: "AI Resume Tailor",
    description: "ATS-optimized resume tailoring using LLMs",
    tags: ["Next.js", "OpenAI"],
    live: true,
    github_url: "https://github.com/example/ai-resume-tailor",
    deployment_url: "https://ai-resume-tailor.example.com",
  },
  {
    title: "Job Trend Analyzer",
    description: "Real-time job market analytics dashboard",
    tags: ["Python", "Streamlit"],
    live: false,
    github_url: "https://github.com/example/job-trend-analyzer",
    deployment_url: "https://job-trend-analyzer.example.com",
  },
];

export default function Portfolio() {
  const [targetRole, setTargetRole] = useState("AI Engineer");
  const [skills, setSkills] = useState("RAG, FastAPI, Vector Databases");
  const [githubUrl, setGithubUrl] = useState("https://github.com/example/rag-proof");
  const [deploymentUrl, setDeploymentUrl] = useState("https://rag-proof.example.com");
  const [brief, setBrief] = useState<ProjectBrief | null>(null);
  const [receipt, setReceipt] = useState<SkillReceiptData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("projects");

  const handleBuild = async () => {
    setError(null);
    try {
      const skillList = splitList(skills);
      const nextBrief = await createProjectBrief({
        target_role: targetRole,
        week: 1,
        skills: skillList,
        project_title: `${skillList[0] || "Proof"} portfolio project`,
      });
      const nextReceipt = await createSkillReceipt({
        project_title: nextBrief.title,
        skills: nextBrief.tech_stack,
        github_url: githubUrl || undefined,
        deployment_url: deploymentUrl || undefined,
        commit_count: 12,
        checks_passed: true,
        code_quality_score: 86,
      });
      setBrief(nextBrief);
      setReceipt(nextReceipt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to build portfolio proof");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
            <p className="text-base text-muted-foreground mt-1">
              Proof-of-skill projects and verifiable receipts.
            </p>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-8">
          <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 w-full justify-start gap-4 sm:gap-8 overflow-x-auto whitespace-nowrap">
            {["projects", "skills"].map((tab) => (
              <TabsTrigger
                key={tab}
                value={tab}
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 py-3 text-base capitalize"
              >
                {tab}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {activeTab === "projects" && (
          <div className="space-y-8">
            {/* Project Grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {mockProjects.map((project) => (
                <div key={project.title} className="card-clean p-5">
                  <div className="h-28 rounded-lg bg-secondary mb-4" />
                  <div className="flex items-start justify-between">
                    <h3 className="text-base font-semibold">{project.title}</h3>
                    {project.live && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Live
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {project.tags.map((tag) => (
                      <span key={tag} className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <Button asChild variant="ghost" size="icon" className="h-7 w-7 rounded" title="Open repository">
                      <a href={project.github_url} target="_blank" rel="noopener noreferrer">
                        <Github className="h-3.5 w-3.5" />
                      </a>
                    </Button>
                    <Button asChild variant="ghost" size="icon" className="h-7 w-7 rounded" title="Open demo">
                      <a href={project.deployment_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            {/* New Project Button */}
            <Button
              variant="outline"
              size="default"
              className="gap-2 rounded-lg text-sm"
              onClick={() => document.getElementById("project-brief-form")?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              <Plus className="h-4 w-4" />
              New Project
            </Button>

            {/* Generate Form */}
            <div id="project-brief-form" className="card-clean p-6 scroll-mt-6">
              <h3 className="text-base font-semibold mb-4">Generate Project Brief</h3>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-sm">Target role</Label>
                  <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Skills to prove</Label>
                  <Input value={skills} onChange={(e) => setSkills(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">GitHub URL</Label>
                  <Input value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Deployment URL</Label>
                  <Input value={deploymentUrl} onChange={(e) => setDeploymentUrl(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
              </div>
              <Button onClick={handleBuild} size="default" className="mt-4 rounded-lg text-sm">
                Generate brief and receipt
              </Button>
              {error && <p className="text-sm text-destructive mt-3">{error}</p>}
            </div>

            {/* Brief & Receipt */}
            {brief && (
              <div className="card-clean p-6">
                <h3 className="text-base font-semibold mb-3">{brief.title}</h3>
                <p className="text-sm text-muted-foreground mb-4">{brief.problem_statement}</p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {brief.tech_stack.map((skill) => (
                    <Badge key={skill} variant="secondary" className="text-xs">{skill}</Badge>
                  ))}
                </div>
                <div className="grid gap-4 md:grid-cols-2 text-sm">
                  <div>
                    <p className="font-medium mb-2">Deliverables</p>
                    <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                      {brief.deliverables.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium mb-2">README sections</p>
                    <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                      {brief.readme_template.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {receipt && (
              <div className="card-clean p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Check className="h-5 w-5 text-emerald-500" />
                  <h3 className="text-base font-semibold">Skill Receipt</h3>
                </div>
                <p className="text-sm text-muted-foreground">
                  {receipt.project_title} — Score: {receipt.verification_score}/100 ({receipt.verification_level})
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === "skills" && (
          <div className="card-clean p-6">
            <h3 className="text-base font-semibold mb-4">Verified Skills</h3>
            <div className="flex flex-wrap gap-2">
              {["Python", "FastAPI", "LangChain", "RAG", "PostgreSQL", "Docker", "AWS", "PyTorch", "React", "TypeScript"].map((skill) => (
                <span key={skill} className="inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-sm font-medium">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
