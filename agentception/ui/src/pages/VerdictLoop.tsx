import { useState, useEffect, useCallback } from "react";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BarChart3,
  Plus,
  TrendingUp,
  Ghost,
  XCircle,
  Phone,
  Building2,
  Trophy,
  Loader2,
} from "lucide-react";
import OutcomeTimeline from "@/components/OutcomeTimeline";
import { AuthRequiredError, getOutcomePatterns, logOutcome as logOutcomeApi } from "@/lib/api";

const OUTCOMES = [
  { value: "ghosted", label: "Ghosted", icon: Ghost, color: "text-gray-400" },
  { value: "rejected", label: "Rejected", icon: XCircle, color: "text-red-500" },
  { value: "screen", label: "Screen", icon: Phone, color: "text-yellow-500" },
  { value: "onsite", label: "Onsite", icon: Building2, color: "text-blue-500" },
  { value: "offer", label: "Offer", icon: Trophy, color: "text-green-500" },
];

interface PatternData {
  ready: boolean;
  reason?: string;
  outcomes_count: number;
  stats?: Record<string, number>;
  callback_rate?: number;
  ghost_rate?: number;
  insight?: string;
  outcomes?: any[];
}

export default function VerdictLoop() {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [outcome, setOutcome] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [patterns, setPatterns] = useState<PatternData | null>(null);
  const [loadingPatterns, setLoadingPatterns] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  // The owner comes from the verified JWT, server-side. This used to be
  // `VITE_SUPABASE_DEFAULT_USER_ID || "demo-user"` sent as a query param — a
  // browser-supplied owner, so anyone could read anyone's outcomes.
  const fetchPatterns = useCallback(async () => {
    setLoadingPatterns(true);
    try {
      setPatterns(await getOutcomePatterns());
    } catch (err) {
      console.error("Failed to load patterns:", err);
    } finally {
      setLoadingPatterns(false);
    }
  }, []);

  useEffect(() => {
    fetchPatterns();
  }, [fetchPatterns]);

  const logOutcome = async () => {
    if (!company || !role || !outcome) return;
    setSubmitting(true);
    setSubmitMessage(null);

    try {
      const data = await logOutcomeApi({ company, role, outcome });
      if (data.ok) {
        setSubmitMessage("Outcome logged!");
        setCompany("");
        setRole("");
        setOutcome("");
        fetchPatterns(); // Refresh
      } else {
        setSubmitMessage("Failed to log outcome");
      }
    } catch (err) {
      // Distinguish "you aren't signed in" (retrying is futile) from a real
      // failure (retrying may work) — the same mistake the Track button made.
      setSubmitMessage(
        err instanceof AuthRequiredError
          ? "Sign in to log an outcome."
          : "Network error — please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="h-8 w-8 text-primary" />
            Verdict Loop
          </h1>
          <p className="text-muted-foreground mt-2">
            Log your application outcomes. After 5+ results, we'll show you
            patterns and actionable insights.
          </p>
        </div>

        {/* Log New Outcome */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              Log an Outcome
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Company</Label>
                <Input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="e.g. Stripe"
                />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="e.g. Backend Engineer"
                />
              </div>
              <div className="space-y-2">
                <Label>Outcome</Label>
                <Select value={outcome} onValueChange={setOutcome}>
                  <SelectTrigger>
                    <SelectValue placeholder="What happened?" />
                  </SelectTrigger>
                  <SelectContent>
                    {OUTCOMES.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        <span className="flex items-center gap-2">
                          <o.icon className={`h-4 w-4 ${o.color}`} />
                          {o.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-4">
              <Button onClick={logOutcome} disabled={!company || !role || !outcome || submitting}>
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Log Outcome
              </Button>
              {submitMessage && (
                <span className="text-sm text-muted-foreground">{submitMessage}</span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Patterns & Insights */}
        {loadingPatterns && (
          <Card>
            <CardContent className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              Loading your patterns...
            </CardContent>
          </Card>
        )}

        {patterns && !loadingPatterns && (
          <>
            {!patterns.ready ? (
              <Card>
                <CardContent className="py-8 text-center">
                  <TrendingUp className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold">
                    {patterns.reason || "Keep logging outcomes to unlock insights"}
                  </h3>
                  <p className="text-muted-foreground mt-2">
                    {patterns.outcomes_count > 0
                      ? `You have ${patterns.outcomes_count} outcomes logged.`
                      : "Start by logging your first application outcome above."}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-6">
                {/* Stats Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold">{patterns.outcomes_count}</p>
                      <p className="text-xs text-muted-foreground">Total Apps</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold text-green-600">
                        {patterns.callback_rate}%
                      </p>
                      <p className="text-xs text-muted-foreground">Callback Rate</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold text-gray-400">
                        {patterns.ghost_rate}%
                      </p>
                      <p className="text-xs text-muted-foreground">Ghost Rate</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4 text-center">
                      <p className="text-3xl font-bold text-yellow-500">
                        {patterns.stats?.screen || 0}
                      </p>
                      <p className="text-xs text-muted-foreground">Screens</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Insight */}
                {patterns.insight && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="h-5 w-5 text-primary" />
                        AI Pattern Analysis
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        {patterns.insight.split("\n").map((p, i) => (
                          <p key={i}>{p}</p>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Outcome Timeline */}
                {patterns.outcomes && patterns.outcomes.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Application Timeline</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <OutcomeTimeline outcomes={patterns.outcomes} />
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </>
        )}
        </div>
      </main>
    </div>
  );
}
