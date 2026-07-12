import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TemplateSelector } from "@/components/TemplateSelector";
import {
  generateDocx,
  generatePdf,
  getTemplates,
  type TailoredResumeData,
  type TemplateOption,
} from "@/lib/supabase";
import {
  Download,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Eye,
  EyeOff,
} from "lucide-react";

interface ResumeDownloadProps {
  tailoredResumeId?: string;
  tailoredData: TailoredResumeData;
  fileName?: string;
  selectedTemplateId?: string;
  onTemplateChange?: (templateId: string) => void;
  onDownloadComplete?: () => void;
  /**
   * If true, skip Supabase doc generation and download a plain-text version locally.
   * Useful when tailoring happens inline on the job-search page without Supabase IDs.
   */
  useClientDownload?: boolean;
}

export const ResumeDownload = ({ 
  tailoredResumeId, 
  tailoredData,
  fileName = "tailored_resume.docx",
  selectedTemplateId,
  onTemplateChange,
  onDownloadComplete,
  useClientDownload = false
}: ResumeDownloadProps) => {
  const [isGeneratingDocx, setIsGeneratingDocx] = useState(false);
  const [generateProgress, setGenerateProgress] = useState(0);
  const [docxComplete, setDocxComplete] = useState(false);
  const [docxError, setDocxError] = useState<string | null>(null);

  const [templates, setTemplates] = useState<TemplateOption[]>([]);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [currentTemplateId, setCurrentTemplateId] = useState<string>(selectedTemplateId || "classic_serif");

  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(true);

  useEffect(() => {
    const loadTemplates = async () => {
      setTemplateLoading(true);
      try {
        const data = await getTemplates();
        setTemplates(data);
        if (!selectedTemplateId && data.length > 0) {
          setCurrentTemplateId(data[0].id);
        }
      } catch (err) {
        console.error("Failed to load templates", err);
        setTemplateError("Failed to load templates");
      } finally {
        setTemplateLoading(false);
      }
    };

    loadTemplates();
  }, [selectedTemplateId]);

  const handleTemplateChange = (id: string) => {
    setCurrentTemplateId(id);
    onTemplateChange?.(id);
  };

  const handleClientDownload = () => {
    // Simple plaintext export for inline-tailored resumes without backend ID
    const plain = JSON.stringify(tailoredData, null, 2);
    const blob = new Blob([plain], { type: "text/plain" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName.replace(/\.docx$/i, ".txt");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    setDocxComplete(true);
    onDownloadComplete?.();
  };

  const handleDownload = async () => {
    if (useClientDownload || !tailoredResumeId) {
      return handleClientDownload();
    }
    setIsGeneratingDocx(true);
    setDocxError(null);
    setGenerateProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setGenerateProgress((prev) => {
          if (prev >= 80) {
            clearInterval(progressInterval);
            return 80;
          }
          return prev + 20;
        });
      }, 300);

      const blob = await generateDocx(tailoredResumeId);

      clearInterval(progressInterval);
      setGenerateProgress(100);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setDocxComplete(true);
      onDownloadComplete?.();
    } catch (err) {
      console.error("Download error:", err);
      setDocxError(err instanceof Error ? err.message : "Failed to generate DOCX");
      setGenerateProgress(0);
    } finally {
      setIsGeneratingDocx(false);
    }
  };

  const handleRetry = () => {
    setDocxError(null);
    setDocxComplete(false);
    setGenerateProgress(0);
  };

  const handleGeneratePdf = async () => {
    if (useClientDownload || !tailoredResumeId) {
      return handleClientDownload();
    }
    if (!currentTemplateId) {
      setPdfError("Please select a template first.");
      return;
    }

    setPdfGenerating(true);
    setPdfError(null);
    try {
      const blob = await generatePdf(tailoredResumeId, currentTemplateId, tailoredData);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName.replace(/\.docx$/i, ".pdf");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      onDownloadComplete?.();
    } catch (err) {
      console.error("PDF generation error:", err);
      setPdfError(err instanceof Error ? err.message : "Failed to generate PDF");
    } finally {
      setPdfGenerating(false);
    }
  };

  const selectedTemplateName =
    templates.find((t) => t.id === currentTemplateId)?.name || "Selected template";

  const previewExperience = (tailoredData.experience || []).slice(0, 2);
  const previewSkills = (tailoredData.skills?.technical || []).slice(0, 6);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Export Tailored Resume
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">

        {/* Preview */}
        <div className="rounded-lg border border-border/70 bg-muted/20 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">Preview</p>
              <p className="text-xs text-muted-foreground">
                {selectedTemplateName} · Quick glance before you download
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="gap-2"
              onClick={() => setShowPreview((v) => !v)}
            >
              {showPreview ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              {showPreview ? "Hide" : "Show"}
            </Button>
          </div>

          {showPreview && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <p className="text-lg font-semibold text-foreground">
                  {tailoredData.contact?.name || "Candidate"}
                </p>
                <p className="text-sm text-muted-foreground">
                  {tailoredData.summary || "Summary will appear here."}
                </p>
                {previewSkills.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Skills: {previewSkills.join(", ")}
                  </p>
                )}
              </div>

              <div className="space-y-3">
                {previewExperience.length > 0 ? (
                  previewExperience.map((exp, idx) => (
                    <div key={`${exp.company}-${idx}`} className="rounded-md border border-border/60 p-3">
                      <p className="text-sm font-semibold text-foreground">
                        {exp.position} @ {exp.company}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {exp.location || ""}{" "}
                        {exp.duration?.start ? `• ${exp.duration.start} - ${exp.duration.end || "present"}` : ""}
                      </p>
                      {exp.achievements && exp.achievements.length > 0 && (
                        <ul className="mt-2 space-y-1 text-xs text-muted-foreground list-disc list-inside">
                          {exp.achievements.slice(0, 2).map((ach, i) => (
                            <li key={i}>{ach}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">Experience preview will appear here.</p>
                )}
              </div>
            </div>
          )}
        </div>

        {!useClientDownload && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Choose a template</p>
            {templateError && (
              <p className="text-xs text-destructive">{templateError}</p>
            )}
            <TemplateSelector
              templates={templates}
              selectedTemplateId={currentTemplateId}
              onChange={handleTemplateChange}
              isLoading={templateLoading}
            />
          </div>
        )}

        {/* Download Status */}
        {!isGeneratingDocx && !docxComplete && !docxError && (
          <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50">
            <div className="p-3 rounded-full bg-primary/10 text-primary">
              <Download className="h-6 w-6" />
            </div>
            <div className="flex-1">
              <p className="font-medium">Ready to Download</p>
              <p className="text-sm text-muted-foreground">
                {useClientDownload
                  ? "Download a quick text copy of your tailored resume."
                  : "Export as PDF using the selected template, or download DOCX."}
              </p>
            </div>
          </div>
        )}

        {/* Generating Progress */}
        {isGeneratingDocx && !useClientDownload && (
          <div className="space-y-3">
            <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <div className="flex-1">
                <p className="font-medium">Generating DOCX...</p>
                <p className="text-sm text-muted-foreground">
                  {generateProgress < 30
                    ? "Preparing document..."
                    : generateProgress < 60
                    ? "Formatting sections..."
                    : generateProgress < 90
                    ? "Adding styling..."
                    : "Finalizing..."}
                </p>
              </div>
            </div>
            <Progress value={generateProgress} className="h-2" />
          </div>
        )}

        {/* Success State */}
        {docxComplete && (
          <div className="flex items-center gap-4 p-4 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
            <CheckCircle2 className="h-6 w-6" />
            <div className="flex-1">
              <p className="font-medium">Download Started!</p>
              <p className="text-sm opacity-80">
                Your tailored resume should be downloading now. Check your downloads folder.
              </p>
            </div>
          </div>
        )}

        {/* Error State */}
        {docxError && (
          <div className="flex items-center gap-4 p-4 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-6 w-6" />
            <div className="flex-1">
              <p className="font-medium">Download Failed</p>
              <p className="text-sm opacity-80">{docxError}</p>
            </div>
          </div>
        )}

        {pdfError && (
          <div className="flex items-center gap-4 p-4 rounded-lg bg-destructive/10 text-destructive">
            <AlertCircle className="h-6 w-6" />
            <div className="flex-1">
              <p className="font-medium">PDF Failed</p>
              <p className="text-sm opacity-80">{pdfError}</p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col md:flex-row gap-3">
          {!useClientDownload && (
            <Button 
              onClick={handleGeneratePdf} 
              disabled={pdfGenerating || templateLoading}
              className="flex-1"
            >
              {pdfGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating PDF...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  Export as PDF
                </>
              )}
            </Button>
          )}

          {docxError ? (
            <Button onClick={handleRetry} variant="outline" className="flex-1">
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          ) : docxComplete ? (
            <Button onClick={handleDownload} variant="outline" className="flex-1">
              <Download className="h-4 w-4 mr-2" />
              Download Again
            </Button>
          ) : (
            <Button 
              onClick={handleDownload} 
              disabled={isGeneratingDocx && !useClientDownload}
              className="flex-1"
            >
              {isGeneratingDocx && !useClientDownload ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" />
                  {useClientDownload ? "Download as TXT" : "Download as DOCX"}
                </>
              )}
            </Button>
          )}
        </div>

        {/* Additional Info */}
        <div className="pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            <strong>Tips:</strong>
          </p>
          <ul className="text-xs text-muted-foreground list-disc list-inside mt-1 space-y-1">
            <li>Review the document before submitting your application</li>
            <li>Make any final personal touches or corrections</li>
            <li>Save a copy of both your original and tailored resume</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

