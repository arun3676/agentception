import { useState } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createTrustProfile, type TrustProfile as TrustProfileData } from "@/lib/api";
import { Github, Linkedin, Mail, Globe, Star, ExternalLink, Check } from "lucide-react";

const splitList = (value: string) =>
  value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);

const verifiedSkills = [
  "Python", "FastAPI", "LangChain", "RAG", "PostgreSQL", "Docker", "AWS", "PyTorch",
];

const featuredProjects = [
  {
    title: "RAG PDF Assistant",
    description: "RAG system for document question answering",
    tags: ["Python", "FastAPI"],
  },
  {
    title: "AI Resume Tailor",
    description: "ATS-optimized resume tailoring using LLMs",
    tags: ["Next.js", "OpenAI"],
  },
  {
    title: "Job Trend Analyzer",
    description: "Real-time job market analytics dashboard",
    tags: ["Python", "Streamlit"],
  },
];

export default function TrustProfile() {
  const [username, setUsername] = useState("arun-2026");
  const [name, setName] = useState("Arun Srinivasan");
  const [targetRole, setTargetRole] = useState("AI Engineer");
  const [skills, setSkills] = useState("RAG, FastAPI, React, Evaluation");
  const [profile, setProfile] = useState<TrustProfileData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const handleGenerate = async () => {
    setError(null);
    try {
      const data = await createTrustProfile({
        username,
        name,
        target_role: targetRole,
        verified_skills: splitList(skills),
        learning_weeks_completed: 6,
        skill_receipts: [
          {
            id: "demo_receipt",
            project_title: "RAG proof project",
            skills: splitList(skills),
            github_url: "https://github.com/example/rag-proof",
            deployment_url: "https://rag-proof.example.com",
            verification_score: 86,
            verification_level: "verified",
            proof_signals: { commit_count: 12, checks_passed: true, code_quality_score: 86 },
            resume_bullets: ["Built a RAG proof project with public artifacts."],
            created_at: new Date().toISOString(),
          },
        ],
        applications: [{ status: "phone_screen" }, { status: "applied" }],
        peer_reviews: [{ rating: 5 }],
      });
      setProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate trust profile");
    }
  };

  const displayProfile = profile || {
    name: "Arun Srinivasan",
    target_role: "AI Engineer",
    trust_score: 87,
    trust_label: "Verified",
    verified_skills: verifiedSkills,
    projects: featuredProjects,
    learning_trajectory: { weeks_completed: 6 },
    application_stats: { callback_rate: 0.23 },
    public_url: "agentception.com/u/arun-2026",
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
          {/* Main Content */}
          <div className="space-y-8">
            {/* Profile Header */}
            <div className="card-clean p-8">
              <div className="flex items-start gap-5">
                <div className="h-20 w-20 rounded-full bg-secondary flex items-center justify-center text-2xl font-bold shrink-0">
                  {displayProfile.name?.[0] || "A"}
                </div>
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-bold">{displayProfile.name}</h1>
                  <p className="text-base text-muted-foreground mt-1">
                    {displayProfile.target_role} @ 2026
                  </p>
                  <div className="flex items-center gap-1.5 mt-2 text-sm text-muted-foreground">
                    <Globe className="h-4 w-4" />
                    San Francisco, CA
                  </div>
                  <div className="flex items-center gap-3 mt-4">
                    <Button asChild variant="ghost" size="icon" className="h-9 w-9 rounded-lg" title="GitHub">
                      <a href="https://github.com/example" target="_blank" rel="noopener noreferrer">
                        <Github className="h-4 w-4" />
                      </a>
                    </Button>
                    <Button asChild variant="ghost" size="icon" className="h-9 w-9 rounded-lg" title="LinkedIn">
                      <a href="https://www.linkedin.com" target="_blank" rel="noopener noreferrer">
                        <Linkedin className="h-4 w-4" />
                      </a>
                    </Button>
                    <Button asChild variant="ghost" size="icon" className="h-9 w-9 rounded-lg" title="Email">
                      <a href="mailto:hello@agentception.com">
                        <Mail className="h-4 w-4" />
                      </a>
                    </Button>
                    <Button asChild variant="ghost" size="icon" className="h-9 w-9 rounded-lg" title="Public profile">
                      <a href={`https://${displayProfile.public_url.replace(/^https?:\/\//, "")}`} target="_blank" rel="noopener noreferrer">
                        <Globe className="h-4 w-4" />
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 w-full justify-start gap-3 sm:gap-6 overflow-x-auto whitespace-nowrap">
                {["overview", "projects", "skills", "experience", "activity"].map((tab) => (
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

            {activeTab === "overview" && (
              <div className="space-y-8">
                {/* About + Verified Skills */}
                <div className="grid gap-5 md:grid-cols-2">
                  <div className="card-clean p-6">
                    <h3 className="text-base font-semibold mb-4">About</h3>
                    <p className="text-base text-muted-foreground">
                      Building intelligent systems that solve real-world problems.
                    </p>
                    <ul className="mt-4 space-y-2 text-base text-muted-foreground">
                      <li className="flex items-center gap-2.5">
                        <Check className="h-4 w-4 text-emerald-500" />
                        AI Engineer Focus
                      </li>
                      <li className="flex items-center gap-2.5">
                        <Check className="h-4 w-4 text-emerald-500" />
                        Open to Summer 2026
                      </li>
                      <li className="flex items-center gap-2.5">
                        <Check className="h-4 w-4 text-emerald-500" />
                        GPA: 3.8/4.0
                      </li>
                    </ul>
                  </div>
                  <div className="card-clean p-6">
                    <h3 className="text-base font-semibold mb-4">Verified Skills</h3>
                    <div className="flex flex-wrap gap-2">
                      {verifiedSkills.slice(0, 7).map((skill) => (
                        <span
                          key={skill}
                          className="inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-sm font-medium"
                        >
                          {skill}
                        </span>
                      ))}
                      <span className="inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-sm font-medium text-muted-foreground">
                        +4 more
                      </span>
                    </div>
                  </div>
                </div>

                {/* Featured Projects */}
                <div>
                  <h3 className="text-base font-semibold mb-4">Featured Projects</h3>
                  <div className="grid gap-4 sm:grid-cols-3">
                    {featuredProjects.map((project) => (
                      <div key={project.title} className="card-clean p-5">
                        <div className="h-24 rounded-lg bg-secondary mb-4" />
                        <h4 className="text-base font-semibold">{project.title}</h4>
                        <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {project.tags.map((tag) => (
                            <span key={tag} className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2 mt-3">
                          <Button variant="ghost" size="icon" className="h-7 w-7 rounded">
                            <Github className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7 rounded">
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Generate Form */}
                <div className="card-clean p-6">
                  <h3 className="text-base font-semibold mb-4">Generate Trust Profile</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label className="text-sm">Username</Label>
                      <Input value={username} onChange={(e) => setUsername(e.target.value)} className="h-10 rounded-lg text-sm" />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-sm">Name</Label>
                      <Input value={name} onChange={(e) => setName(e.target.value)} className="h-10 rounded-lg text-sm" />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-sm">Target role</Label>
                      <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} className="h-10 rounded-lg text-sm" />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-sm">Verified skills</Label>
                      <Input value={skills} onChange={(e) => setSkills(e.target.value)} className="h-10 rounded-lg text-sm" />
                    </div>
                  </div>
                  <Button onClick={handleGenerate} size="default" className="mt-4 rounded-lg text-sm">
                    Generate trust profile
                  </Button>
                  {error && <p className="text-sm text-destructive mt-3">{error}</p>}
                </div>
              </div>
            )}

            {activeTab === "projects" && (
              <div>
                <h3 className="text-base font-semibold mb-4">Featured Projects</h3>
                <div className="grid gap-4 sm:grid-cols-3">
                  {featuredProjects.map((project) => (
                    <div key={project.title} className="card-clean p-5">
                      <h4 className="text-base font-semibold">{project.title}</h4>
                      <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {project.tags.map((tag) => (
                          <span key={tag} className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "skills" && (
              <div className="card-clean p-6">
                <h3 className="text-base font-semibold mb-4">Verified Skills</h3>
                <div className="flex flex-wrap gap-2">
                  {displayProfile.verified_skills.map((skill) => (
                    <span key={skill} className="inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-sm font-medium">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "experience" && (
              <div className="card-clean p-6">
                <h3 className="text-base font-semibold mb-3">Experience Signals</h3>
                <p className="text-sm text-muted-foreground">
                  {displayProfile.learning_trajectory.weeks_completed} learning weeks completed with a {Math.round(displayProfile.application_stats.callback_rate * 100)}% callback rate.
                </p>
              </div>
            )}

            {activeTab === "activity" && (
              <div className="card-clean p-6">
                <h3 className="text-base font-semibold mb-3">Recent Activity</h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>Generated trust profile</li>
                  <li>Verified RAG proof project</li>
                  <li>Updated application stats</li>
                </ul>
              </div>
            )}
          </div>

          {/* Right Sidebar */}
          <aside className="space-y-5">
            {/* Trust Score */}
            <div className="card-clean p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted-foreground">Trust Score</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
                  <Check className="h-5 w-5 text-emerald-500" />
                </div>
                <span className="text-4xl font-bold">87</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">Top 15% of students</p>
              <svg className="w-full h-12 mt-3 text-emerald-500" viewBox="0 0 100 20">
                <path
                  d="M0,15 Q10,5 20,12 T40,8 T60,14 T80,6 T100,10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
              </svg>
            </div>

            {/* Peer Interview Score */}
            <div className="card-clean p-6">
              <p className="text-sm text-muted-foreground mb-3">Peer Interview Score</p>
              <div className="flex items-center gap-2">
                <span className="text-3xl font-bold">4.6</span>
                <span className="text-sm text-muted-foreground">/5.0</span>
              </div>
              <div className="flex gap-1 mt-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <Star
                    key={star}
                    className={`h-4 w-4 ${star <= 4 ? "fill-amber-400 text-amber-400" : "fill-amber-200 text-amber-200"}`}
                  />
                ))}
              </div>
            </div>

            {/* Applications */}
            <div className="card-clean p-6">
              <p className="text-sm text-muted-foreground mb-2">Applications</p>
              <p className="text-3xl font-bold">42</p>
              <p className="text-xs text-muted-foreground mt-1">23% callback rate</p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
