import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { TopNav } from "@/components/TopNav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Target,
  Zap,
  AlertTriangle,
  Mail,
  BookOpen,
  PenTool,
  Loader2,
  ArrowRight,
  Calendar,
} from "lucide-react";
import VerdictCard from "@/components/VerdictCard";

const BACKEND = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

interface ActionData {
  action_type: "apply_now" | "reframe_bullet" | "learn_module";
  data: any;
  deadline_days: number;
  summary: string;
  action_id?: string;
}

export default function OneThing() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const auditId = searchParams.get("audit_id");

  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<ActionData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchOneThing = useCallback(async () => {
    if (!auditId) return;
    setLoading(true);
    setError(null);

    try {
      const resp = await fetch(`${BACKEND}/audit/${auditId}/one-thing`, {
        method: "POST",
      });
      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || "Failed to get action");
      }
      const data = await resp.json();
      setAction(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [auditId]);

  useEffect(() => {
    if (auditId) fetchOneThing();
  }, [auditId, fetchOneThing]);

  const actionIcon = (type: string) => {
    switch (type) {
      case "apply_now":
        return <Mail className="h-6 w-6 text-green-500" />;
      case "reframe_bullet":
        return <PenTool className="h-6 w-6 text-yellow-500" />;
      case "learn_module":
        return <BookOpen className="h-6 w-6 text-blue-500" />;
      default:
        return <Target className="h-6 w-6" />;
    }
  };

  const actionColor = (type: string) => {
    switch (type) {
      case "apply_now":
        return "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800";
      case "reframe_bullet":
        return "bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800";
      case "learn_module":
        return "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800";
      default:
        return "";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="app-main">
        <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Target className="h-8 w-8 text-primary" />
            Your One Thing
          </h1>
          <p className="text-muted-foreground mt-2">
            Based on your audit, here's the single most impactful action to take right now.
          </p>
        </div>

        {loading && (
          <Card>
            <CardContent className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary mr-3" />
              <span className="text-lg">Deciding your best next move...</span>
            </CardContent>
          </Card>
        )}

        {error && (
          <Card className="border-destructive">
            <CardContent className="py-6">
              <p className="text-destructive">{error}</p>
              <Button variant="outline" className="mt-4" onClick={() => navigate("/audit")}>
                Go back to Audit
              </Button>
            </CardContent>
          </Card>
        )}

        {action && (
          <div className="space-y-6">
            {/* Main Action Card */}
            <Card className={`border-2 ${actionColor(action.action_type)}`}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-2xl">
                    {actionIcon(action.action_type)}
                    {action.summary}
                  </CardTitle>
                  <Badge variant="outline" className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {action.deadline_days} days
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <Separator className="mb-6" />

                {/* Apply Now: Show company cards */}
                {action.action_type === "apply_now" && action.data?.companies && (
                  <div className="space-y-4">
                    {action.data.companies.map((company: any, i: number) => (
                      <VerdictCard
                        key={i}
                        title={company.name}
                        subtitle={company.match_reason}
                        detail={company.angle}
                        extra={company.email_hook}
                        icon={<Mail className="h-4 w-4" />}
                        priority={company.priority}
                      />
                    ))}
                  </div>
                )}

                {/* Reframe Bullets: Side-by-side comparison */}
                {action.action_type === "reframe_bullet" &&
                  action.data?.reframed_bullets && (
                    <div className="space-y-4">
                      {action.data.reframed_bullets.map((bullet: any, i: number) => (
                        <div key={i} className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-red-50 dark:bg-red-950/20 rounded-md">
                            <p className="text-xs font-semibold text-red-600 mb-1">
                              ORIGINAL
                            </p>
                            <p className="text-sm">{bullet.original}</p>
                          </div>
                          <div className="p-4 bg-green-50 dark:bg-green-950/20 rounded-md">
                            <p className="text-xs font-semibold text-green-600 mb-1">
                              REWRITTEN
                            </p>
                            <p className="text-sm">{bullet.rewritten}</p>
                            <p className="text-xs text-muted-foreground mt-2">
                              {bullet.why_better}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                {/* Learning Module: Daily plan with checkboxes */}
                {action.action_type === "learn_module" && action.data && (
                  <div className="space-y-4">
                    {action.data.module_title && (
                      <h3 className="text-xl font-semibold">
                        {action.data.module_title}
                      </h3>
                    )}

                    {action.data.project && (
                      <Card className="bg-accent/50">
                        <CardContent className="pt-4">
                          <p className="font-semibold">
                            Project: {action.data.project.title}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {action.data.project.description}
                          </p>
                          {action.data.project.tech_stack && (
                            <div className="flex gap-1 mt-2 flex-wrap">
                              {action.data.project.tech_stack.map(
                                (t: string, i: number) => (
                                  <Badge key={i} variant="secondary" className="text-xs">
                                    {t}
                                  </Badge>
                                )
                              )}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {action.data.daily_plan?.map((day: any, i: number) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-3 rounded-md hover:bg-accent/50 transition-colors"
                      >
                        <Checkbox id={`day-${day.day}`} />
                        <div className="flex-1">
                          <label
                            htmlFor={`day-${day.day}`}
                            className="font-medium cursor-pointer"
                          >
                            Day {day.day}: {day.focus}
                          </label>
                          <ul className="text-sm text-muted-foreground mt-1 list-disc list-inside">
                            {day.tasks?.map((task: string, j: number) => (
                              <li key={j}>{task}</li>
                            ))}
                          </ul>
                          {day.hours && (
                            <Badge variant="outline" className="mt-1 text-xs">
                              ~{day.hours}h
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Navigation */}
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => navigate("/audit")}>
                Back to Audit
              </Button>
              <Button onClick={() => navigate("/verdict-loop")} className="flex-1">
                Track Your Outcomes
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {!auditId && !loading && (
          <Card>
            <CardContent className="py-12 text-center">
              <AlertTriangle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold">No Audit Selected</h3>
              <p className="text-muted-foreground mt-2">
                Run an audit first to get your personalised action plan.
              </p>
              <Button className="mt-4" onClick={() => navigate("/audit")}>
                Start an Audit
              </Button>
            </CardContent>
          </Card>
        )}
        </div>
      </main>
    </div>
  );
}
