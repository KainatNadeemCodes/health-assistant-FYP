/**
 * Skeleton Component
 * ------------------
 * Placeholder loading UI used while content is being fetched.
 * Improves perceived performance and visual stability.
 */

import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
