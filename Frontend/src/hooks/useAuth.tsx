/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * The central hub for user identity and access control.
 * Manages session state for Patients, Admins, and Guests.
 *
 * KEY FIX in this version:
 * - signIn() and signUp() now call the real FastAPI backend
 * - User ID is the real integer from the database, not a fake timestamp
 * - User session is persisted in localStorage so it survives page refresh
 * - Guest mode still works without any backend call
 * -------------------------------------------------------------------------
 */

import {
  useState,
  useEffect,
  createContext,
  useContext,
  useCallback,
} from "react";
import { loginUser, registerUser } from "@/services/api";

export type UserRole = "guest" | "patient" | "admin";

type User = {
  id: string;       // real integer from DB stored as string
  email: string;
  fullName: string;
  role: UserRole;
};

type AuthContextType = {
  user: User | null;
  role: UserRole;
  loading: boolean;
  signIn:  (email: string, password: string) => Promise<{ error: any }>;
  signUp:  (email: string, password: string, fullName: string) => Promise<{ error: any }>;
  signOut: () => void;
  setRole: (role: UserRole) => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Keys used to persist the session in localStorage
const STORAGE_USER = "health_user";
const STORAGE_ROLE = "health_role";

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [loading, setLoading]     = useState(true);
  const [user, setUser]           = useState<User | null>(null);
  const [role, setRoleState]      = useState<UserRole>("guest");

  // Restore session from localStorage on first load
  // This means the user stays logged in after a page refresh
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem(STORAGE_USER);
      const storedRole = localStorage.getItem(STORAGE_ROLE) as UserRole | null;
      if (storedUser) {
        setUser(JSON.parse(storedUser));
        setRoleState(storedRole || "patient");
      }
    } catch {
      // If localStorage is corrupted just start fresh
      localStorage.removeItem(STORAGE_USER);
      localStorage.removeItem(STORAGE_ROLE);
    } finally {
      setLoading(false);
    }
  }, []);

  // Helper that saves the session to localStorage and state together
  const persistSession = useCallback((newUser: User, newRole: UserRole) => {
    setUser(newUser);
    setRoleState(newRole);
    localStorage.setItem(STORAGE_USER, JSON.stringify(newUser));
    localStorage.setItem(STORAGE_ROLE, newRole);
  }, []);

  // ── signIn — calls POST /auth/login on the real backend ──────────────────
  const signIn = async (email: string, password: string) => {
    try {
      // This now calls the real FastAPI endpoint
      const dbUser = await loginUser(email, password);

      // dbUser.id is the real integer from the users table
      const newUser: User = {
        id:       String(dbUser.id),      // real DB id, not a fake timestamp
        email:    dbUser.email,
        fullName: dbUser.username,
        role:     dbUser.role === "Patient" ? "patient" : "guest",
      };

      persistSession(newUser, newUser.role);
      return { error: null };

    } catch (err: any) {
      // Parse the error message from the backend response
      let message = "Login failed. Please check your credentials.";
      try {
        const parsed = JSON.parse(err.message);
        message = parsed.detail || message;
      } catch {
        message = err.message || message;
      }
      return { error: { message } };
    }
  };

  // ── signUp — calls POST /auth/register on the real backend ───────────────
  const signUp = async (email: string, password: string, fullName: string) => {
    try {
      // This now calls the real FastAPI endpoint
      const dbUser = await registerUser(fullName, email, password);

      // dbUser.id is the real integer from the users table
      const newUser: User = {
        id:       String(dbUser.id),      // real DB id, not "patient-" + Date.now()
        email:    dbUser.email,
        fullName: dbUser.username,
        role:     "patient",
      };

      persistSession(newUser, "patient");
      return { error: null };

    } catch (err: any) {
      let message = "Registration failed. This email may already be registered.";
      try {
        const parsed = JSON.parse(err.message);
        message = parsed.detail || message;
      } catch {
        message = err.message || message;
      }
      return { error: { message } };
    }
  };

  // ── signOut — clears everything ───────────────────────────────────────────
  const signOut = () => {
    setUser(null);
    setRoleState("guest");
    localStorage.removeItem(STORAGE_USER);
    localStorage.removeItem(STORAGE_ROLE);
    // Also clear any symptom session data
    sessionStorage.removeItem("analysisResult");
    sessionStorage.removeItem("queryId");
    sessionStorage.removeItem("consultId");
    sessionStorage.removeItem("lastSymptoms");
  };

  // ── setRole — used for guest mode and admin switching ────────────────────
  const setRole = useCallback((r: UserRole) => {
    setRoleState(r);
    if (r === "guest") {
      setUser(null);
      localStorage.removeItem(STORAGE_USER);
      localStorage.removeItem(STORAGE_ROLE);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, role, loading, signIn, signUp, signOut, setRole }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};