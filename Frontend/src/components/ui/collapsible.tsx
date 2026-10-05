/**
 * Collapsible Component
 * ---------------------
 * Simple wrapper around Radix UI Collapsible primitives.
 * Provides expandable and collapsible content sections.
 * Used for toggles, FAQs, and hidden content areas.
 */

import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";

const Collapsible = CollapsiblePrimitive.Root;

const CollapsibleTrigger = CollapsiblePrimitive.CollapsibleTrigger;

const CollapsibleContent = CollapsiblePrimitive.CollapsibleContent;

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
