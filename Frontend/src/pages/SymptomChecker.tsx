/**
 * FILE: src/pages/SymptomChecker.tsx
 * PURPOSE: Main Chat Interface — UC-01, UC-02, UC-03, UC-04, UC-05
 * SRS: FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR10, FR11, FR17, FR18
 *
 * This is where the user actually talks to the AI assistant. It handles:
 *  - Text symptom input with validation
 *  - Voice input via MediaRecorder → backend /voice-input (UC-02)
 *  - Optional patient metadata panel for personalization (UC-03)
 *  - Guest message limit enforcement (UC-02 SRS limit)
 *  - Rendering the triage ResultCard inline in the chat
 *  - Navigating to the Explainability page for the full report
 *
 * Changes from v2 (voice fix):
 *  - REMOVED webkitSpeechRecognition — it silently fails on Pakistani networks
 *    because Chrome sends audio to Google's servers which are unreachable.
 *  - ADDED MediaRecorder-based recording: browser captures audio locally,
 *    sends the blob to our own backend at /voice-input, which transcribes it
 *    server-side. No Google network dependency from the browser at all.
 *  - Recording state: idle → recording (red pulse) → transcribing (spinner)
 *  - Supports English and Urdu via ?language= param to backend
 */

import { useState, useRef, useEffect }  from "react";
import { useNavigate }                   from "react-router-dom";
import { Button }                        from "@/components/ui/button";
import { Input }                         from "@/components/ui/input";
import { useAuth }                       from "@/hooks/useAuth";
import { useTranslation }                from "react-i18next";
import {
  predictSymptoms,
  type PredictionResponse,
  type PatientMetadata,
} from "@/services/api";
import {
  Loader2, Send, Mic, MicOff, X, Brain, AlertTriangle,
  Stethoscope, ChevronRight, ShieldCheck, Activity, Heart,
} from "lucide-react";
import { toast }                    from "sonner";
import { motion, AnimatePresence }  from "framer-motion";

// ─── Types ─────────────────────────────────────────────────────────────────

type Message = {
  role:    "ai" | "user";
  content: string;
  isUrdu?: boolean;
  result?: PredictionResponse;
};

// Three-state voice lifecycle so the UI shows the right icon at each stage
type VoiceState = "idle" | "recording" | "transcribing";

const GUEST_MESSAGE_LIMIT = 5;
const API_BASE            = "http://localhost:8000";

// ─── Triage config ──────────────────────────────────────────────────────────

const TRIAGE_CONFIG = {
  "self-care":   { label: "Self-Care",   color: "text-emerald-400", border: "border-emerald-500/40", bg: "bg-emerald-500/10", icon: ShieldCheck,   dot: "bg-emerald-400" },
  "visit-gp":    { label: "Visit GP",    color: "text-amber-400",   border: "border-amber-500/40",   bg: "bg-amber-500/10",   icon: Activity,      dot: "bg-amber-400"   },
  "urgent-care": { label: "Urgent Care", color: "text-red-400",     border: "border-red-500/40",     bg: "bg-red-500/10",     icon: AlertTriangle, dot: "bg-red-400"     },
} as const;

// ─── Result card ────────────────────────────────────────────────────────────

const ResultCard = ({ data, onViewFull }: { data: PredictionResponse; onViewFull: () => void }) => {
  const triageKey  = (data.triage_level as keyof typeof TRIAGE_CONFIG) ?? "visit-gp";
  const triage     = TRIAGE_CONFIG[triageKey] ?? TRIAGE_CONFIG["visit-gp"];
  const TriageIcon = triage.icon;
  const topCond    = data.conditions?.[0];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-md">
      <div className={`rounded-t-xl px-4 py-3 flex items-center gap-3 ${triage.bg} border ${triage.border}`}>
        <TriageIcon className={`h-5 w-5 shrink-0 ${triage.color}`} />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Triage Level</p>
          <p className={`font-bold text-sm ${triage.color}`}>{triage.label}</p>
        </div>
        <span className={`h-2.5 w-2.5 rounded-full animate-pulse ${triage.dot}`} />
      </div>

      <div className="glass-card rounded-t-none border-t-0 p-4 space-y-4">
        {topCond && (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-0.5">Top Prediction</p>
              <p className="font-semibold text-sm">{topCond.name}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground mb-0.5">Confidence</p>
              <p className="font-bold text-primary text-sm">{topCond.confidence}%</p>
            </div>
          </div>
        )}

        {data.conditions && data.conditions.length > 0 && (
          <div className="space-y-2">
            {data.conditions.map((c) => (
              <div key={c.name}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground truncate max-w-[180px]">{c.name}</span>
                  <span className="text-primary font-medium">{c.confidence}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-primary/10 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${c.confidence}%` }} transition={{ duration: 0.6, ease: "easeOut" }} className="h-full rounded-full bg-primary" />
                </div>
              </div>
            ))}
          </div>
        )}

        {data.recommended_specialist && (
          <div className="flex items-center gap-2 rounded-lg bg-primary/5 border border-primary/20 px-3 py-2">
            <Stethoscope className="h-4 w-4 text-primary shrink-0" />
            <div>
              <p className="text-xs text-muted-foreground">Recommended Specialist</p>
              <p className="text-sm font-medium">{data.recommended_specialist}</p>
            </div>
          </div>
        )}

        {data.triage_explanation && (
          <p className="text-xs text-muted-foreground leading-relaxed border-l-2 border-primary/30 pl-3">{data.triage_explanation}</p>
        )}

        {data.self_care_tips && data.self_care_tips.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
              <Heart className="h-3 w-3" /> Self-Care Tips
            </p>
            <ul className="space-y-1">
              {data.self_care_tips.map((tip, i) => (
                <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                  <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary/50 shrink-0" />
                  {tip}
                </li>
              ))}
            </ul>
          </div>
        )}

        {data.key_symptoms && data.key_symptoms.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {data.key_symptoms.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary border border-primary/20">{s}</span>
            ))}
          </div>
        )}

        {data.profile_notes && data.profile_notes.length > 0 && (
          <div className="space-y-1">
            {data.profile_notes.map((note, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-amber-400/80">
                <span className="mt-0.5 shrink-0">ℹ</span>
                <span>{note}</span>
              </div>
            ))}
          </div>
        )}

        {data.red_flag_warnings && data.red_flag_warnings.length > 0 && (
          <div className="rounded-md bg-red-500/10 border border-red-500/30 px-3 py-2 space-y-1">
            {data.red_flag_warnings.map((warn, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-red-400 font-medium">
                <span className="shrink-0">⚠</span>
                <span>{warn}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between pt-1 border-t border-primary/10">
          <p className="text-[10px] text-muted-foreground/60 max-w-[200px] leading-tight">{data.disclaimer}</p>
          <Button size="sm" variant="ghost" className="text-xs text-primary hover:bg-primary/10 h-7 px-2 shrink-0" onClick={onViewFull}>
            Full Report <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

// ─── Main Component ─────────────────────────────────────────────────────────

const SymptomChecker = () => {
  const { user, role } = useAuth();
  const { t, i18n }   = useTranslation();
  const navigate       = useNavigate();

  const [input, setInput]             = useState("");
  const [messages, setMessages]       = useState<Message[]>([
    { role: "ai", content: t("chat.welcome") },
    { role: "ai", content: t("chat.welcome_prompt") },
  ]);
  const [loading, setLoading]         = useState(false);
  const [guestCount, setGuestCount]   = useState(0);
  // Three distinct voice states for clean UI feedback
  const [voiceState, setVoiceState]   = useState<VoiceState>("idle");
  const [showMetadata, setShowMetadata] = useState(false);
  const [metadata, setMetadata]       = useState<PatientMetadata>({
    age: undefined, sex: undefined, severity: undefined,
    chronic_disease: false, pregnant: false,
  });

  // MediaRecorder refs — hold the active recorder and collected audio chunks
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef   = useRef<Blob[]>([]);
  const streamRef        = useRef<MediaStream | null>(null);
  const messagesEndRef   = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Clean up mic stream when component unmounts mid-recording
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  // ── UC-02: Voice input via MediaRecorder → backend transcription ──────────
  const toggleVoice = async () => {
    // ── STOP: already recording → stop the recorder, send audio to backend ──
    if (voiceState === "recording") {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop(); // triggers the onstop handler below
      }
      return;
    }

    // ── Don't start a new one while the previous is transcribing ──
    if (voiceState === "transcribing") return;

    // ── START: request mic permission and begin recording ────────────────────
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Pick the best supported audio format
      // Chrome supports webm/opus; Firefox supports ogg/opus
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")
        ? "audio/ogg;codecs=opus"
        : "audio/webm"; // fallback

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current   = [];

      // Collect audio data chunks as they come in
      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      // When recording stops → send the collected audio to our backend
      recorder.onstop = async () => {
        // Release the mic indicator light immediately
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (audioChunksRef.current.length === 0) {
          setVoiceState("idle");
          toast.error("No audio captured. Please try again.");
          return;
        }

        setVoiceState("transcribing");
        toast.info("Processing your voice...");

        const blob     = new Blob(audioChunksRef.current, { type: mimeType });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");

        // Map i18n language to our backend's expected param
        const lang = i18n.language === "ur" ? "ur" : "en";

        try {
          const response = await fetch(`${API_BASE}/voice-input?language=${lang}`, {
            method: "POST",
            body:   formData,
          });

          if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error ${response.status}`);
          }

          const result = await response.json();
          const transcript: string = result.transcript || "";

          if (!transcript.trim()) {
            throw new Error("Transcription came back empty. Please speak more clearly.");
          }

          // Append transcript to whatever the user already typed
          setInput((prev) => (prev ? prev + " " + transcript : transcript));
          toast.success("Voice captured! Review and hit Send.");
        } catch (err: any) {
          toast.error(err.message || "Voice transcription failed. Please try again.");
        } finally {
          setVoiceState("idle");
        }
      };

      // Collect data every 250ms so we have chunks as they arrive
      recorder.start(250);
      setVoiceState("recording");
      toast.info("Recording... Speak your symptoms. Click mic again to stop.");

    } catch (err: any) {
      setVoiceState("idle");
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        toast.error("Microphone access denied. Allow mic access in your browser settings.");
      } else if (err.name === "NotFoundError") {
        toast.error("No microphone found. Connect a mic and try again.");
      } else {
        toast.error("Could not access microphone: " + (err.message || "Unknown error."));
      }
    }
  };

  // ── Send symptoms ───────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || input.length < 5) {
      toast.error("Please describe your symptoms (at least 5 characters).");
      return;
    }

    if (role === "guest") {
      if (guestCount >= GUEST_MESSAGE_LIMIT) {
        toast.error(t("guest.limit_reached"));
        return;
      }
      setGuestCount((c) => c + 1);
    }

    const userMsg = input.trim();
    const isUrdu  = /[\u0600-\u06FF]/.test(userMsg);

    setMessages((prev) => [...prev, { role: "user", content: userMsg, isUrdu }]);
    setInput("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "ai", content: t("chat.processing") }]);

    try {
      const data = await predictSymptoms(
        userMsg,
        i18n.language,
        metadata,
        user?.id ?? undefined,
      );

      sessionStorage.setItem("analysisResult", JSON.stringify(data));
      sessionStorage.setItem("queryId",        "q-" + Date.now());
      sessionStorage.setItem("lastSymptoms",   userMsg);
      if (data.query_id) {
        sessionStorage.setItem("consultId", data.query_id);
      }

      setMessages((prev) => {
        const clean = prev.filter((m) => m.content !== t("chat.processing"));
        return [
          ...clean,
          { role: "ai", content: data.summary || "Analysis complete.", isUrdu: i18n.language === "ur" },
          { role: "ai", content: "__result__", result: data },
        ];
      });
    } catch (err: unknown) {
      const error = err as Error;
      setMessages((prev) => prev.filter((m) => m.content !== t("chat.processing")));
      toast.error(error.message || "Failed to analyze symptoms.");
    } finally {
      setLoading(false);
    }
  };

  const handleEndSession = () => {
    // Stop any active recording before clearing session
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setVoiceState("idle");
    setMessages([
      { role: "ai", content: t("chat.welcome") },
      { role: "ai", content: t("chat.welcome_prompt") },
    ]);
    sessionStorage.removeItem("analysisResult");
    sessionStorage.removeItem("queryId");
    sessionStorage.removeItem("lastSymptoms");
    sessionStorage.removeItem("consultId");
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const isGuestLimited = role === "guest" && guestCount >= GUEST_MESSAGE_LIMIT;

  // Derive mic button appearance from voiceState
  const micTitle =
    voiceState === "recording"     ? "Click to stop recording"      :
    voiceState === "transcribing"  ? "Processing your voice..."      :
                                     "Click to start voice input";

  const micClass =
    voiceState === "recording"    ? "text-destructive animate-pulse" :
    voiceState === "transcribing" ? "text-amber-400 animate-spin"    :
                                    "text-muted-foreground";

  const inputPlaceholder =
    voiceState === "recording"    ? "🔴 Recording... click mic again to stop" :
    voiceState === "transcribing" ? "⏳ Transcribing your voice..."            :
                                    t("chat.placeholder");

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">

      {/* Header */}
      <div className="glass-card border-b border-primary/20 px-4 py-3">
        <div className="container flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="h-6 w-6 text-primary" />
            <h1 className="font-display text-sm font-bold">{t("app_name")}</h1>
          </div>
          <Button variant="ghost" size="sm" onClick={handleEndSession} className="text-destructive">
            <X className="h-4 w-4 mr-1" /> {t("chat.end_session")}
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="container max-w-3xl space-y-4">
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.content === "__result__" && msg.result ? (
                  <ResultCard data={msg.result} onViewFull={() => navigate("/explainability")} />
                ) : (
                  <div
                    className={`px-4 py-3 rounded-lg max-w-[80%] ${msg.role === "ai" ? "bg-muted" : "bg-primary text-primary-foreground"}`}
                    dir={msg.isUrdu ? "rtl" : "ltr"}
                  >
                    <p className="text-sm">{msg.content}</p>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* UC-03: Patient metadata panel */}
      <AnimatePresence>
        {showMetadata && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="border-t border-primary/20 bg-background/95 px-4 py-3 overflow-hidden"
          >
            <div className="container max-w-3xl">
              <p className="text-xs text-muted-foreground mb-3 font-semibold uppercase tracking-wider">
                Optional: Patient Details — helps personalise your results
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Age</label>
                  <input
                    type="number" min={1} max={120} placeholder="e.g. 32"
                    value={metadata.age ?? ""}
                    onChange={(e) => setMetadata((m) => ({ ...m, age: e.target.value ? parseInt(e.target.value) : undefined }))}
                    className="w-full rounded-md border border-primary/20 bg-muted/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Sex</label>
                  <select
                    value={metadata.sex ?? ""}
                    onChange={(e) => setMetadata((m) => ({ ...m, sex: (e.target.value as PatientMetadata["sex"]) || undefined }))}
                    className="w-full rounded-md border border-primary/20 bg-muted/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Select</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className="text-xs text-muted-foreground block mb-1">Severity: {metadata.severity ?? "—"}/5</label>
                  <input
                    type="range" min={1} max={5} step={1}
                    value={metadata.severity ?? 1}
                    onChange={(e) => setMetadata((m) => ({ ...m, severity: parseInt(e.target.value) }))}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                    <span>Mild</span><span>Moderate</span><span>Severe</span>
                  </div>
                </div>
                <div className="col-span-2 sm:col-span-3 flex flex-wrap gap-4 pt-1">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={metadata.chronic_disease ?? false}
                      onChange={(e) => setMetadata((m) => ({ ...m, chronic_disease: e.target.checked }))}
                      className="accent-primary" />
                    <span>Chronic disease (diabetes, hypertension, etc.)</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={metadata.pregnant ?? false}
                      onChange={(e) => setMetadata((m) => ({ ...m, pregnant: e.target.checked }))}
                      className="accent-primary" />
                    <span>Pregnant</span>
                  </label>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input bar */}
      <div className="border-t border-primary/20 bg-background/90 backdrop-blur px-4 py-4">
        <div className="container max-w-3xl">
          <div className="flex items-center gap-3 glass-card p-2">
            {/* Patient metadata toggle */}
            <Button
              variant="ghost" size="icon"
              title="Add patient details for personalised results"
              className={showMetadata ? "text-primary" : "text-muted-foreground"}
              onClick={() => setShowMetadata((v) => !v)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="8" r="4"/>
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                <line x1="19" y1="8" x2="23" y2="8"/>
                <line x1="21" y1="6" x2="21" y2="10"/>
              </svg>
            </Button>

            {/* Mic button: idle → red pulse (recording) → amber spin (transcribing) */}
            <Button
              variant="ghost" size="icon"
              title={micTitle}
              className={micClass}
              onClick={toggleVoice}
              disabled={voiceState === "transcribing" || loading}
            >
              {voiceState === "transcribing" ? (
                <Loader2 className="h-5 w-5" />
              ) : voiceState === "recording" ? (
                <MicOff className="h-5 w-5" />
              ) : (
                <Mic className="h-5 w-5" />
              )}
            </Button>

            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder={inputPlaceholder}
              disabled={loading || isGuestLimited || voiceState !== "idle"}
              className="flex-1 bg-transparent border-0 focus-visible:ring-0"
            />
            <Button size="icon" onClick={handleSend} disabled={loading || !input.trim() || isGuestLimited || voiceState !== "idle"}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>

          {/* Guest limit warning */}
          {role === "guest" && guestCount >= GUEST_MESSAGE_LIMIT - 1 && (
            <p className="text-xs text-amber-400 text-center mt-2">
              {GUEST_MESSAGE_LIMIT - guestCount <= 0
                ? "Message limit reached. Please sign up to continue."
                : `${GUEST_MESSAGE_LIMIT - guestCount} message(s) remaining as guest.`}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SymptomChecker;