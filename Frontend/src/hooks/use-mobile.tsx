/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * A utility hook that detects if the user is on a mobile device. 
 * * It monitors screen size in real-time to ensure the assistant's 
 * interface remains clean and usable on smaller screens.
 * * Basically: It's the "brain" behind our responsive layout decisions.
 * -------------------------------------------------------------------------
 */

import * as React from "react";

const MOBILE_BREAKPOINT = 768;

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}
