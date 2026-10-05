/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * The app's control center. It manages navigation, user authentication 
 * states, and role-based access (Guest/Patient/Admin) in one place.
 * -------------------------------------------------------------------------
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth, type UserRole } from "@/hooks/useAuth";
import { useTranslation } from "react-i18next";
import { Brain, Menu, X, LogOut, User, LayoutDashboard } from "lucide-react";
import LanguageToggle from "@/components/LanguageToggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: "guest", label: "Guest" },
  { value: "patient", label: "Patient" },
  { value: "admin", label: "Admin" },
];

const Navbar = () => {
  const { user, role, signOut, setRole } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { t } = useTranslation();

  return (
    <nav className="sticky top-0 z-50 border-b border-primary/20 bg-background/80 backdrop-blur-lg">
      <div className="container flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
            <Brain className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-display text-xl font-bold text-foreground glow-text">{t("app_name")}</span>
        </Link>

        <div className="hidden items-center gap-4 md:flex">
          <Link to="/symptom-checker" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">
            {t("nav.symptom_checker")}
          </Link>
          <Link to="/about" className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors">
            {t("nav.about")}
          </Link>

          {/* Role switcher for demo */}
          <select
            value={role}
            onChange={(e) => {
              const newRole = e.target.value as UserRole;
              setRole(newRole);
              if (newRole === "admin") navigate("/admin");
              if (newRole === "patient") {
                if (user) navigate("/dashboard");
                else navigate("/auth");
              }
              if (newRole === "guest")   navigate("/");
            }}
            className="text-xs bg-muted/50 border border-primary/20 rounded px-2 py-1 text-foreground"
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>

          <LanguageToggle />

          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2 border-primary/30">
                  <User className="h-4 w-4" />
                  {user.fullName}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="glass-card">
                <DropdownMenuItem onClick={() => navigate("/dashboard")}>
                  <LayoutDashboard className="mr-2 h-4 w-4" />
                  {t("nav.dashboard")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => signOut()}>
                  <LogOut className="mr-2 h-4 w-4" />
                  {t("nav.sign_out")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button size="sm" onClick={() => navigate("/auth")} className="bg-primary hover:bg-primary/90">
              {t("nav.sign_in")}
            </Button>
          )}
        </div>

        <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(!mobileOpen)}>
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </div>

      {mobileOpen && (
        <div className="border-t border-primary/20 glass-card p-4 md:hidden">
          <div className="flex flex-col gap-3">
            <Link to="/symptom-checker" className="text-sm font-medium" onClick={() => setMobileOpen(false)}>
              {t("nav.symptom_checker")}
            </Link>
            <Link to="/about" className="text-sm font-medium" onClick={() => setMobileOpen(false)}>
              {t("nav.about")}
            </Link>
            <select
              value={role}
              onChange={(e) => {
                const newRole = e.target.value as UserRole;
                setRole(newRole);
                if (newRole === "admin") navigate("/admin");
                if (newRole === "patient") {
                if (user) navigate("/dashboard");
                else navigate("/auth");
              }
                if (newRole === "guest")   navigate("/");
              }}
              className="text-xs bg-muted/50 border border-primary/20 rounded px-2 py-1 text-foreground"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
            <LanguageToggle />
            {user ? (
              <>
                <Link to="/dashboard" className="text-sm font-medium" onClick={() => setMobileOpen(false)}>
                  {t("nav.dashboard")}
                </Link>
                <Button variant="outline" size="sm" className="border-primary/30" onClick={() => { signOut(); setMobileOpen(false); }}>
                  {t("nav.sign_out")}
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={() => { navigate("/auth"); setMobileOpen(false); }}>
                {t("nav.sign_in")}
              </Button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
