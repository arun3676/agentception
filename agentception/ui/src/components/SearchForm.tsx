import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { searchCompanies } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

interface SearchFormProps {
  onSearchStart: (runId: string) => void;
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

export const validateSearchInput = (location: string, role: string) => {
  if (!role.trim()) return "Choose a role to search.";
  if (!location.trim()) return "Enter a location to search.";
  return null;
};

export const SearchForm = ({ onSearchStart }: SearchFormProps) => {
  const [location, setLocation] = useState("San Francisco, CA");
  const [role, setRole] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async () => {
    const validationError = validateSearchInput(location, role);
    if (validationError) {
      toast({
        title: "Search details required",
        description: validationError,
        variant: "destructive",
      });
      return;
    }

    setIsSearching(true);
    try {
      const result = await searchCompanies({
        city: location,
        role,
        depth: "standard",
      });
      if (!result.run_id?.trim()) throw new Error("Search did not return an identifier.");
      onSearchStart(result.run_id);
    } catch {
      toast({
        title: "Search failed",
        description: "The search service is unavailable. No results were generated; please try again later.",
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
          <label htmlFor="search-location" className="text-sm font-medium text-foreground">
            Location
          </label>
          <Input
            id="search-location"
            placeholder="e.g., San Francisco, CA"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            className="h-12 rounded-2xl bg-background/80"
          />
        </div>

        <div className="space-y-2">
          <label id="search-role-label" className="text-sm font-medium text-foreground">
            Desired role
          </label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger aria-labelledby="search-role-label" className="h-12 rounded-2xl bg-background/80">
              <SelectValue placeholder="Choose a role" />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((roleName) => (
                <SelectItem key={roleName} value={roleName}>
                  {roleName}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div
        role="status"
        className="rounded-2xl border border-border bg-secondary/40 px-4 py-3 text-xs leading-5 text-muted-foreground"
      >
        Search uses only the role and location entered above. Resume upload and personal workspace features remain off
        until secure account ownership is available.
      </div>

      <div className="flex gap-3 pt-2">
        <Button onClick={handleSearch} disabled={isSearching} className="h-12 w-full rounded-2xl sm:w-auto">
          {isSearching ? "Searching..." : "Search Jobs"}
        </Button>
      </div>
    </div>
  );
};
