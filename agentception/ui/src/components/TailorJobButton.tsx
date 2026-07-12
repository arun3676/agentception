import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Sparkles } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface TailorJobButtonProps {
  jobUrl: string;
  jobSnippet?: string;
  jobTitle?: string;
  company?: string;
  resumeId?: string | null; // Supabase resume ID
  resumeToken?: string | null; // Backend token (fallback)
  runId?: string | null;
}

export const TailorJobButton = ({ 
  jobUrl, 
  jobSnippet, 
  jobTitle,
  company,
  resumeId,
  resumeToken,
}: TailorJobButtonProps) => {
  const navigate = useNavigate();

  const handleTailor = () => {
    // Navigate to tailor page with job data + resume token from homepage
    navigate("/tailor-resume", {
      state: {
        jobUrl,
        jobSnippet,
        jobTitle,
        company,
        resumeId,
        resumeToken,
      },
    });
  };

  return (
    <Button onClick={handleTailor} className="gap-2 rounded-2xl">
      <Sparkles className="h-4 w-4" />
      Tailor for this job
    </Button>
  );
};

