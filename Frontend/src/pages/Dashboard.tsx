import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useTranslation } from "react-i18next";
import { fetchHistory, type HealthQuery } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Loader2, Clock, ArrowRight, Activity } from "lucide-react";
import TriageBadge from "@/components/TriageBadge";
import { format } from "date-fns";

const Dashboard = () => {
  const { user, role } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [queries, setQueries] = useState<HealthQuery[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
  if (role === "guest") navigate("/auth");
  if (!user && role === "patient") navigate("/auth");
}, [role, user, navigate]);

  useEffect(() => {
  if (!user) {
    setLoading(false);
    return;
  }
  fetchHistory(user.id)
    .then((data) => setQueries(data))
    .catch(() => setQueries([]))
    .finally(() => setLoading(false));
}, [user]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="container max-w-4xl py-8 md:py-12">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold glow-text">{t("dashboard.title")}</h1>
          <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
        </div>
        <Button onClick={() => navigate("/symptom-checker")} className="bg-primary hover:bg-primary/90">
          <Activity className="mr-2 h-4 w-4" /> {t("dashboard.new_check")}
        </Button>
      </div>

      {queries.length === 0 ? (
        <div className="glass-card-glow flex flex-col items-center justify-center py-16 text-center">
          <Activity className="mb-4 h-12 w-12 text-muted-foreground/40" />
          <h3 className="font-display text-lg font-semibold">{t("dashboard.no_queries")}</h3>
          <p className="mt-2 text-sm text-muted-foreground">{t("dashboard.no_queries_desc")}</p>
          <Button className="mt-6 bg-primary hover:bg-primary/90" onClick={() => navigate("/symptom-checker")}>
            {t("dashboard.check_symptoms")} <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {queries.map((q) => (
            <div key={q.id} className="glass-card hover:border-primary/40 transition-colors p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                    <Clock className="h-3 w-3" />
                    {format(new Date(q.created_at), "MMM d, yyyy 'at' h:mm a")}
                  </div>
                  <p className="text-sm font-medium line-clamp-2">{q.symptoms}</p>
                  {q.ai_response && (
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{q.ai_response}</p>
                  )}
                  {q.recommended_specialist && (
                    <p className="mt-1 text-xs"><strong>{t("results.specialist")}:</strong> {q.recommended_specialist}</p>
                  )}
                </div>
                {q.triage_level && (
                  <div className="shrink-0">
                    <TriageBadge level={q.triage_level} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
