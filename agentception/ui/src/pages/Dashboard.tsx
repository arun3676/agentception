import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listLearningPaths, type LearningPath } from "@/lib/api";
import {
  Share2,
  Check,
  Lock,
  Minus,
  ChevronRight,
  Github,
  ExternalLink,
  Play,
  Plus,
} from "lucide-react";

const CircularProgress = ({ value, size = 96 }: { value: number; size?: number }) => {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (value / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          className="text-muted"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="text-emerald-500 transition-all duration-500"
        />
      </svg>
      <span className="absolute text-2xl font-semibold">{value}%</span>
    </div>
  );
};

interface WeekModule {
  id: string;
  week: string;
  title: string;
  description: string;
  status: "completed" | "active" | "locked";
}

const weeks: WeekModule[] = [
  { id: "w1", week: "W1", title: "Foundations", description: "Python, APIs, Git, Docker", status: "completed" },
  { id: "w2", week: "W2", title: "LLM Basics", description: "Prompts, Tokens, OpenAI API", status: "completed" },
  { id: "w3", week: "W3", title: "Embeddings", description: "Vectors, Similarity, ChromaDB", status: "completed" },
  { id: "w4", week: "W4", title: "RAG Pipeline", description: "Build a full RAG application", status: "active" },
  { id: "w5", week: "W5", title: "Evaluation", description: "Evaluate RAG quality", status: "locked" },
  { id: "w6", week: "W6", title: "Agentic Apps", description: "Tools, Functions, Agents", status: "locked" },
];

const projectBrief = {
  title: "Build a RAG QA System",
  description: "Create a RAG system that can answer questions from PDF docs.",
  tags: ["Python", "FastAPI", "LangChain", "Chroma"],
  checklist: [
    "Ingest PDFs",
    "Chunk & Embed",
    "Build Retriever",
    "Create QA Chain",
    "Deploy API",
  ],
  deliverables: [
    { label: "Live API URL", icon: ExternalLink },
    { label: "GitHub Repository", icon: Github },
    { label: "Demo Video (2 min)", icon: Play },
  ],
};

const Dashboard = () => {
  const [activeWeek, setActiveWeek] = useState("w4");
  const [activeTab, setActiveTab] = useState("roadmap");
  const [savedPaths, setSavedPaths] = useState<Array<{ id: string; title: string; topic: string; expertise_level: string; created_at: string }>>([]);

  useEffect(() => {
    loadSavedPaths();
  }, []);

  const loadSavedPaths = async () => {
    try {
      const data = await listLearningPaths();
      setSavedPaths(data.paths || []);
    } catch {
      setSavedPaths([]);
    }
  };

  const currentWeek = weeks.find((w) => w.id === activeWeek);

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Roadmap</h1>
            <p className="text-base text-muted-foreground mt-1">12-week plan to become an AI Engineer</p>
          </div>
          <Button asChild variant="outline" size="sm" className="gap-2 rounded-lg text-sm w-full sm:w-auto">
            <Link to="/profile">
              <Share2 className="h-4 w-4" />
              Share Roadmap
            </Link>
          </Button>
        </div>

        {/* Learning Path CTA */}
        {savedPaths.length === 0 && (
          <div className="card-clean p-6 mb-6 flex items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold">No active learning path</h3>
              <p className="text-sm text-muted-foreground">Generate a custom AI-first learning path tailored to your goals.</p>
            </div>
            <Link to="/learning-paths">
              <Button size="default" className="gap-2 rounded-lg text-sm">
                <Plus className="h-4 w-4" />
                Generate path
              </Button>
            </Link>
          </div>
        )}

        {savedPaths.length > 0 && (
          <div className="card-clean p-6 mb-6">
            <h3 className="text-base font-semibold mb-3">Your Learning Paths</h3>
            <div className="space-y-2">
              {savedPaths.slice(0, 3).map((p) => (
                <Link
                  key={p.id}
                  to={`/learning-paths?topic=${encodeURIComponent(p.topic)}`}
                  className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-secondary/50 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium">{p.title}</p>
                    <p className="text-xs text-muted-foreground">{p.topic} · {p.expertise_level}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
            <Link to="/learning-paths">
              <Button variant="ghost" size="sm" className="mt-3 text-sm rounded-lg">
                View all paths
              </Button>
            </Link>
          </div>
        )}

        {/* Top Cards */}
        <div className="grid gap-5 lg:grid-cols-2 mb-8">
          {/* Current Week Card */}
          <div className="card-clean p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-sm text-muted-foreground mb-2">Week 4 of 12</p>
                <h2 className="text-xl font-semibold">RAG Pipeline Build</h2>
                <p className="text-base text-muted-foreground mt-2">
                  Build a production-ready RAG system with FastAPI, LangChain and Vector DB.
                </p>
                <div className="mt-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">60% Complete</span>
                  </div>
                  <Progress value={60} className="h-2" />
                </div>
              </div>
              <Button asChild variant="ghost" size="sm" className="gap-1 text-sm rounded-lg shrink-0 ml-4">
                <Link to="/learning-paths?topic=RAG%20Pipeline">
                  View Week
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>

          {/* This Week's Progress */}
          <div className="card-clean p-6">
            <h3 className="text-base font-semibold mb-5">This Week's Progress</h3>
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 sm:gap-8">
              <CircularProgress value={60} />
              <div className="flex-1 space-y-4">
                {[
                  { label: "Learn", value: "3/4" },
                  { label: "Project", value: "2/3" },
                  { label: "Quiz", value: "4/5" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between text-base">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-8">
          <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 w-full justify-start gap-4 sm:gap-8 overflow-x-auto whitespace-nowrap">
            {["roadmap", "skills", "resources"].map((tab) => (
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

        {/* Content */}
        {activeTab === "skills" && (
          <div className="card-clean p-6">
            <h3 className="text-base font-semibold mb-4">Skills in progress</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {projectBrief.tags.map((skill) => (
                <div key={skill} className="rounded-lg border border-border p-4">
                  <p className="text-sm font-medium">{skill}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Mapped to this week's project proof.</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "resources" && (
          <div className="card-clean p-6">
            <h3 className="text-base font-semibold mb-4">Recommended resources</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {["RAG Architecture", "FastAPI Deployment", "Vector Search Evaluation", "Recruiter Proof README"].map((topic) => (
                <Link
                  key={topic}
                  to={`/resources?topic=${encodeURIComponent(topic)}`}
                  className="flex items-center justify-between rounded-lg border border-border p-4 hover:bg-secondary/50 transition-colors"
                >
                  <span className="text-sm font-medium">{topic}</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
          </div>
        )}

        {activeTab === "roadmap" && (
        <div className="grid gap-6 md:grid-cols-[1fr_340px] lg:grid-cols-[1fr_420px]">
          {/* Weekly Modules */}
          <div className="space-y-3">
            {weeks.map((week) => {
              const isActive = week.id === activeWeek;
              return (
                <button
                  key={week.id}
                  onClick={() => week.status !== "locked" && setActiveWeek(week.id)}
                  className={`w-full text-left card-clean p-5 transition-colors ${
                    week.status === "locked" ? "opacity-60 cursor-not-allowed" : "hover:bg-accent/5"
                  } ${isActive ? "ring-1 ring-border" : ""}`}
                >
                  <div className="flex items-center gap-5">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-medium ${
                        week.status === "completed"
                          ? "bg-emerald-50 text-emerald-600"
                          : week.status === "active"
                          ? "bg-foreground text-background"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {week.status === "completed" ? (
                        <Check className="h-5 w-5" />
                      ) : week.status === "locked" ? (
                        <Lock className="h-4 w-4" />
                      ) : (
                        week.week
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-base font-medium">{week.title}</p>
                      <p className="text-sm text-muted-foreground">{week.description}</p>
                    </div>
                    {week.status === "active" ? (
                      <Minus className="h-5 w-5 text-muted-foreground" />
                    ) : week.status === "locked" ? (
                      <Lock className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <Check className="h-5 w-5 text-emerald-500" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Right Panel - Project Brief */}
          {currentWeek && currentWeek.status === "active" && (
            <div className="space-y-5">
              {/* Project Brief */}
              <div className="card-clean p-6">
                <p className="text-sm text-muted-foreground mb-3">Project Brief</p>
                <h3 className="text-lg font-semibold">{projectBrief.title}</h3>
                <p className="text-base text-muted-foreground mt-2">{projectBrief.description}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  {projectBrief.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-sm font-medium"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <ul className="mt-5 space-y-3">
                  {projectBrief.checklist.map((item) => (
                    <li key={item} className="flex items-center gap-3 text-base">
                      <Check className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
                <Button asChild variant="ghost" size="sm" className="gap-1 mt-5 text-sm rounded-lg">
                  <Link to="/portfolio">
                    View Full Brief
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>

              {/* Deliverables */}
              <div className="card-clean p-6">
                <p className="text-sm text-muted-foreground mb-4">Deliverables</p>
                <ul className="space-y-3">
                  {projectBrief.deliverables.map((item) => (
                    <li key={item.label} className="flex items-center gap-3 text-base">
                      <item.icon className="h-5 w-5 text-muted-foreground shrink-0" />
                      <span>{item.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
