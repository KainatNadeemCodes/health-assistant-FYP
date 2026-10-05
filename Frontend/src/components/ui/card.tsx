/**
 * card.tsx
 * ------------------------------------------------------------------
 * A collection of modular components for building card-based layouts.
 * * Think of this as a flexible container system—you can mix and match 
 * headers, titles, and footers to keep content organized and visually
 * consistent across the app.
 */

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The main wrapper. Sets the background, border, and subtle shadow
 * that defines the card's presence on the page.
 */
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...props} />
));
Card.displayName = "Card";

/**
 * The top section of the card. Perfect for grouping the title and
 * description with consistent padding and vertical spacing.
 */
const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

/**
 * The primary heading. Styled to be bold and clear without 
 * overwhelming the rest of the card content.
 */
const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-2xl font-semibold leading-none tracking-tight", className)} {...props} />
  ),
);
CardTitle.displayName = "CardTitle";

/**
 * Subtext or secondary info. Uses a muted color to create 
 * a nice visual hierarchy under the title.
 */
const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  ),
);
CardDescription.displayName = "CardDescription";

/**
 * The main body of the card. It handles the side padding but 
 * removes the top padding to sit snugly under the header.
 */
const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />,
);
CardContent.displayName = "CardContent";

/**
 * The bottom row. Usually used for action buttons or timestamps,
 * aligned horizontally with a bit of breathing room.
 */
const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  ),
);
CardFooter.displayName = "CardFooter";

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent };