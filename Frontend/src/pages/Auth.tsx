import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Brain, Loader2, Lock, Mail } from "lucide-react";
import { toast } from "sonner";
import LanguageToggle from "@/components/LanguageToggle";

const Auth = () => {
  const { user, signIn, signUp, setRole } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const [mode, setMode] = useState<"login" | "register">(
    searchParams.get("tab") === "signup" ? "register" : "login"
  );
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  useEffect(() => {
    if (user) navigate("/dashboard");
  }, [user, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { error } = await signIn(email, password);
    if (error) toast.error(error.message || error);
    else navigate("/dashboard");
    setLoading(false);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { error } = await signUp(email, password, fullName);
    if (error) toast.error(error.message || error);
    else {
      toast.success(t("auth.sign_up_success"));
      navigate("/dashboard");
    }
    setLoading(false);
  };

  const handleGuest = () => {
    setRole("guest");
    navigate("/symptom-checker");
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center">
            <Brain className="h-16 w-16 text-primary glow-text" />
          </div>
          <h1 className="font-display text-2xl font-bold text-primary glow-text">{t("app_name")}</h1>
          <div className="mt-4 flex justify-center">
            <LanguageToggle />
          </div>
        </div>

        <div className="glass-card-glow p-8">
          <h2 className="mb-6 text-center font-display text-xl font-semibold">
            {t("auth.login_title")}
            <div className="mx-auto mt-2 h-0.5 w-20 bg-primary/50" />
          </h2>

          <form onSubmit={mode === "login" ? handleLogin : handleRegister} className="space-y-4">
            {mode === "register" && (
              <div className="relative">
                <Input
                  placeholder={t("auth.full_name")}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="bg-muted/50 border-primary/20 pl-10 h-12"
                />
                <div className="absolute left-3 top-1/2 -translate-y-1/2">
                  <Lock className="h-4 w-4 text-muted-foreground" />
                </div>
              </div>
            )}

            <div className="relative">
              <Input
                type="email"
                placeholder={t("auth.email")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-muted/50 border-primary/20 pl-10 h-12"
              />
              <div className="absolute left-3 top-1/2 -translate-y-1/2">
                <Mail className="h-4 w-4 text-muted-foreground" />
              </div>
            </div>

            <div className="relative">
              <Input
                type="password"
                placeholder={t("auth.password")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="bg-muted/50 border-primary/20 pl-10 h-12"
              />
              <div className="absolute left-3 top-1/2 -translate-y-1/2">
                <Lock className="h-4 w-4 text-muted-foreground" />
              </div>
            </div>

            {mode === "login" && (
              <div className="text-start">
                <button type="button" className="text-xs text-primary hover:underline">
                  {t("auth.forgot_password")}
                </button>
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 bg-primary hover:bg-primary/90 text-lg font-semibold"
            >
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {mode === "login" ? t("auth.login") : t("auth.register")}
            </Button>
          </form>

          <div className="mt-4 space-y-3">
            <Button
              variant="outline"
              className="w-full h-12 border-primary/30 hover:bg-primary/10"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? t("auth.register") : t("auth.login")}
            </Button>

            <Button
              variant="outline"
              className="w-full h-12 border-primary/30 hover:bg-primary/10"
              onClick={handleGuest}
            >
              {t("auth.continue_guest")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Auth;
