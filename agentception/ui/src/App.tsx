import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/theme-provider";
import { lazy, Suspense } from "react";
import FeatureUnavailable from "./pages/FeatureUnavailable";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();
const Index = lazy(() => import("./pages/Index"));
const Resources = lazy(() => import("./pages/Resources"));
const Dashboard = lazy(() => import("./pages/Dashboard"));

const RouteLoading = () => (
  <main className="grid min-h-screen place-items-center bg-background px-6" role="status" aria-live="polite">
    <p className="text-sm text-muted-foreground">Loading page…</p>
  </main>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Suspense fallback={<RouteLoading />}>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/resources" element={<Resources />} />
              <Route path="/learning-paths" element={<FeatureUnavailable feature="Personal learning paths" />} />
              <Route path="/applications" element={<FeatureUnavailable feature="Application tracking" />} />
              <Route path="/skill-gaps" element={<FeatureUnavailable feature="Resume skill analysis" />} />
              <Route path="/tailor-resume" element={<FeatureUnavailable feature="Resume tailoring" />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
