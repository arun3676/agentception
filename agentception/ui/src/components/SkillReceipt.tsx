import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { SkillReceipt as SkillReceiptData } from "@/lib/api";

interface SkillReceiptProps {
  receipt: SkillReceiptData;
}

export function SkillReceipt({ receipt }: SkillReceiptProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>{receipt.project_title}</CardTitle>
            <CardDescription>Verification level: {receipt.verification_level.replaceAll("_", " ")}</CardDescription>
          </div>
          <Badge variant={receipt.verification_level === "verified" ? "default" : "secondary"}>
            {receipt.verification_score}/100
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={receipt.verification_score} />
        <div className="flex flex-wrap gap-2">
          {receipt.skills.map((skill) => (
            <Badge key={skill} variant="outline">
              {skill}
            </Badge>
          ))}
        </div>
        <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-3">
          <span>{receipt.proof_signals.commit_count} commits</span>
          <span>{receipt.proof_signals.checks_passed ? "Checks passed" : "Checks pending"}</span>
          <span>{receipt.proof_signals.code_quality_score}/100 quality</span>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">Resume bullets</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {receipt.resume_bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
