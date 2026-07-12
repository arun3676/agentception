import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Eye,
  EyeOff,
  FileText,
  Mail,
  Phone,
  MapPin,
  Briefcase,
  GraduationCap,
  Wrench,
  Award,
  Link2,
  X,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { ResumeStructured } from "@/lib/api";

interface ResumeViewerProps {
  text: string;
  structured?: ResumeStructured;
  fileName?: string;
  insights?: {
    role?: string;
    skills?: string[];
    skills_flat?: string[];
  } | null;
  onClose?: () => void;
}

export const ResumeViewer = ({ text, structured, fileName, insights, onClose }: ResumeViewerProps) => {
  const [expanded, setExpanded] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  const hasSection = (key: string) => {
    if (!structured) return false;
    const val = (structured as any)[key];
    if (Array.isArray(val)) return val.length > 0;
    if (typeof val === "string") return val.length > 0;
    if (typeof val === "object" && val !== null) {
      return Object.values(val).some((v: any) =>
        Array.isArray(v) ? v.length > 0 : v && String(v).length > 0
      );
    }
    return false;
  };

  const skillsList = Array.isArray(insights?.skills_flat)
    ? insights.skills_flat
    : Array.isArray(insights?.skills)
    ? insights.skills
    : [];

  const allSkills = [
    ...(structured?.skills?.technical || []),
    ...(structured?.skills?.frameworks || []),
    ...(structured?.skills?.tools || []),
  ];

  const contact = structured?.contact;

  return (
    <Card className="overflow-hidden border-border/60 shadow-sm">
      {/* Header */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
              <h3 className="text-sm font-semibold text-foreground">Your Resume</h3>
            </div>
            {contact?.name && (
              <p className="text-lg font-bold text-foreground truncate">{contact.name}</p>
            )}
            {insights?.role && (
              <p className="text-sm text-muted-foreground">{insights.role}</p>
            )}
            {fileName && (
              <p className="text-xs text-muted-foreground/70 truncate mt-0.5">{fileName}</p>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0 ml-3">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={() => setExpanded(!expanded)}
              title={expanded ? "Collapse" : "Expand"}
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
            {onClose && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                onClick={onClose}
                title="Remove resume"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Contact Chips */}
        {contact && (contact.email || contact.phone || contact.location) && (
          <div className="flex flex-wrap gap-2 mt-3">
            {contact.email && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-secondary rounded-md px-2 py-1 max-w-[180px]">
                <Mail className="h-3 w-3 shrink-0" />
                <span className="truncate">{contact.email}</span>
              </span>
            )}
            {contact.phone && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-secondary rounded-md px-2 py-1 max-w-[140px]">
                <Phone className="h-3 w-3 shrink-0" />
                <span className="truncate">{contact.phone}</span>
              </span>
            )}
            {contact.location && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground bg-secondary rounded-md px-2 py-1 max-w-[160px]">
                <MapPin className="h-3 w-3 shrink-0" />
                <span className="truncate">{contact.location}</span>
              </span>
            )}
          </div>
        )}

        {/* Social Links */}
        {contact && (contact.linkedin || contact.github || contact.portfolio) && (
          <div className="flex flex-wrap gap-2 mt-2">
            {contact.linkedin && (
              <a
                href={contact.linkedin}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Link2 className="h-3 w-3" />
                LinkedIn
              </a>
            )}
            {contact.github && (
              <a
                href={contact.github}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Link2 className="h-3 w-3" />
                GitHub
              </a>
            )}
            {contact.portfolio && (
              <a
                href={contact.portfolio}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Link2 className="h-3 w-3" />
                Portfolio
              </a>
            )}
          </div>
        )}
      </div>

      <Separator />

      <CardContent className="pt-4 pb-5">
        {!expanded ? (
          /* Collapsed view: Summary + Skills */
          <div className="space-y-4">
            {structured?.summary && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                  Summary
                </p>
                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-4">
                  {structured.summary}
                </p>
              </div>
            )}

            {/* Skills */}
            {(allSkills.length > 0 || skillsList.length > 0) && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(allSkills.length > 0 ? allSkills : skillsList)
                    .slice(0, 12)
                    .map((skill) => (
                      <Badge
                        key={skill}
                        variant="secondary"
                        className="text-[11px] font-medium px-2 py-0.5"
                      >
                        {skill}
                      </Badge>
                    ))}
                </div>
              </div>
            )}

            {/* Experience preview */}
            {structured?.experience && structured.experience.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Experience
                </p>
                <div className="space-y-2">
                  {structured.experience.slice(0, 2).map((exp, i) => (
                    <div key={i} className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{exp.title || exp.company}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {exp.company} {exp.dates && `• ${exp.dates}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              className="w-full h-8 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setExpanded(true)}
            >
              <Eye className="h-3.5 w-3.5 mr-1.5" />
              View full resume
            </Button>
          </div>
        ) : (
          /* Expanded view: All sections */
          <div className="space-y-6 max-h-[50vh] sm:max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
            {/* Summary */}
            {hasSection("summary") && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  <FileText className="h-3.5 w-3.5" />
                  Professional Summary
                </h4>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {structured!.summary}
                </p>
              </section>
            )}

            {/* Experience */}
            {hasSection("experience") && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  <Briefcase className="h-3.5 w-3.5" />
                  Experience
                </h4>
                <div className="space-y-4">
                  {structured!.experience.map((exp, i) => (
                    <div key={i} className="rounded-lg border border-border/50 p-3.5">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground">
                            {exp.title || "Position"}
                          </p>
                          <p className="text-sm text-muted-foreground">{exp.company}</p>
                        </div>
                        {exp.dates && (
                          <span className="text-xs text-muted-foreground shrink-0 bg-secondary rounded px-2 py-0.5">
                            {exp.dates}
                          </span>
                        )}
                      </div>
                      {exp.location && (
                        <p className="text-xs text-muted-foreground mb-2">{exp.location}</p>
                      )}
                      {exp.bullets && exp.bullets.length > 0 && (
                        <ul className="space-y-1 mt-2">
                          {exp.bullets.map((bullet, j) => (
                            <li key={j} className="text-sm text-muted-foreground leading-relaxed flex items-start gap-2">
                              <span className="h-1 w-1 rounded-full bg-muted-foreground/50 mt-2 shrink-0" />
                              {bullet}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Education */}
            {hasSection("education") && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  <GraduationCap className="h-3.5 w-3.5" />
                  Education
                </h4>
                <div className="space-y-3">
                  {structured!.education.map((edu, i) => (
                    <div key={i} className="rounded-lg border border-border/50 p-3.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground">
                            {edu.school || "Institution"}
                          </p>
                          <p className="text-sm text-muted-foreground">{edu.degree}</p>
                        </div>
                        {edu.dates && (
                          <span className="text-xs text-muted-foreground shrink-0 bg-secondary rounded px-2 py-0.5">
                            {edu.dates}
                          </span>
                        )}
                      </div>
                      {edu.gpa && (
                        <p className="text-xs text-muted-foreground mt-1">GPA: {edu.gpa}</p>
                      )}
                      {edu.details && edu.details.length > 0 && (
                        <ul className="mt-2 space-y-0.5">
                          {edu.details.map((d, j) => (
                            <li key={j} className="text-xs text-muted-foreground">{d}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Skills */}
            {(hasSection("skills") || allSkills.length > 0) && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  <Wrench className="h-3.5 w-3.5" />
                  Skills
                </h4>
                {structured?.skills && (
                  <div className="space-y-3">
                    {structured.skills.technical.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Languages & Core</p>
                        <div className="flex flex-wrap gap-1.5">
                          {structured.skills.technical.map((skill) => (
                            <Badge key={skill} variant="secondary" className="text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {structured.skills.frameworks.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Frameworks & Libraries</p>
                        <div className="flex flex-wrap gap-1.5">
                          {structured.skills.frameworks.map((skill) => (
                            <Badge key={skill} variant="outline" className="text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {structured.skills.tools.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Tools & Platforms</p>
                        <div className="flex flex-wrap gap-1.5">
                          {structured.skills.tools.map((skill) => (
                            <Badge key={skill} variant="outline" className="text-[11px] bg-secondary/50">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {structured.skills.soft.length > 0 && (
                      <div>
                        <p className="text-xs text-muted-foreground mb-1.5">Soft Skills</p>
                        <div className="flex flex-wrap gap-1.5">
                          {structured.skills.soft.map((skill) => (
                            <Badge key={skill} variant="outline" className="text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </section>
            )}

            {/* Projects */}
            {hasSection("projects") && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  <Briefcase className="h-3.5 w-3.5" />
                  Projects
                </h4>
                <div className="space-y-3">
                  {structured!.projects.map((proj, i) => (
                    <div key={i} className="rounded-lg border border-border/50 p-3.5">
                      <p className="text-sm font-semibold text-foreground">{proj.title}</p>
                      {proj.description && (
                        <p className="text-sm text-muted-foreground leading-relaxed mt-1">
                          {proj.description}
                        </p>
                      )}
                      {proj.tech_stack.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {proj.tech_stack.map((tech) => (
                            <Badge key={tech} variant="secondary" className="text-[10px]">
                              {tech}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Certifications */}
            {hasSection("certifications") && (
              <section>
                <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  <Award className="h-3.5 w-3.5" />
                  Certifications
                </h4>
                <ul className="space-y-1.5">
                  {structured!.certifications.map((cert, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <span className="h-1 w-1 rounded-full bg-muted-foreground/50 mt-2 shrink-0" />
                      {cert}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <Button
              variant="ghost"
              size="sm"
              className="w-full h-8 text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setExpanded(false)}
            >
              <EyeOff className="h-3.5 w-3.5 mr-1.5" />
              Collapse
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
