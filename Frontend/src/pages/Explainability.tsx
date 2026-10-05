/**
 * FILE: src/pages/Explainability.tsx
 * PURPOSE: UC-04 — Explainability Panel + PDF Export + UC-08 Feedback
 * SRS: FR13 (Explainability), FR14 (Feedback), FR10 (Disclaimer)
 *
 * This page loads the analysis result saved in sessionStorage by SymptomChecker.tsx,
 * renders the full breakdown with confidence bars, key symptoms, and specialist info,
 * and provides the PDF download + star rating feedback form.
 *
 * Changes from prototype v1:
 *  - FeedbackWidget integrated at the bottom (UC-08 was completely missing before)
 *  - consultId now read from sessionStorage so the feedback hits the right DB row
 *  - PDF request now sends the full result payload (not just query_id) — fixes
 *    the "PDF generation failed" error that happened for guest sessions
 *  - Star rating visualization added for feedback score display
 */

import { useEffect, useState } from "react";
import { useNavigate }         from "react-router-dom";
import { useTranslation }      from "react-i18next";
import { Button }              from "@/components/ui/button";
import {
  Brain, AlertTriangle, ArrowLeft, Download,
  Stethoscope, ShieldCheck, Activity, Heart,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { generatePdf }    from "@/services/api";
import FeedbackWidget     from "@/components/FeedbackWidget";
import { toast }          from "sonner";

// ─── Types ────────────────────────────────────────────────────────────────────
type AnalysisResult = {
  summary:                string;
  conditions:             { name: string; confidence: number; description: string }[];
  triage_level:           string;
  triage_explanation:     string;
  recommended_specialist: string;
  self_care_tips:         string[];
  key_symptoms:           string[];
  profile_notes?:         string[];
  red_flag_warnings?:     string[];
  disclaimer:             string;
};

// ─── Triage config ─────────────────────────────────────────────────────────────
const TRIAGE_CONFIG = {
  "self-care":   { label: "Self-Care",   color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/40", icon: ShieldCheck },
  "visit-gp":   { label: "Visit GP",    color: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/40",   icon: Activity    },
  "urgent-care":{ label: "Urgent Care", color: "text-red-400",     bg: "bg-red-500/10",     border: "border-red-500/40",     icon: AlertTriangle },
} as const;

// Bar colors for the confidence chart — one per condition in top-3
const BAR_COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4"];

// ─── Section wrapper ──────────────────────────────────────────────────────────
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="rounded-xl border border-primary/20 bg-muted/20 p-5">
    <h3 className="text-sm font-semibold text-primary mb-4 uppercase tracking-wider">{title}</h3>
    {children}
  </div>
);

// ─── Main component ───────────────────────────────────────────────────────────
const Explainability = () => {
  const { t }      = useTranslation();
  const navigate   = useNavigate();
  const [result, setResult]       = useState<AnalysisResult | null>(null);
  const [queryId, setQueryId]     = useState<string | null>(null);
  const [consultId, setConsultId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    // All data is stashed in sessionStorage by SymptomChecker after a prediction
    const stored = sessionStorage.getItem("analysisResult");
    if (stored) {
      setResult(JSON.parse(stored));
    } else {
      // Nothing to show — send them back to the checker
      navigate("/symptom-checker");
      return;
    }

    setQueryId(sessionStorage.getItem("queryId"));
    // consultId is the actual DB row id returned by /predict — needed for feedback
    setConsultId(sessionStorage.getItem("consultId"));
  }, [navigate]);

  const handleDownloadPdf = async () => {
    if (!queryId || !result) {
      toast.error("No analysis result found. Please run a check first.");
      return;
    }
    setDownloading(true);
    try {
      const storedSymptoms = sessionStorage.getItem("lastSymptoms") || "Self-reported via assistant";
      // We send the full result to the backend — fixes the guest session PDF failure
      const blob = await generatePdf(queryId, result, storedSymptoms);
      const url  = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href     = url;
      link.download = `health_report_${queryId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success("PDF downloaded successfully!");
    } catch (err: unknown) {
      const error = err as Error;
      toast.error(error.message || "PDF download failed. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  if (!result) return null;

  const triageKey    = (result.triage_level as keyof typeof TRIAGE_CONFIG) ?? "visit-gp";
  const triageCfg    = TRIAGE_CONFIG[triageKey] ?? TRIAGE_CONFIG["visit-gp"];
  const TriageIcon   = triageCfg.icon;

  // Format conditions for the recharts bar chart
  const chartData = result.conditions?.map((c) => ({
    name:       c.name.length > 20 ? c.name.slice(0, 18) + "…" : c.name,
    fullName:   c.name,
    confidence: c.confidence,
  })) ?? [];

  return (
    <div className="container max-w-4xl py-8 md:py-12 space-y-6">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/symptom-checker")}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="font-display text-2xl font-bold glow-text flex items-center gap-2">
              <Brain className="h-6 w-6 text-primary" />
              {t("explainability.title", "Analysis Report")}
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              AI-generated health insights — not a medical diagnosis
            </p>
          </div>
        </div>
        <Button
          onClick={handleDownloadPdf}
          disabled={downloading}
          className="bg-primary hover:bg-primary/90 gap-2"
        >
          <Download className="h-4 w-4" />
          {downloading ? "Generating…" : "Download PDF"}
        </Button>
      </div>

      {/* ── Summary ── */}
      <div className={`rounded-xl px-5 py-4 border ${triageCfg.bg} ${triageCfg.border} flex items-center gap-3`}>
        <TriageIcon className={`h-6 w-6 shrink-0 ${triageCfg.color}`} />
        <div>
          <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Triage Level</p>
          <p className={`font-bold ${triageCfg.color}`}>{triageCfg.label}</p>
          {result.triage_explanation && (
            <p className="text-xs text-muted-foreground mt-1">{result.triage_explanation}</p>
          )}
        </div>
      </div>

      {/* ── Conditions confidence chart ── */}
      <Section title="Condition Confidence Breakdown">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={130} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0]?.payload;
                  return (
                    <div className="rounded-lg border border-primary/20 bg-background/95 px-3 py-2 text-xs shadow-lg">
                      <p className="font-semibold text-primary">{d?.fullName}</p>
                      <p className="text-muted-foreground">Confidence: {d?.confidence}%</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="confidence" radius={[0, 4, 4, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i] ?? BAR_COLORS[0]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">No condition data available.</p>
        )}
      </Section>

      {/* ── Key influencing symptoms ── */}
      {result.key_symptoms && result.key_symptoms.length > 0 && (
        <Section title="Key Symptoms That Influenced the Prediction">
          <div className="flex flex-wrap gap-2">
            {result.key_symptoms.map((s) => (
              <span
                key={s}
                className="px-3 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20"
              >
                {s}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* ── Recommended specialist ── */}
      {result.recommended_specialist && (
        <Section title="Recommended Specialist">
          <div className="flex items-center gap-3">
            <Stethoscope className="h-5 w-5 text-primary shrink-0" />
            <p className="font-semibold">{result.recommended_specialist}</p>
          </div>
        </Section>
      )}

      {/* ── Self-care tips ── */}
      {result.self_care_tips && result.self_care_tips.length > 0 && (
        <Section title="Self-Care Recommendations">
          <ul className="space-y-2">
            {result.self_care_tips.map((tip, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <Heart className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                {tip}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ── Profile notes (personalization) ── */}
      {result.profile_notes && result.profile_notes.length > 0 && (
        <Section title="Personalized Guidance Notes">
          <ul className="space-y-1">
            {result.profile_notes.map((note, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-amber-400/80">
                <span className="mt-0.5 shrink-0">ℹ</span>
                {note}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* ── Red flag warnings ── */}
      {result.red_flag_warnings && result.red_flag_warnings.length > 0 && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 space-y-2">
          <h3 className="text-sm font-semibold text-red-400 uppercase tracking-wider flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" /> Red Flag Warnings
          </h3>
          {result.red_flag_warnings.map((w, i) => (
            <p key={i} className="text-xs text-red-400">{w}</p>
          ))}
        </div>
      )}

      {/* ── Disclaimer (SRS FR10 — must appear on every result screen) ── */}
      <div className="rounded-xl border border-primary/10 bg-muted/10 px-4 py-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          <strong className="text-foreground">Disclaimer: </strong>
          {result.disclaimer ||
            "This is AI-generated guidance only and is NOT a substitute for professional medical advice. Please consult a qualified healthcare professional for any health concerns."}
        </p>
      </div>

      {/* ── UC-08 Feedback Widget (was completely missing in prototype v1) ── */}
      {consultId && (
        <FeedbackWidget consultId={consultId} />
      )}
      {!consultId && (
        <div className="text-center py-2">
          <p className="text-xs text-muted-foreground/50">
            Log in to submit feedback and help improve the model.
          </p>
        </div>
      )}
    </div>
  );
};

export default Explainability;