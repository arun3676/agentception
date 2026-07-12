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
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthProvider>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/resources" element={<RequireAuth><Resources /></RequireAuth>} />
            <Route path="/learning-paths" element={<RequireAuth><LearningPaths /></RequireAuth>} />
            <Route path="/applications" element={<RequireAuth><Applications /></RequireAuth>} />
            <Route path="/skill-gaps" element={<RequireAuth><SkillGaps /></RequireAuth>} />
            <Route path="/tailor-resume" element={<RequireAuth><TailorResume /></RequireAuth>} />
            <Route path="/audit" element={<RequireAuth><Audit /></RequireAuth>} />
            <Route path="/one-thing" element={<RequireAuth><OneThing /></RequireAuth>} />
            <Route path="/verdict-loop" element={<RequireAuth><VerdictLoop /></RequireAuth>} />
            <Route path="/cohort" element={<RequireAuth><Cohort /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth><TrustProfile /></RequireAuth>} />
            <Route path="/portfolio" element={<RequireAuth><Portfolio /></RequireAuth>} />
            <Route path="/career-reverse-engineer" element={<RequireAuth><CareerReverseEngineer /></RequireAuth>} />
            <Route path="/system-health" element={<RequireAuth><SystemHealth /></RequireAuth>} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
          </AuthProvider>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
