import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/theme-provider";
import Index from "./pages/Index";
import TailorResume from "./pages/TailorResume";
import Resources from "./pages/Resources";
import LearningPaths from "./pages/LearningPaths";
import Dashboard from "./pages/Dashboard";
import Applications from "./pages/Applications";
import SkillGaps from "./pages/SkillGaps";
import Audit from "./pages/Audit";
import OneThing from "./pages/OneThing";
import VerdictLoop from "./pages/VerdictLoop";
import Cohort from "./pages/Cohort";
import TrustProfile from "./pages/TrustProfile";
import Portfolio from "./pages/Portfolio";
import CareerReverseEngineer from "./pages/CareerReverseEngineer";
import SystemHealth from "./pages/SystemHealth";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/learning-paths" element={<LearningPaths />} />
            <Route path="/applications" element={<Applications />} />
            <Route path="/skill-gaps" element={<SkillGaps />} />
            <Route path="/tailor-resume" element={<TailorResume />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/one-thing" element={<OneThing />} />
            <Route path="/verdict-loop" element={<VerdictLoop />} />
            <Route path="/cohort" element={<Cohort />} />
            <Route path="/profile" element={<TrustProfile />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/career-reverse-engineer" element={<CareerReverseEngineer />} />
            <Route path="/system-health" element={<SystemHealth />} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
