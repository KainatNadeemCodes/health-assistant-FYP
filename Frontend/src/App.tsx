/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * The Root Component of our application. 
 * * It acts as the "Grand Orchestrator," setting up essential services like 
 * Routing, Authentication, and Global Notifications.
 * * It defines the entire page structure—from the Symptom Checker to the 
 * AI Explainability dashboard—ensuring a seamless user journey.
 * -------------------------------------------------------------------------
 */

import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";

import Navbar from "@/components/Navbar";
import Index from "./pages/Index";
import Auth from "./pages/Auth";
import SymptomChecker from "./pages/SymptomChecker";
import Dashboard from "./pages/Dashboard";
import About from "./pages/About";
import Explainability from "./pages/Explainability";
import NotFound from "./pages/NotFound";
import AdminDashboard from "./pages/AdminDashboard";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AuthProvider>
          <Navbar />
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/auth" element={<Auth />} />
            <Route path="/symptom-checker" element={<SymptomChecker />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/about" element={<About />} />
            <Route path="/explainability" element={<Explainability />} />
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
