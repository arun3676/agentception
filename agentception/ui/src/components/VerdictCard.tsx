import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ReactNode } from "react";

interface VerdictCardProps {
  title: string;
  subtitle: string;
  detail: string;
  extra?: string;
  icon?: ReactNode;
  priority?: number;
}

export default function VerdictCard({
  title,
  subtitle,
  detail,
  extra,
  icon,
  priority,
}: VerdictCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="pt-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            {icon && <div className="mt-1">{icon}</div>}
            <div>
              <h4 className="font-semibold text-base">{title}</h4>
              <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
              <p className="text-sm mt-2">{detail}</p>
              {extra && (
                <p className="text-xs italic text-muted-foreground mt-2 border-l-2 border-primary/30 pl-2">
                  "{extra}"
                </p>
              )}
            </div>
          </div>
          {priority !== undefined && (
            <Badge variant="outline" className="shrink-0">
              #{priority}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
