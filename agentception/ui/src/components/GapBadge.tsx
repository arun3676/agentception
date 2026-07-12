import { Badge } from "@/components/ui/badge";
import { Zap, AlertTriangle, Target } from "lucide-react";

interface GapBadgeProps {
  type: "skills" | "framing" | "ready";
}

export default function GapBadge({ type }: GapBadgeProps) {
  switch (type) {
    case "ready":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 hover:bg-green-200">
          <Zap className="h-3 w-3 mr-1" />
          Ready to Apply
        </Badge>
      );
    case "framing":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 hover:bg-yellow-200">
          <AlertTriangle className="h-3 w-3 mr-1" />
          Framing Issue
        </Badge>
      );
    case "skills":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 hover:bg-red-200">
          <Target className="h-3 w-3 mr-1" />
          Skills Gap
        </Badge>
      );
    default:
      return <Badge variant="outline">{type}</Badge>;
  }
}
