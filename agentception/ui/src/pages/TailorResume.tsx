import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { TopNav } from "@/components/TopNav";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ResumeUpload } from "@/components/ResumeUpload";
import { JobDescriptionInput } from "@/components/JobDescriptionInput";
import { TailoredResumeView } from "@/components/TailoredResumeView";
import { ResumeDownload } from "@/components/ResumeDownload";
import { toast } from "@/hooks/use-toast";
import { getResumeByToken, bridgeResumeToSupabase, fetchJobDescriptionText } from "@/lib/api";
import { 
  tailorResume, 
  isSupabaseReady,
  type ParsedResumeData, 
  type ParsedJobData, 
  type TailorResumeResponse,
  type Keyword
} from "@/lib/supabase";
import { 
  Upload, 
  FileText, 
  Sparkles, 
  Download,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  FileCheck,
  RefreshCw
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// Step definitions
type Step = 1 | 2 | 3 | 4;

interface StepConfig {
  title: string;
  description: string;
  icon: React.ReactNode;
}

type ResumeInsights = Record<string, unknown>;

const steps: Record<Step, StepConfig> = {
  1: {
    title: "Upload Resume",
    description: "Upload your current resume (PDF or DOCX)",
    icon: <Upload className="h-5 w-5" />,
  },
  2: {
    title: "Job Description",
    description: "Paste the job description you want to apply for",
    icon: <FileText className="h-5 w-5" />,
  },
  3: {
    title: "Tailor Resume",
    description: "AI optimizes your resume for the job",
    icon: <Sparkles className="h-5 w-5" />,
  },
  4: {
    title: "Download",
    description: "Download your tailored resume",
    icon: <Download className="h-5 w-5" />,
  },
};

const TailorResume = () => {
  const location = useLocation();
  const jobData = location.state as {
    jobUrl?: string;
    jobSnippet?: string;
    jobTitle?: string;
    company?: string;
    resumeId?: string;
    resumeToken?: string;
  } | null;

  // Current step in the flow
  const [currentStep, setCurrentStep] = useState<Step>(jobData?.resumeId ? 2 : 1);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("classic_serif");
  
  // Resume data
  const [resumeId, setResumeId] = useState<string | null>(jobData?.resumeId || null);
  const [parsedResume, setParsedResume] = useState<ParsedResumeData | null>(null);
  const [resumeFileName, setResumeFileName] = useState<string>("");
  const [resumeInsights, setResumeInsights] = useState<ResumeInsights | null>(null);
  
  // Bridging: homepage resume token -> Supabase
  const [isBridging, setIsBridging] = useState(!!(jobData?.resumeToken));
  const [bridgeError, setBridgeError] = useState<string | null>(null);
  const [detectedResume, setDetectedResume] = useState<{
    name: string;
    role: string;
    skills: string[];
    text: string;
    fileName: string;
    structured: any;
    token: string;
  } | null>(null);
  
  // Job description data (pre-filled if coming from job card)
  const [jobDescriptionId, setJobDescriptionId] = useState<string | null>(null);
  const [parsedJobDescription, setParsedJobDescription] = useState<ParsedJobData | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [prefilledJobText, setPrefilledJobText] = useState<string>(jobData?.jobSnippet || "");
  const [isFetchingJD, setIsFetchingJD] = useState(false);
  
  // Pre-fetch full job description from job URL
  useEffect(() => {
    if (!jobData?.jobUrl) return;
    
    const fetchJD = async () => {
      setIsFetchingJD(true);
      try {
        const text = await fetchJobDescriptionText(jobData.jobUrl!, jobData.jobSnippet);
        if (text && text.length > 50) {
          setPrefilledJobText(text);
        }
      } catch (err) {
        console.warn("Could not pre-fetch job description, will use snippet:", err);
      } finally {
        setIsFetchingJD(false);
      }
    };
    
    fetchJD();
  }, [jobData?.jobUrl, jobData?.jobSnippet]);
  
  // Tailored resume data
  const [tailoredResumeId, setTailoredResumeId] = useState<string | null>(null);
  const [tailoredData, setTailoredData] = useState<TailorResumeResponse | null>(null);
  
  // Loading states
  const [isTailoring, setIsTailoring] = useState(false);
  const [tailoringProgress, setTailoringProgress] = useState(0);

  // Detect and bridge homepage-uploaded resume
  useEffect(() => {
    const token = jobData?.resumeToken;
    if (!token || jobData?.resumeId) return;

    const fetchAndDetect = async () => {
      setIsBridging(true);
      setBridgeError(null);
      try {
        const result = await getResumeByToken(token);
        const structured = result.structured;
        
        setDetectedResume({
          name: structured?.contact?.name || "Your Resume",
          role: result.insights?.role || "",
          skills: result.insights?.skills_flat?.slice(0, 8) || [],
          text: result.text_preview,
          fileName: jobData?.company ? `${jobData.company} application` : "Uploaded resume",
          structured: structured || {},
          token: token,
        });
        
        toast({
          title: "Resume detected",
          description: "We found your resume from the search. Ready to tailor.",
        });
      } catch (err) {
        console.error("Failed to fetch resume:", err);
        setBridgeError("Could not load your resume. Please upload it again.");
      } finally {
        setIsBridging(false);
      }
    };

    fetchAndDetect();
  }, [jobData?.resumeToken, jobData?.resumeId, jobData?.company]);

  const handleBridgeResume = async () => {
    if (!detectedResume) return;
    
    setIsBridging(true);
    setBridgeError(null);
    
    try {
      const s = detectedResume.structured;
      
      // Build ParsedResumeData from our backend's structured data
      const builtParsedResume: ParsedResumeData = {
        contact: {
          name: s?.contact?.name || detectedResume.name || "Your Name",
          email: s?.contact?.email || null,
          phone: s?.contact?.phone || null,
          linkedin: s?.contact?.linkedin || null,
          github: s?.contact?.github || null,
          website: s?.contact?.portfolio || null,
          address: s?.contact?.location || null,
          city: null,
          state: null,
          country: null,
        },
        summary: s?.summary || "",
        experience: (s?.experience || []).map((exp: any) => {
          const dates = exp.dates || "";
          const dateParts = dates.split(/[-–—]/).map((d: string) => d.trim());
          return {
            company: exp.company || "",
            position: exp.title || exp.company || "",
            duration: {
              start: dateParts[0] || "",
              end: dateParts[1] || "present",
            },
            location: exp.location || "",
            description: exp.bullets?.join(". ") || "",
            achievements: exp.bullets || [],
            technologies: [],
          };
        }),
        education: (s?.education || []).map((edu: any) => {
          const dates = edu.dates || "";
          const dateParts = dates.split(/[-–—]/).map((d: string) => d.trim());
          return {
            institution: edu.school || "",
            degree: edu.degree || "",
            field: null,
            duration: {
              start: dateParts[0] || "",
              end: dateParts[1] || "present",
            },
            gpa: edu.gpa || undefined,
            honors: edu.details || [],
            location: "",
          };
        }),
        skills: {
          technical: s?.skills?.technical || [],
          soft: s?.skills?.soft || [],
          languages: [],
          industry: [],
          tools: s?.skills?.tools || [],
          frameworks: s?.skills?.frameworks || [],
        },
        certifications: (s?.certifications || []).map((c: string) => ({
          name: c,
          issuer: "",
          date: "",
        })),
        projects: (s?.projects || []).map((p: any) => ({
          name: p.title || "",
          description: p.description || "",
          technologies: p.tech_stack || [],
          url: p.links?.[0] || undefined,
        })),
      };
      
      // Use backend token as the resumeId
      setResumeId(detectedResume.token);
      setParsedResume(builtParsedResume);
      setResumeFileName(detectedResume.fileName);
      setCurrentStep(2);
      
      toast({
        title: "Resume ready",
        description: "Your resume has been loaded. Proceeding to job description.",
      });
    } catch (err) {
      console.error("Failed to bridge resume:", err);
      setBridgeError(
        err instanceof Error 
          ? err.message 
          : "Failed to process resume. Please upload manually."
      );
    } finally {
      setIsBridging(false);
    }
  };

  // Step completion handlers
  const handleResumeUploaded = (
    id: string, 
    data: ParsedResumeData, 
    fileName: string,
    insights?: ResumeInsights
  ) => {
    setResumeId(id);
    setParsedResume(data);
    setResumeFileName(fileName);
    if (insights) {
      setResumeInsights(insights);
    }
    setCurrentStep(2);
    toast({
      title: "Resume parsed successfully",
      description: `Extracted data from ${fileName}`,
    });
  };

  const handleJobDescriptionParsed = (
    id: string,
    data: ParsedJobData,
    extractedKeywords: Keyword[]
  ) => {
    setJobDescriptionId(id);
    setParsedJobDescription(data);
    setKeywords(extractedKeywords);
    setCurrentStep(3);
    toast({
      title: "Job description analyzed",
      description: `Found ${extractedKeywords.length} ATS keywords`,
    });
  };

  const handleTailorResume = async () => {
    if (!resumeId || !jobDescriptionId) {
      toast({
        title: "Missing data",
        description: "Please complete the previous steps first",
        variant: "destructive",
      });
      return;
    }

    setIsTailoring(true);
    setTailoringProgress(0);

    try {
      const progressInterval = setInterval(() => {
        setTailoringProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 3000);

      let effectiveResumeId = resumeId;
      
      // If resumeId is a backend token (64 hex chars), bridge to Supabase first
      if (/^[a-f0-9]{64}$/i.test(resumeId)) {
        try {
          const bridgeResult = await bridgeResumeToSupabase(resumeId);
          effectiveResumeId = bridgeResult.resumeId;
          setResumeId(effectiveResumeId);
        } catch (bridgeErr) {
          console.error("Bridge to Supabase failed:", bridgeErr);
          clearInterval(progressInterval);
          toast({
            title: "Failed to process resume",
            description: "Could not bridge resume to Supabase. Please upload manually.",
            variant: "destructive",
          });
          setCurrentStep(1);
          setDetectedResume(null);
          return;
        }
      }
      
      const result = await tailorResume(effectiveResumeId, jobDescriptionId);
      
      clearInterval(progressInterval);
      setTailoringProgress(100);
      
      setTailoredResumeId(result.tailoredResumeId);
      setTailoredData(result);
      setCurrentStep(4);
      
      toast({
        title: "Resume tailored successfully!",
        description: `ATS match score: ${result.matchScore}%`,
      });
    } catch (error) {
      console.error("Tailoring error:", error);
      toast({
        title: "Failed to tailor resume",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsTailoring(false);
    }
  };

  const handleDownloadComplete = () => {
    toast({
      title: "Download started",
      description: "Your tailored resume is downloading...",
    });
  };

  const handleStartOver = () => {
    setCurrentStep(1);
    setResumeId(null);
    setParsedResume(null);
    setResumeFileName("");
    setJobDescriptionId(null);
    setParsedJobDescription(null);
    setKeywords([]);
    setTailoredResumeId(null);
    setTailoredData(null);
    setTailoringProgress(0);
    setDetectedResume(null);
    setBridgeError(null);
  };

  // Calculate overall progress
  const overallProgress = ((currentStep - 1) / 4) * 100 + (isTailoring ? (tailoringProgress / 4) : 0);

  return (
    <div className="min-h-screen bg-background">
      <TopNav />

      <main className="app-main">
        <section className="glass-panel mb-8 rounded-[2rem] p-6 sm:p-8">
          <p className="eyebrow mb-3">Resume tailoring</p>
          <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
            Tailor your resume.
            <span className="hero-gradient-text block">Beat the ATS.</span>
          </h1>
          <p className="mt-4 max-w-3xl text-muted-foreground">
            Upload your resume and paste a job description. The AI optimizes keywords, bullets, and section priority for the role.
          </p>
        </section>

        {/* Supabase Configuration Warning */}
        {!isSupabaseReady() && (
          <Alert variant="destructive" className="mb-8 max-w-3xl rounded-3xl">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Configuration Required</AlertTitle>
            <AlertDescription>
              <p className="mb-2">
                Resume tailoring needs Supabase credentials and a valid authenticated user ID. To enable it, please:
              </p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>Create a <code className="px-1 bg-muted rounded">.env.local</code> file in the <code className="px-1 bg-muted rounded">ui</code> folder</li>
                <li>Add your Supabase credentials:
                  <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-x-auto">
{`VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_SUPABASE_DEFAULT_USER_ID=your-auth-user-id`}
                  </pre>
                </li>
                <li>Restart the development server</li>
              </ol>
            </AlertDescription>
          </Alert>
        )}

        {/* Progress Steps */}
        <div className="soft-card mb-8 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center gap-3 sm:gap-4 pb-2">
            {([1, 2, 3, 4] as Step[]).map((step) => (
              <div
                key={step}
                className={`flex items-center gap-2 sm:gap-3 ${
                  step <= currentStep ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-2xl border-2 transition-colors ${
                    step < currentStep
                      ? "bg-primary border-primary text-primary-foreground"
                      : step === currentStep
                      ? "border-primary text-primary"
                      : "border-muted"
                  }`}
                >
                  {step < currentStep ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    steps[step].icon
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium">{steps[step].title}</p>
                  <p className="hidden text-xs text-muted-foreground sm:block">{steps[step].description}</p>
                </div>
              </div>
            ))}
          </div>
          <Progress value={overallProgress} className="h-2" />
        </div>

        {/* Step Content */}
        <div className="mx-auto max-w-4xl">
          {/* Step 1: Upload Resume */}
          {currentStep === 1 && (
            <div className="space-y-6">
              {/* Detected resume from homepage search */}
              {detectedResume && (
                <Card className="soft-card border-primary/30 bg-primary/5">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FileCheck className="h-5 w-5 text-primary" />
                      Resume Detected from Search
                    </CardTitle>
                    <CardDescription>
                      We found the resume you uploaded earlier. Use it to tailor for this job.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="rounded-xl bg-card p-4 space-y-3">
                      <div>
                        <p className="text-lg font-semibold">{detectedResume.name}</p>
                        {detectedResume.role && (
                          <p className="text-sm text-muted-foreground">{detectedResume.role}</p>
                        )}
                      </div>
                      
                      {detectedResume.skills.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {detectedResume.skills.map((skill) => (
                            <Badge key={skill} variant="secondary" className="text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      )}
                      
                      <div className="text-xs text-muted-foreground">
                        {detectedResume.text.length.toLocaleString()} characters extracted
                      </div>
                    </div>

                    {bridgeError && (
                      <Alert variant="destructive" className="rounded-xl">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>{bridgeError}</AlertDescription>
                      </Alert>
                    )}

                    <div className="flex flex-col gap-3 sm:flex-row">
                      <Button 
                        onClick={handleBridgeResume} 
                        disabled={isBridging}
                        className="flex-1 rounded-2xl"
                      >
                        {isBridging ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Loading resume...
                          </>
                        ) : (
                          <>
                            <Sparkles className="h-4 w-4 mr-2" />
                            Use This Resume
                          </>
                        )}
                      </Button>
                      <Button 
                        variant="outline" 
                        onClick={() => setDetectedResume(null)}
                        disabled={isBridging}
                        className="rounded-2xl"
                      >
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Upload Different
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Default upload area */}
              {!detectedResume && (
                <Card className="soft-card">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Upload className="h-5 w-5" />
                      Upload Your Resume
                    </CardTitle>
                    <CardDescription>
                      Upload your current resume in PDF or DOCX format. Our AI will parse and extract your information.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {isBridging ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground mr-3" />
                        <span className="text-muted-foreground">Checking for uploaded resume...</span>
                      </div>
                    ) : (
                      <ResumeUpload onUploadComplete={handleResumeUploaded} />
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* Step 2: Job Description */}
          {currentStep === 2 && (
            <Card className="soft-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {isFetchingJD ? "Fetching Job Description..." : "Enter Job Description"}
                </CardTitle>
                <CardDescription>
                  {isFetchingJD 
                    ? `Loading full description for ${jobData?.jobTitle || "this role"} from ${jobData?.company || "the listing"}...`
                    : "Paste the job description you want to apply for. We'll extract keywords and requirements."
                  }
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isFetchingJD && (
                  <div className="flex items-center gap-3 py-4 mb-4 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Pre-fetching job description from URL...
                  </div>
                )}
                <JobDescriptionInput 
                  onParseComplete={handleJobDescriptionParsed}
                  onBack={() => setCurrentStep(1)}
                  prefilledText={prefilledJobText}
                  prefilledTitle={jobData?.jobTitle}
                  prefilledCompany={jobData?.company}
                  prefilledUrl={jobData?.jobUrl}
                />
              </CardContent>
            </Card>
          )}

          {/* Step 3: Generate Tailored Resume */}
          {currentStep === 3 && (
            <Card className="soft-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5" />
                  Generate Tailored Resume
                </CardTitle>
                <CardDescription>
                  Review your data and generate an ATS-optimized version of your resume.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Summary Cards */}
                <div className="grid gap-4 md:grid-cols-2">
                  {/* Resume Summary */}
                    <Card className="rounded-3xl border-border/70 bg-muted/50">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Your Resume</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-2">{resumeFileName}</p>
                      {parsedResume && (
                        <div className="space-y-1 text-xs">
                          <p><span className="font-medium">Name:</span> {parsedResume.contact.name}</p>
                          <p><span className="font-medium">Experience:</span> {parsedResume.experience.length} positions</p>
                          <p><span className="font-medium">Skills:</span> {parsedResume.skills.technical?.length || 0} technical skills</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Job Description Summary */}
                  <Card className="rounded-3xl border-border/70 bg-muted/50">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium">Target Job</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {parsedJobDescription && (
                        <div className="space-y-1 text-xs">
                          <p><span className="font-medium">Company:</span> {parsedJobDescription.company?.name || "Unknown"}</p>
                          <p><span className="font-medium">Experience:</span> {parsedJobDescription.requirements.experience.minYears || "Not specified"} years</p>
                          <p><span className="font-medium">Keywords:</span> {keywords.length} ATS keywords found</p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Top Keywords Preview */}
                {keywords.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Top ATS Keywords:</p>
                    <div className="flex flex-wrap gap-2">
                      {keywords.slice(0, 10).map((keyword, index) => (
                        <span
                          key={index}
                          className={`px-2 py-1 rounded-full text-xs ${
                            keyword.context === "required"
                              ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                              : keyword.context === "preferred"
                              ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300"
                              : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                          }`}
                        >
                          {keyword.text}
                        </span>
                      ))}
                      {keywords.length > 10 && (
                        <span className="px-2 py-1 text-xs text-muted-foreground">
                          +{keywords.length - 10} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Tailoring Progress */}
                {isTailoring && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Tailoring resume...</span>
                      <span className="font-medium">{tailoringProgress}%</span>
                    </div>
                    <Progress value={tailoringProgress} className="h-2" />
                    <p className="text-xs text-muted-foreground">
                      {tailoringProgress < 30
                        ? "Analyzing job requirements..."
                        : tailoringProgress < 60
                        ? "Optimizing keywords and bullet points..."
                        : tailoringProgress < 90
                        ? "Reordering sections for relevance..."
                        : "Finalizing tailored resume..."}
                    </p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
                  <Button variant="outline" onClick={() => setCurrentStep(2)} className="rounded-2xl">
                    Back
                  </Button>
                  <Button 
                    onClick={handleTailorResume} 
                    disabled={isTailoring}
                    className="flex-1 rounded-2xl"
                  >
                    {isTailoring ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Tailoring Resume...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Generate Tailored Resume
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 4: Download */}
          {currentStep === 4 && tailoredData && (
            <div className="space-y-6">
              <TailoredResumeView 
                originalResume={parsedResume!}
                tailoredData={tailoredData}
                keywords={keywords}
              />
              <ResumeDownload 
                tailoredResumeId={tailoredResumeId!}
                tailoredData={tailoredData.tailoredData}
                fileName={`${parsedResume?.contact.name || "resume"}_tailored.docx`}
                selectedTemplateId={selectedTemplateId}
                onTemplateChange={setSelectedTemplateId}
                onDownloadComplete={handleDownloadComplete}
              />
              <div className="flex justify-center">
                <Button variant="outline" onClick={handleStartOver} className="rounded-2xl">
                  Tailor Another Resume
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default TailorResume;

