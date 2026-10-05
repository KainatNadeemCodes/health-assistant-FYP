/**
 * FILE: src/components/FeedbackWidget.tsx
 * PURPOSE: UC-08 — User Feedback Loop (1–5 Star Rating)
 * SRS: FR14 — Feedback Mechanism
 *
 * This is the star rating widget that appears at the bottom of the
 * Explainability page after the user gets their analysis result.
 * It sends the rating + optional comment to POST /feedback on the backend.
 *
 * I kept it as a separate component so it can be reused anywhere we need
 * to collect feedback without duplicating the logic.
 */

import { useState } from "react";
import { Star, Send, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const API_BASE = "http://localhost:8000";

interface FeedbackWidgetProps {
  consultId: number | string;
}

const FeedbackWidget = ({ consultId }: FeedbackWidgetProps) => {
  const [hovered, setHovered]   = useState(0);
  const [selected, setSelected] = useState(0);
  const [comment, setComment]   = useState("");
  const [loading, setLoading]   = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // Star labels so the user knows what each rating means
  const STAR_LABELS = ["", "Not helpful", "Somewhat helpful", "Helpful", "Very helpful", "Excellent!"];

  const handleSubmit = async () => {
    if (selected === 0) {
      toast.error("Please select a star rating before submitting.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/feedback`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          consult_id: Number(consultId),
          rating:     selected,
          comments:   comment.trim() || null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Submission failed.");
      }

      setSubmitted(true);
      toast.success("Thank you for your feedback!");
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "Could not submit feedback. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Show a thank-you confirmation once submitted
  if (submitted) {
    return (
      <div className="flex flex-col items-center gap-2 py-6 text-center">
        <CheckCircle2 className="h-8 w-8 text-emerald-400" />
        <p className="text-sm font-semibold text-emerald-400">Feedback received — thank you!</p>
        <p className="text-xs text-muted-foreground">Your rating helps improve future predictions.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-primary/20 bg-muted/20 p-5 space-y-4">
      <div>
        <h4 className="text-sm font-semibold text-primary uppercase tracking-wider mb-1">
          How helpful was this?
        </h4>
        <p className="text-xs text-muted-foreground">
          Rate the accuracy and usefulness of these results.
        </p>
      </div>

      {/* Star selector */}
      <div className="flex items-center gap-2">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => setSelected(star)}
            onMouseEnter={() => setHovered(star)}
            onMouseLeave={() => setHovered(0)}
            className="focus:outline-none transition-transform hover:scale-110"
            aria-label={`Rate ${star} out of 5`}
          >
            <Star
              className={`h-7 w-7 transition-colors ${
                star <= (hovered || selected)
                  ? "fill-amber-400 text-amber-400"
                  : "text-muted-foreground/40"
              }`}
            />
          </button>
        ))}
        {(hovered || selected) > 0 && (
          <span className="text-xs text-muted-foreground ml-1">
            {STAR_LABELS[hovered || selected]}
          </span>
        )}
      </div>

      {/* Optional comment */}
      <div>
        <textarea
          rows={2}
          placeholder="Any additional comments? (optional)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={300}
          className="w-full rounded-md border border-primary/20 bg-muted/50 px-3 py-2 text-sm
                     text-foreground placeholder:text-muted-foreground/60
                     focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        />
        <p className="text-[10px] text-muted-foreground/50 text-right mt-0.5">
          {comment.length}/300
        </p>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={loading || selected === 0}
        size="sm"
        className="w-full bg-primary hover:bg-primary/90"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : (
          <Send className="h-4 w-4 mr-2" />
        )}
        Submit Feedback
      </Button>
    </div>
  );
};

export default FeedbackWidget;