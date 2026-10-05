/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * This component acts as the mandatory legal and ethical footer for 
 * AI-generated responses. It uses the 'AlertTriangle' to ensure users 
 * don't miss the professional medical advice disclaimer.
 * * Basically: It keeps our AI helpful, while keeping our users safe.
 * -------------------------------------------------------------------------
 */

import { AlertTriangle } from "lucide-react";

const Disclaimer = () => (
  <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm text-muted-foreground">
    <div className="flex items-start gap-2">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
      <p>
        <strong className="text-foreground">Disclaimer:</strong> This AI assistant provides general health guidance only.
        It is <strong>not</strong> a substitute for professional medical advice, diagnosis, or treatment.
        Always consult a qualified healthcare provider.
      </p>
    </div>
  </div>
);

export default Disclaimer;
