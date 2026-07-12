import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, Sparkles } from "lucide-react";

export type TemplateOption = {
  id: string;
  name: string;
  description: string;
  features?: string[];
};

interface TemplateSelectorProps {
  templates: TemplateOption[];
  selectedTemplateId?: string;
  onChange: (templateId: string) => void;
  isLoading?: boolean;
}

export function TemplateSelector({
  templates,
  selectedTemplateId,
  onChange,
  isLoading,
}: TemplateSelectorProps) {
  if (isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="p-4 space-y-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-2/3" />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <RadioGroup
      value={selectedTemplateId}
      onValueChange={onChange}
      className="grid gap-3 md:grid-cols-3"
    >
      {templates.map((template) => (
        <Card
          key={template.id}
          className={`cursor-pointer transition border ${
            selectedTemplateId === template.id
              ? "border-primary shadow-md"
              : "border-border"
          }`}
          onClick={() => onChange(template.id)}
        >
          <CardHeader className="pb-2 flex items-start justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <RadioGroupItem value={template.id} id={template.id} />
              {template.name}
              {template.id === "latex_modern" && (
                <Badge variant="outline" className="gap-1">
                  <Sparkles className="h-3 w-3" />
                  LaTeX
                </Badge>
              )}
            </CardTitle>
            {selectedTemplateId === template.id && (
              <Badge className="bg-primary/10 text-primary">
                <Check className="h-3 w-3 mr-1" />
                Selected
              </Badge>
            )}
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>{template.description}</p>
            {template.features && template.features.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {template.features.slice(0, 3).map((feature) => (
                  <Badge key={feature} variant="secondary">
                    {feature}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </RadioGroup>
  );
}

