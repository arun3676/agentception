import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { parseResume, type ParsedResumeData } from "@/lib/supabase";
import { 
  Upload, 
  File, 
  FileText, 
  X, 
  CheckCircle2, 
  Loader2,
  AlertCircle,
  User,
  Briefcase,
  GraduationCap,
  Code
} from "lucide-react";

interface ResumeUploadProps {
  onUploadComplete: (resumeId: string, data: ParsedResumeData, fileName: string, insights?: ResumeInsights) => void;
}

type ResumeInsights = {
  role?: string | null;
  seniority?: string | null;
  skills?: string[];
  domains?: string[];
  years_experience?: number;
};

export const ResumeUpload = ({ onUploadComplete }: ResumeUploadProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [parsedData, setParsedData] = useState<ParsedResumeData | null>(null);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [insights, setInsights] = useState<ResumeInsights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConfirmed, setIsConfirmed] = useState(false);

  const isValidFile = useCallback((file: File): boolean => {
    const validTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ];
    const validExtensions = [".pdf", ".docx"];
    const hasValidType = validTypes.includes(file.type);
    const hasValidExtension = validExtensions.some((ext) =>
      file.name.toLowerCase().endsWith(ext)
    );
    return hasValidType || hasValidExtension;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    setError(null);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      if (isValidFile(droppedFile)) {
        setFile(droppedFile);
      } else {
        setError("Please upload a PDF or DOCX file");
      }
    }
  }, [isValidFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (isValidFile(selectedFile)) {
        setFile(selectedFile);
      } else {
        setError("Please upload a PDF or DOCX file");
      }
    }
  }, [isValidFile]);

  const handleRemoveFile = () => {
    setFile(null);
    setParsedData(null);
    setResumeId(null);
    setInsights(null);
    setIsConfirmed(false);
    setError(null);
    setUploadProgress(0);
  };

  const deriveInsights = (data: ParsedResumeData): ResumeInsights => {
    const roleCandidate = data.experience?.[0]?.position || data.summary || null;
    const skills: string[] = [
      ...(data.skills.technical || []),
      ...(data.skills.languages || []),
      ...(data.skills.industry || []),
    ];
    const textBlob = [
      data.summary,
      data.experience?.map((e) => `${e.position} ${e.description || ""}`).join(" "),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const domainKeywords: Record<string, string[]> = {
      fintech: ["fintech", "bank", "payments", "trading", "financial"],
      healthcare: ["health", "clinical", "patient", "ehr", "fhir"],
      ecommerce: ["ecommerce", "e-commerce", "retail", "marketplace"],
      security: ["security", "infosec", "cyber"],
      ml_ai: ["machine learning", "ml", "ai", "llm", "rag", "genai"],
      data: ["data platform", "etl", "elt", "warehouse", "analytics"],
    };
    const domains: string[] = [];
    Object.entries(domainKeywords).forEach(([domain, kws]) => {
      if (kws.some((kw) => textBlob.includes(kw))) {
        domains.push(domain);
      }
    });
    return {
      role: roleCandidate,
      seniority: null,
      skills: Array.from(new Set(skills)).slice(0, 20),
      domains,
      years_experience: undefined,
    };
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Simulate initial progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 80) {
            clearInterval(progressInterval);
            return 80;
          }
          return prev + 20;
        });
      }, 500);

      const result = await parseResume(file);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      
      // Debug: Log what we received
      const expCount = result.structuredData?.experience?.length || 0
      const skillsCount = result.structuredData?.skills?.technical?.length || 0
      console.log('✅ Resume parse result:', {
        resumeId: result.resumeId,
        experienceCount: expCount,
        skillsCount: skillsCount,
        experienceArray: result.structuredData?.experience,
        skillsObject: result.structuredData?.skills,
        fullStructuredData: result.structuredData,
      })
      
      // Warn if empty
      if (expCount === 0) {
        console.warn('⚠️ Frontend received 0 experience entries')
      }
      if (skillsCount === 0) {
        console.warn('⚠️ Frontend received 0 technical skills')
      }
      const derived = deriveInsights(result.structuredData);
      setResumeId(result.resumeId);
      setParsedData(result.structuredData);
      setInsights(derived);
    } catch (err) {
      console.error("Upload error:", err);
      setError(err instanceof Error ? err.message : "Failed to upload resume");
      setUploadProgress(0);
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = () => {
    if (!file) return <Upload className="h-8 w-8 text-muted-foreground" />;
    if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
      return <File className="h-8 w-8 text-red-500" />;
    }
    return <FileText className="h-8 w-8 text-blue-500" />;
  };

  return (
    <div className="space-y-6">
      {/* Drop Zone */}
      {!file && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-lg p-12 transition-colors cursor-pointer ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50"
          }`}
        >
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={handleFileSelect}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div className="flex flex-col items-center justify-center text-center">
            <div className="p-4 rounded-full bg-muted mb-4">
              <Upload className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="text-lg font-medium text-foreground mb-1">
              Drop your resume here
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              or click to browse
            </p>
            <p className="text-xs text-muted-foreground">
              Supports PDF and DOCX files up to 10MB
            </p>
          </div>
        </div>
      )}

      {/* Selected File Display */}
      {file && !parsedData && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center gap-4 p-4">
            {getFileIcon()}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {formatFileSize(file.size)}
              </p>
            </div>
            {isUploading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleRemoveFile}
                className="shrink-0"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </CardContent>
          
          {/* Upload Progress */}
          {isUploading && (
            <div className="px-4 pb-4">
              <Progress value={uploadProgress} className="h-2" />
              <p className="text-xs text-muted-foreground mt-2">
                {uploadProgress < 30
                  ? "Uploading file..."
                  : uploadProgress < 60
                  ? "Extracting text..."
                  : uploadProgress < 90
                  ? "Parsing resume with AI..."
                  : "Finalizing..."}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* Parsed Resume Preview */}
      {parsedData && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Resume parsed successfully!</span>
          </div>

          {/* Insights Summary */}
          {insights && (
            <Card>
              <CardContent className="p-4 space-y-3">
                <p className="text-sm font-medium">Detected Insights</p>
                <div className="text-sm text-muted-foreground space-y-1">
                  <p><span className="font-medium text-foreground">Role:</span> {insights.role || "Not detected"}</p>
                  {insights.domains && insights.domains.length > 0 && (
                    <p><span className="font-medium text-foreground">Domains:</span> {insights.domains.join(", ")}</p>
                  )}
                  {insights.skills && insights.skills.length > 0 && (
                    <p>
                      <span className="font-medium text-foreground">Key skills:</span>{" "}
                      {insights.skills.slice(0, 8).join(", ")}
                      {insights.skills.length > 8 && ` +${insights.skills.length - 8} more`}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="p-4 space-y-4">
              {/* Contact Info */}
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-full bg-primary/10 text-primary">
                  <User className="h-4 w-4" />
                </div>
                <div>
                  <p className="font-medium">{parsedData.contact.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {[parsedData.contact.email, parsedData.contact.phone]
                      .filter(Boolean)
                      .join(" • ")}
                  </p>
                </div>
              </div>

              {/* Experience Summary */}
              {parsedData.experience.length > 0 && (
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                    <Briefcase className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium">Experience</p>
                    <p className="text-sm text-muted-foreground">
                      {parsedData.experience.length} position
                      {parsedData.experience.length !== 1 ? "s" : ""} •{" "}
                      {parsedData.experience[0]?.company} (most recent)
                    </p>
                  </div>
                </div>
              )}

              {/* Education Summary */}
              {parsedData.education.length > 0 && (
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                    <GraduationCap className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium">Education</p>
                    <p className="text-sm text-muted-foreground">
                      {parsedData.education[0]?.degree} •{" "}
                      {parsedData.education[0]?.institution}
                    </p>
                  </div>
                </div>
              )}

              {/* Skills Summary */}
              {parsedData.skills.technical && parsedData.skills.technical.length > 0 && (
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">
                    <Code className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-medium">Skills</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {parsedData.skills.technical.slice(0, 8).map((skill, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 bg-muted text-xs rounded-full"
                        >
                          {skill}
                        </span>
                      ))}
                      {parsedData.skills.technical.length > 8 && (
                        <span className="text-xs text-muted-foreground">
                          +{parsedData.skills.technical.length - 8} more
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={handleRemoveFile} className="flex-1">
              Upload Different Resume
            </Button>
            <Button 
              onClick={() => {
                if (parsedData && resumeId) {
                  setIsConfirmed(true);
                  onUploadComplete(
                    resumeId,
                    parsedData,
                    file?.name || "resume",
                    insights || undefined
                  );
                } else {
                  setError("Resume ID missing. Please re-upload.");
                }
              }}
              className="flex-1"
            >
              Confirm & Continue
            </Button>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 text-destructive">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Upload Button */}
      {file && !parsedData && !isUploading && (
        <Button onClick={handleUpload} className="w-full">
          <Upload className="h-4 w-4 mr-2" />
          Parse Resume
        </Button>
      )}
    </div>
  );
};

