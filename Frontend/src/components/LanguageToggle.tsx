/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * This component handles the language switching logic (English/Urdu). 
 * * It’s a key accessibility feature designed to make our health guidance 
 * reachable for a broader audience. 
 * * Basically: It's a simple, one-click toggle that swaps the entire app's 
 * context via the 'useLanguage' hook.
 * -------------------------------------------------------------------------
 */

import { useLanguage } from "@/hooks/useLanguage";
import { Globe } from "lucide-react";
import { Button } from "@/components/ui/button";

const LanguageToggle = () => {
  const { isUrdu, toggleLanguage } = useLanguage();

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      className="gap-2 border-primary/30 bg-transparent hover:bg-primary/10"
    >
      <Globe className="h-4 w-4" />
      {isUrdu ? "English" : "اردو"}
    </Button>
  );
};

export default LanguageToggle;
