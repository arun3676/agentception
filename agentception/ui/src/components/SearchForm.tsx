import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Upload } from "lucide-react";
import { uploadResume, searchCompanies } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

interface SearchFormProps {
  onSearchStart: (runId: string, usedResume: boolean) => void;
  onResumeUploaded: (
    token: string,
    insights?: ResumeInsights,
    textPreview?: string,
    fileName?: string,
    structured?: import("@/lib/api").ResumeStructured
  ) => void;
}

interface ResumeInsights {
  role?: string;
  skills?: string[];
  skills_flat?: string[];
  [key: string]: unknown;
}

const ROLES = [
  "AI Engineer",
  "Full-Stack Developer",
  "Java Developer",
  "Data Analyst",
  "Data Engineer",
  "Machine Learning Engineer",
  "DevOps Engineer",
  "Cloud Engineer",
  "Cybersecurity Engineer",
  "Product Manager",
  "Software Architect",
  "Backend Engineer",
  "Frontend Engineer",
  "Mobile Developer",
  "Blockchain Developer",
];

export const SearchForm = ({ onSearchStart, onResumeUploaded }: SearchFormProps) => {
  const [location, setLocation] = useState("San Francisco, CA");
  const [role, setRole] = useState<string>("");
  const [resumeToken, setResumeToken] = useState<string | null>(null);
  const [resumeFileName, setResumeFileName] = useState<string | null>(null);
  const [resumeInsights, setResumeInsights] = useState<ResumeInsights | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "application/pdf") {
      toast({
        title: "Invalid file type",
        description: "Please upload a PDF file",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);
    try {
      // Upload to backend for search (backend extracts insights for matching)
      const result = await uploadResume(file);
      setResumeToken(result.token);
      setResumeFileName(file.name);
      setResumeInsights(result.insights || null);
      onResumeUploaded(result.token, result.insights, result.text_preview, file.name, result.structured);
      
      toast({
        title: "Resume uploaded",
        description: `Uploaded ${file.name} (${result.chars} characters). Ready for search.`,
      });
    } catch (error) {
      console.error("Resume upload failed:", error);
      toast({
        title: "Upload failed",
        description: "Failed to upload resume. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleSearch = async () => {
    if (!location.trim()) {
      toast({
        title: "Location required",
        description: "Please enter a location",
        variant: "destructive",
      });
      return;
    }

    setIsSearching(true);
    try {
      const result = await searchCompanies({
        city: location,
        role: role || undefined,
        resumeToken: resumeToken || undefined,
        depth: "standard",
        offset: 0,
        limit: 5,
      });
      onSearchStart(result.run_id, Boolean(resumeToken));
    } catch (error) {
      console.error("Search failed:", error);
      toast({
        title: "Search failed",
        description: "Failed to start job search. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Location</label>
          <Input
            placeholder="e.g., San Francisco, CA"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="h-12 rounded-2xl bg-background/80"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Desired Role (optional)</label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="h-12 rounded-2xl bg-background/80">
              <SelectValue placeholder="Role will be detected from resume" />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">Resume (optional, improves search)</label>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button variant="outline" className="h-12 justify-center gap-2 rounded-2xl sm:w-auto" disabled={isUploading} asChild>
            <label>
              <Upload className="h-4 w-4" />
              {isUploading ? "Uploading..." : "Choose File"}
              <input
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </Button>
          <span className="min-w-0 truncate text-sm text-muted-foreground">
            {resumeFileName || "No file chosen"}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Upload here improves search. Resume tailoring will confirm the resume in its guided flow.
        </p>
        {resumeInsights && (
          <div className="mt-2 rounded-2xl border border-primary/30 bg-primary/10 p-4 text-sm text-foreground">
            <p className="font-medium text-primary">Search enhanced with your resume</p>
            <p className="text-muted-foreground">
              {(() => {
                const skillsArr = Array.isArray(resumeInsights?.skills_flat)
                  ? resumeInsights.skills_flat
                  : Array.isArray(resumeInsights?.skills)
                  ? resumeInsights.skills
                  : [];
                const skillsText = skillsArr.slice(0, 5).join(", ");
                return `Role: ${resumeInsights.role || "Detected from resume"} • Skills: ${skillsText || "Key skills detected"}`;
              })()}
            </p>
          </div>
        )}
      </div>

      <div className="flex gap-3 pt-2">
        <Button onClick={handleSearch} disabled={isSearching || isUploading} className="h-12 w-full rounded-2xl sm:w-auto">
          {isSearching ? "Searching..." : "Search Jobs"}
        </Button>
      </div>
    </div>
  );
};
