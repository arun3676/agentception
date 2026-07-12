import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Upload, Brain, Target, Shield, Zap, AlertTriangle } from "lucide-react";
import GapBadge from "@/components/GapBadge";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const DEFAULT_ROLES = [
  "AI Engineer",
  "ML Engineer",
  "Data Scientist",
  "Full-Stack Developer",
  "Backend Engineer",
  "Frontend Engineer",
  "DevOps Engineer",
  "Data Engineer",
  "Product Manager",
  "Cloud Architect",
  "Cybersecurity Analyst",
  "Mobile Developer",
];

interface AuditResult {
  audit_id: string;
  run_id: string;
  verdict_text: string;
  gap_type: "skills" | "framing" | "ready";
  gap_details: {
    gaps: Array<{ skill: string; jd_frequency: number; resume_evidence: string | null }>;
    undefendable_claims: Array<{ bullet: string; reason: string }>;
  };
  strengths: Array<{ skill: string; evidence: string }>;
  percentile: number;
  target_role: string;
  jd_count: number;
}

export default function Audit() {
  const navigate = useNavigate();
  const [role, setRole] = useState("");
  const [city, setCity] = useState("San Francisco");
  const [resumeToken, setResumeToken] = useState<string | null>(null);
  const [resumeFile, setResumeFile] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [result, setResult] = useState<AuditResult | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>(DEFAULT_ROLES);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch available roles from backend
  useEffect(() => {
    fetch(`${BACKEND}/api/roles`)
      .then((res) => res.json())
      .then((data) => {
        if (data.roles && data.roles.length > 0) {
          setRoles(data.roles);
        }
      })
      .catch(() => {
        // fallback to defaults
      });
  }, []);

  // Auto-scroll status messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [statusMessages]);

  // SSE listener
  useEffect(() => {
    if (!runId || !isRunning) return;

    const es = new EventSource(`${BACKEND}/timeline/${runId}`);
    let msgCount = 0;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "heartbeat") return;
        if (data.message) {
          msgCount++;
          setStatusMessages((prev) => [...prev, data.message]);
          setProgress(Math.min(95, msgCount * 8));
        }
      } catch {
        // ignore parse errors
      }
    };

    es.addEventListener("end", () => {
      es.close();
      setProgress(100);
      // Fetch the result
      fetch(`${BACKEND}/audit/${runId}/result`)
        .then((r) => r.json())
        .then((data) => {
          setResult(data);
          setIsRunning(false);
        })
        .catch(() => setIsRunning(false));
    });

    es.onerror = () => {
      es.close();
      setIsRunning(false);
    };

    return () => es.close();
  }, [runId, isRunning]);

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setResumeFile(file.name);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const resp = await fetch(`${BACKEND}/upload/resume`, { method: "POST", body: formData });
      const data = await resp.json();
      setResumeToken(data.token);
    } catch (err) {
      console.error("Resume upload failed:", err);
    }
  };

  const startAudit = async () => {
    if (!role) return;
    setIsRunning(true);
    setResult(null);
    setStatusMessages([]);
    setProgress(0);

    try {
      const resp = await fetch(`${BACKEND}/audit/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_role: role,
          resume_token: resumeToken,
          city,
        }),
      });
      const data = await resp.json();
      setRunId(data.run_id);
    } catch (err) {
      console.error("Audit start failed:", err);
      setIsRunning(false);
    }
  };

  const gapIcon = (type: string) => {
    switch (type) {
      case "ready":
        return <Zap className="h-5 w-5 text-green-500" />;
      case "framing":
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      default:
        return <Target className="h-5 w-5 text-red-500" />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Brain className="h-8 w-8 text-primary" />
            Career Readiness Audit
          </h1>
          <p className="text-muted-foreground mt-2">
            Upload your resume and pick a target role. We'll compare you against 20+
            real job descriptions and tell you exactly where you stand.
          </p>
        </div>

        {/* Input Section */}
        {!isRunning && !result && (
          <Card>
            <CardHeader>
              <CardTitle>Start Your Audit</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Resume Upload */}
              <div className="space-y-2">
                <Label htmlFor="resume">Resume (PDF)</Label>
                <div className="flex items-center gap-3">
                  <label
                    htmlFor="resume-input"
                    className="flex items-center gap-2 px-4 py-2 border rounded-md cursor-pointer hover:bg-accent transition-colors"
                  >
                    <Upload className="h-4 w-4" />
                    {resumeFile || "Choose file"}
                  </label>
                  <input
                    id="resume-input"
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={handleResumeUpload}
                  />
                  {resumeToken && (
                    <Badge variant="secondary" className="text-green-600">
                      Uploaded
                    </Badge>
                  )}
                </div>
              </div>

              {/* Role Picker */}
              <div className="space-y-2">
                <Label>Target Role</Label>
                <Select value={role} onValueChange={setRole}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select your target role" />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* City */}
              <div className="space-y-2">
                <Label>City / Market</Label>
                <Input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="San Francisco"
                />
              </div>

              <Button
                size="lg"
                className="w-full"
                onClick={startAudit}
                disabled={!role}
              >
                <Shield className="mr-2 h-5 w-5" />
                Run Readiness Audit
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Progress Section */}
        {isRunning && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5 animate-pulse text-primary" />
                Audit in Progress...
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={progress} className="h-3" />
              <div className="max-h-60 overflow-y-auto space-y-1 text-sm font-mono bg-muted/50 p-3 rounded-md">
                {statusMessages.map((msg, i) => (
                  <div key={i} className="text-muted-foreground">
                    {msg}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results Section */}
        {result && (
          <div className="space-y-6">
            {/* Summary Card */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    {gapIcon(result.gap_type)}
                    Audit Result
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <GapBadge type={result.gap_type} />
                    <Badge variant="outline">
                      Percentile: {result.percentile}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-2">
                  Compared against {result.jd_count} real {result.target_role} job descriptions
                </p>
                <Separator className="my-4" />
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {result.verdict_text.split("\n").map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Gaps */}
            {result.gap_details?.gaps?.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-red-500 flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    What's Blocking You ({result.gap_details.gaps.length} gaps)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.gap_details.gaps.map((gap, i) => (
                      <div
                        key={i}
                        className="flex items-start justify-between p-3 bg-red-50 dark:bg-red-950/20 rounded-md"
                      >
                        <div>
                          <span className="font-semibold">{gap.skill}</span>
                          <p className="text-sm text-muted-foreground mt-1">
                            {gap.resume_evidence || "No evidence found in resume"}
                          </p>
                        </div>
                        <Badge variant="destructive">
                          {gap.jd_frequency} JDs
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Strengths */}
            {result.strengths?.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-green-600 flex items-center gap-2">
                    <Zap className="h-5 w-5" />
                    Your Strengths
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.strengths.map((s, i) => (
                      <div
                        key={i}
                        className="p-3 bg-green-50 dark:bg-green-950/20 rounded-md"
                      >
                        <span className="font-semibold">{s.skill}</span>
                        <p className="text-sm text-muted-foreground mt-1">
                          {s.evidence}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              <Button
                onClick={() =>
                  navigate(`/one-thing?audit_id=${result.audit_id}`)
                }
                className="flex-1"
              >
                <Target className="mr-2 h-4 w-4" />
                Get Your One Thing
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setResult(null);
                  setRunId(null);
                  setStatusMessages([]);
                  setProgress(0);
                }}
              >
                Run Another Audit
              </Button>
            </div>
          </div>
        )}
        </div>
      </main>
    </div>
  );
}
