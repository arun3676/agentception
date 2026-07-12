import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Mail, ExternalLink, Copy, Edit, Save, X } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface EmailCardProps {
  company: string;
  email: string;
  subject: string;
  body: string;
  onUpdate?: (updates: { email: string; body: string }) => void;
}

export const EmailCard = ({ company, email, subject, body, onUpdate }: EmailCardProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedEmail, setEditedEmail] = useState(email);
  const [editedBody, setEditedBody] = useState(body);

  // Sync state when props change (only when not editing)
  useEffect(() => {
    if (!isEditing) {
      setEditedEmail(email);
      setEditedBody(body);
    }
  }, [email, body, isEditing]);

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleSave = () => {
    setIsEditing(false);
    // Notify parent component of changes
    if (onUpdate) {
      onUpdate({
        email: editedEmail,
        body: editedBody,
      });
    }
    toast({
      title: "Changes saved",
      description: "Email content and address updated",
    });
  };

  const handleCancel = () => {
    setEditedEmail(email);
    setEditedBody(body);
    setIsEditing(false);
    toast({
      title: "Changes cancelled",
      description: "Reverted to original content",
    });
  };

  // Get current values: use edited when editing, props when not editing
  const currentEmail = isEditing ? editedEmail : email;
  const currentBody = isEditing ? editedBody : body;

  const handleCopy = () => {
    const emailText = `Subject: ${subject}\n\n${currentBody}`;
    navigator.clipboard.writeText(emailText);
    toast({
      title: "Copied to clipboard",
      description: "Email content copied to clipboard",
    });
  };

  const handleGmail = () => {
    const mailtoLink = `mailto:${currentEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(currentBody)}`;
    window.open(mailtoLink, "_blank");
  };

  const handleOutlook = () => {
    const mailtoLink = `mailto:${currentEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(currentBody)}`;
    window.open(mailtoLink, "_blank");
  };

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-6 transition-all hover:border-foreground/20">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">{company}</h3>
          {!isEditing ? (
            <Button onClick={handleEdit} variant="outline" size="icon">
              <Edit className="h-4 w-4" />
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button onClick={handleSave} variant="default" size="icon">
                <Save className="h-4 w-4" />
              </Button>
              <Button onClick={handleCancel} variant="outline" size="icon">
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Mail className="h-4 w-4" />
          {isEditing ? (
            <Input
              type="email"
              value={editedEmail}
              onChange={(e) => setEditedEmail(e.target.value)}
              className="flex-1"
              placeholder="Enter email address"
            />
          ) : (
            <a href={`mailto:${currentEmail}`} className="text-foreground hover:underline">
              {currentEmail}
            </a>
          )}
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium text-foreground">{subject}</p>
        </div>
        {isEditing ? (
          <Textarea
            value={editedBody}
            onChange={(e) => setEditedBody(e.target.value)}
            className="min-h-[150px] resize-y"
            placeholder="Enter email body"
          />
        ) : (
          <div className="rounded-md bg-muted p-4">
            <p className="text-sm leading-relaxed text-foreground">{currentBody}</p>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <Button onClick={handleGmail} className="gap-2 flex-1">
          <ExternalLink className="h-4 w-4" />
          Open in Gmail
        </Button>
        <Button onClick={handleOutlook} variant="outline" className="gap-2 flex-1">
          <ExternalLink className="h-4 w-4" />
          Open in Outlook
        </Button>
        <Button onClick={handleCopy} variant="outline" size="icon">
          <Copy className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};
