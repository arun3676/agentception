import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { createLearningPath, listLearningPaths, getLearningPath, type LearningPath } from "@/lib/api";
import { RoadmapTimeline } from "@/components/RoadmapTimeline";
import { Sparkles, ChevronRight, Plus } from "lucide-react";

const LearningPathsPage = () => {
  const [topic, setTopic] = useState("AI Engineer");
  const [expertiseLevel, setExpertiseLevel] = useState("beginner");
  const [learningStyle, setLearningStyle] = useState("project-based");
  const [timeCommitment, setTimeCommitment] = useState("moderate");
  const [goals, setGoals] = useState("Build LLM apps, master RAG");
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState<LearningPath | null>(null);
  const [savedPaths, setSavedPaths] = useState<Array<{ id: string; title: string; topic: string; expertise_level: string; created_at: string }>>([]);
  const [activeTab, setActiveTab] = useState("generate");

  const [searchParams] = useSearchParams();

  useEffect(() => {
    const topicParam = searchParams.get("topic");
    if (topicParam) setTopic(topicParam);
    loadSavedPaths();
  }, [searchParams]);

  const loadSavedPaths = async () => {
    try {
      const data = await listLearningPaths();
      setSavedPaths(data.paths || []);
    } catch {
      setSavedPaths([]);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const result = await createLearningPath({
        topic,
        expertise_level: expertiseLevel,
        learning_style: learningStyle,
        time_commitment: timeCommitment,
        goals: goals.split(",").map((g) => g.trim()).filter(Boolean),
      });
      setPath(result);
      setActiveTab("view");
      loadSavedPaths();
    } finally {
      setLoading(false);
    }
  };

  const handleLoadPath = async (pathId: string) => {
    try {
      const result = await getLearningPath(pathId);
      setPath(result);
      setActiveTab("view");
    } catch {
      // ignore
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Learning Paths</h1>
            <p className="text-base text-muted-foreground mt-1">
              Generate AI-first learning paths that connect concepts, resources, and proof-building projects.
            </p>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-8">
          <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 w-full justify-start gap-4 sm:gap-8 overflow-x-auto whitespace-nowrap">
            {["generate", "saved", "view"].map((tab) => (
              <TabsTrigger
                key={tab}
                value={tab}
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-foreground data-[state=active]:bg-transparent data-[state=active]:shadow-none px-0 py-3 text-base capitalize"
              >
                {tab === "view" && !path ? "Preview" : tab}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {activeTab === "generate" && (
          <div className="space-y-8">
            {/* Saved paths quick access */}
            {savedPaths.length > 0 && (
              <div className="card-clean p-6">
                <h3 className="text-base font-semibold mb-4">Your Saved Paths</h3>
                <div className="space-y-2">
                  {savedPaths.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => handleLoadPath(p.id)}
                      className="w-full text-left flex items-center justify-between rounded-lg border border-border p-4 hover:bg-secondary/50 transition-colors"
                    >
                      <div>
                        <p className="text-sm font-medium">{p.title}</p>
                        <p className="text-xs text-muted-foreground">{p.topic} · {p.expertise_level}</p>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Generate form */}
            <div className="card-clean p-6">
              <h3 className="text-base font-semibold mb-1 flex items-center gap-2.5">
                <Sparkles className="h-5 w-5" />
                Generate a learning path
              </h3>
              <p className="text-sm text-muted-foreground mb-5">Tell us what you want to learn and we will build a path.</p>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-sm">Topic</Label>
                  <Input value={topic} onChange={(e) => setTopic(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Expertise level</Label>
                  <Input value={expertiseLevel} onChange={(e) => setExpertiseLevel(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Learning style</Label>
                  <Input value={learningStyle} onChange={(e) => setLearningStyle(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2">
                  <Label className="text-sm">Time commitment</Label>
                  <Input value={timeCommitment} onChange={(e) => setTimeCommitment(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label className="text-sm">Goals (comma separated)</Label>
                  <Input value={goals} onChange={(e) => setGoals(e.target.value)} className="h-10 rounded-lg text-sm" />
                </div>
              </div>
              <Button onClick={handleGenerate} disabled={loading} size="default" className="mt-5 rounded-lg text-sm">
                {loading ? "Generating..." : "Generate learning path"}
              </Button>
            </div>
          </div>
        )}

        {activeTab === "saved" && (
          <div className="space-y-4">
            {savedPaths.length === 0 ? (
              <div className="card-clean p-8 text-center">
                <p className="text-muted-foreground">No saved learning paths yet.</p>
                <Button variant="outline" size="sm" className="mt-4 rounded-lg text-sm" onClick={() => setActiveTab("generate")}>
                  <Plus className="h-4 w-4 mr-1.5" />
                  Generate your first path
                </Button>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {savedPaths.map((p) => (
                  <div key={p.id} className="card-clean p-5">
                    <h3 className="text-base font-semibold">{p.title}</h3>
                    <p className="text-sm text-muted-foreground mt-1">{p.topic} · {p.expertise_level}</p>
                    <p className="text-xs text-muted-foreground mt-3">Created {new Date(p.created_at).toLocaleDateString()}</p>
                    <Button variant="outline" size="sm" className="mt-4 rounded-lg text-xs" onClick={() => handleLoadPath(p.id)}>
                      View Path
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "view" && path && <RoadmapTimeline path={path} />}
      </main>
    </div>
  );
};

export default LearningPathsPage;
