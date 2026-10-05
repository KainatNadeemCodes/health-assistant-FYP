/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * The communication bridge between our Frontend and the FastAPI backend.
 * Handles symptom prediction, auth (login/register), history retrieval,
 * feedback submission, and PDF report generation.
 *
 * KEY FIX in this version:
 * - Added loginUser() and registerUser() functions (were completely missing)
 * - user_id now comes from the real database integer ID, not a fake timestamp string
 * - Added submitFeedback() for UC-08 star rating
 * -------------------------------------------------------------------------
 */

const API_BASE_URL = "http://localhost:8000";

// ─── Types ────────────────────────────────────────────────────────────────────

export type PatientMetadata = {
  age?:            number;
  sex?:            "Male" | "Female" | "Other";
  severity?:       number;
  chronic_disease?: boolean;
  pregnant?:       boolean;
};

export type PredictionResponse = {
  query_id:               string;
  summary:                string;
  conditions:             { name: string; confidence: number; description: string }[];
  triage_level:           "self-care" | "visit-gp" | "urgent-care";
  triage_explanation:     string;
  recommended_specialist: string;
  self_care_tips:         string[];
  key_symptoms:           string[];
  profile_notes:          string[];
  red_flag_warnings:      string[];
  disclaimer:             string;
};

export type HealthQuery = {
  id:                   string;
  symptoms:             string;
  ai_response:          string | null;
  triage_level:         string | null;
  recommended_specialist: string | null;
  predicted_conditions: PredictionResponse["conditions"] | null;
  created_at:           string;
};

// This is what the backend returns after login or register
export type AuthUser = {
  id:         number;   // real integer from the database — this is the user_id
  username:   string;
  email:      string;
  role:       string;
  age:        number | null;
  gender:     string | null;
  created_at: string;
};

// ─── Core request helper ──────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed with status ${res.status}`);
  }
  return res.json();
}

// ─── Auth endpoints (these were completely missing before) ────────────────────

/**
 * POST /auth/login
 * Authenticates a registered user and returns their full profile.
 * The id field in the response is the real database integer — save this as user_id.
 */
export async function loginUser(email: string, password: string): Promise<AuthUser> {
  return request<AuthUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

/**
 * POST /auth/register
 * Creates a new account and returns the created user profile.
 * Same as login — the id field is the real database integer.
 */
export async function registerUser(
  fullName: string,
  email:    string,
  password: string
): Promise<AuthUser> {
  return request<AuthUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
}

// ─── Symptom prediction ───────────────────────────────────────────────────────

/**
 * POST /predict
 * Sends symptoms + optional patient metadata to the FastAPI ML backend.
 * Pass the real user_id (integer as string) if the user is logged in.
 */
export async function predictSymptoms(
  symptoms:  string,
  language:  string = "en",
  metadata?: PatientMetadata,
  userId?:   string
): Promise<PredictionResponse> {
  return request<PredictionResponse>("/predict", {
    method: "POST",
    body: JSON.stringify({
      symptoms,
      language,
      user_id: userId || null,
      ...metadata,
    }),
  });
}

// ─── History ──────────────────────────────────────────────────────────────────

/**
 * GET /history
 * Fetches past consultations for a logged-in user.
 * userId must be the real integer id from the database, passed as a string.
 */
export async function fetchHistory(userId: string): Promise<HealthQuery[]> {
  return request<HealthQuery[]>(`/history?user_id=${encodeURIComponent(userId)}`);
}

// ─── Feedback (UC-08) ─────────────────────────────────────────────────────────

/**
 * POST /feedback
 * Submits a 1-5 star rating for a consultation.
 * consultId is the id returned by /predict in the query_id field.
 */
export async function submitFeedback(
  consultId: number | string,
  rating:    number,
  comments?: string
): Promise<void> {
  await request("/feedback", {
    method: "POST",
    body: JSON.stringify({
      consult_id: Number(consultId),
      rating,
      comments: comments || null,
    }),
  });
}

// ─── PDF report ───────────────────────────────────────────────────────────────

/**
 * POST /generate-pdf
 * Sends the full prediction result to the backend PDF engine.
 * Works for both guests and registered users because no DB lookup needed.
 */
export async function generatePdf(
  queryId:     string,
  result:      PredictionResponse,
  symptoms:    string,
  patientName: string = "Patient"
): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/generate-pdf`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query_id:               queryId,
      patient_name:           patientName,
      symptoms:               symptoms,
      conditions:             result.conditions,
      triage_level:           result.triage_level,
      triage_explanation:     result.triage_explanation,
      recommended_specialist: result.recommended_specialist,
      key_symptoms:           result.key_symptoms,
      summary:                result.summary,
    }),
  });
  if (!res.ok) throw new Error("PDF generation failed");
  return res.blob();
}

// ─── Admin types ──────────────────────────────────────────────────────────────

export type AdminAnalytics = {
  total_consultations:     number;
  total_users:             number;
  total_feedback:          number;
  avg_rating:              number;
  condition_distribution:  { condition: string; count: number }[];
  triage_distribution:     Record<string, number>;
  daily_trend:             { date: string; count: number }[];
  specialist_distribution: { specialist: string; count: number }[];
  rating_distribution:     Record<string, number>;
};

export type AdminUser = {
  id:                 number;
  username:           string;
  email:              string;
  role:               string;
  age:                number | null;
  gender:             string | null;
  consultation_count: number;
  created_at:         string;
};

// ─── Admin endpoints ──────────────────────────────────────────────────────────

export async function fetchAdminAnalytics(adminKey: string): Promise<AdminAnalytics> {
  return request<AdminAnalytics>(`/admin/analytics?admin_key=${encodeURIComponent(adminKey)}`);
}

export async function fetchAdminUsers(adminKey: string): Promise<AdminUser[]> {
  return request<AdminUser[]>(`/admin/users?admin_key=${encodeURIComponent(adminKey)}`);
}

export async function updateUserRole(
  userId:   number,
  role:     string,
  adminKey: string
): Promise<void> {
  await request(`/admin/users/${userId}/role?admin_key=${encodeURIComponent(adminKey)}`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}