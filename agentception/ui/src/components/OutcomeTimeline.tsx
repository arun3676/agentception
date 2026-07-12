import { Ghost, XCircle, Phone, Building2, Trophy } from "lucide-react";

interface Outcome {
  id?: string;
  company: string;
  role: string;
  outcome: string;
  outcome_logged_at?: string;
}

interface OutcomeTimelineProps {
  outcomes: Outcome[];
}

const outcomeConfig: Record<string, { icon: any; color: string; bgColor: string }> = {
  ghosted: { icon: Ghost, color: "text-gray-400", bgColor: "bg-gray-200 dark:bg-gray-700" },
  rejected: { icon: XCircle, color: "text-red-500", bgColor: "bg-red-200 dark:bg-red-900" },
  screen: { icon: Phone, color: "text-yellow-500", bgColor: "bg-yellow-200 dark:bg-yellow-900" },
  onsite: { icon: Building2, color: "text-blue-500", bgColor: "bg-blue-200 dark:bg-blue-900" },
  offer: { icon: Trophy, color: "text-green-500", bgColor: "bg-green-200 dark:bg-green-900" },
};

export default function OutcomeTimeline({ outcomes }: OutcomeTimelineProps) {
  return (
    <div className="space-y-1">
      {/* Dot timeline */}
      <div className="flex gap-1 flex-wrap mb-4">
        {outcomes.map((o, i) => {
          const config = outcomeConfig[o.outcome] || outcomeConfig.ghosted;
          const Icon = config.icon;
          return (
            <div
              key={i}
              className={`w-8 h-8 rounded-full ${config.bgColor} flex items-center justify-center cursor-pointer transition-transform hover:scale-125`}
              title={`${o.company} — ${o.role} → ${o.outcome}`}
            >
              <Icon className={`h-4 w-4 ${config.color}`} />
            </div>
          );
        })}
      </div>

      {/* Detail list */}
      <div className="space-y-2">
        {outcomes.slice(0, 10).map((o, i) => {
          const config = outcomeConfig[o.outcome] || outcomeConfig.ghosted;
          const Icon = config.icon;
          const dateStr = o.outcome_logged_at
            ? new Date(o.outcome_logged_at).toLocaleDateString()
            : "";
          return (
            <div
              key={i}
              className="flex items-center gap-3 p-2 rounded-md hover:bg-accent/50 transition-colors text-sm"
            >
              <div
                className={`w-6 h-6 rounded-full ${config.bgColor} flex items-center justify-center shrink-0`}
              >
                <Icon className={`h-3 w-3 ${config.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <span className="font-medium">{o.company}</span>
                <span className="text-muted-foreground"> — {o.role}</span>
              </div>
              <span className="text-xs text-muted-foreground shrink-0">{dateStr}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
