import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiKeyHealth, type ApiKeyHealthResponse } from "@/lib/api";

export default function SystemHealth() {
  const [health, setHealth] = useState<ApiKeyHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheck = async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getApiKeyHealth());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check API keys");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
          Back to job search
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>API Key Health</CardTitle>
            <CardDescription>
              Runs minimal live checks against configured providers and reports only status, never secret values.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={handleCheck} disabled={loading}>
              {loading ? "Checking..." : "Check keys"}
            </Button>
            {error && <p className="text-sm text-destructive">{error}</p>}
            {health && (
              <div className="space-y-4">
                <div className="rounded-lg border p-4 text-sm">
                  <p className="font-medium">Cheap model policy</p>
                  <p className="text-muted-foreground">Chat: {health.cheap_model_policy.chat_primary}</p>
                  <p className="text-muted-foreground">Fallback: {health.cheap_model_policy.openai_fallback}</p>
                  <p className="text-muted-foreground">Embeddings: {health.cheap_model_policy.embedding}</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {Object.entries(health.checks).map(([provider, check]) => (
                    <div key={provider} className="rounded-lg border p-4">
                      <div className="flex items-center justify-between">
                        <p className="font-medium capitalize">{provider}</p>
                        <Badge variant={check.ok ? "default" : check.configured ? "secondary" : "outline"}>
                          {check.status}
                        </Badge>
                      </div>
                      {check.status_code && <p className="mt-2 text-sm text-muted-foreground">HTTP {check.status_code}</p>}
                      {check.error && <p className="mt-2 text-sm text-muted-foreground">{check.error}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
