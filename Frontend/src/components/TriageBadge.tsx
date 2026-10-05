/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * A visual indicator for medical urgency levels. It maps AI assessments 
 * to clear, color-coded badges (Green for Self-Care, Red for Urgent). 
 * * Basically: It translates complex health data into an easy-to-read 
 * priority level for the user.
 * -------------------------------------------------------------------------
 */

import { cn } from "@/lib/utils";
import { ShieldCheck, Stethoscope, AlertTriangle } from "lucide-react";

const triageConfig = {
  "self-care": {
    label: "Self-Care",
    icon: ShieldCheck,
    className: "bg-success/10 text-success border-success/30",
  },
  "visit-gp": {
    label: "Visit a Doctor",
    icon: Stethoscope,
    className: "bg-warning/10 text-warning border-warning/30",
  },
  "urgent-care": {
    label: "Seek Urgent Care",
    icon: AlertTriangle,
    className: "bg-destructive/10 text-destructive border-destructive/30",
  },
};

const TriageBadge = ({ level }: { level: string }) => {
  const config = triageConfig[level as keyof typeof triageConfig] || triageConfig["visit-gp"];
  const Icon = config.icon;

  return (
    <div className={cn("inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold", config.className)}>
      <Icon className="h-4 w-4" />
      {config.label}
    </div>
  );
};

export default TriageBadge;
