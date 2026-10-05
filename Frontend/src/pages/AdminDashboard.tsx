/**
 * FILE: src/pages/AdminDashboard.tsx
 * PURPOSE: Admin / Clinician Analytics Dashboard
 * ROLE: Admin only — protected by token login
 *
 * FIX in this version:
 *  - Changed ?token= to ?admin_key= to match what app.py expects
 *  - Admin login now sends the right param to /admin/login
 *  - All fetch calls now use admin_key consistently
 */

import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid,
} from "recharts";
import {
  Users, Activity, Star, ShieldAlert, Stethoscope,
  LogIn, Loader2, RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input }  from "@/components/ui/input";
import { toast }  from "sonner";

const API = "http://localhost:8000";

const TRIAGE_COLORS: Record<string, string> = {
  Low:    "#10b981",
  Medium: "#f59e0b",
  High:   "#ef4444",
};
const BAR_COLORS = [
  "#3b82f6","#8b5cf6","#06b6d4","#f59e0b",
  "#10b981","#ef4444","#ec4899","#14b8a6","#f97316","#6366f1",
];

interface Analytics {
  total_consultations:  number;
  total_users:          number;
  avg_rating:           number;
  total_feedback:       number;
  triage_distribution:  Record<string, number>;
  top_conditions:       { prediction: string; count: number }[];
  top_specialists:      { specialist: string; count: number }[];
  daily_activity:       { date: string; count: number }[];
  recent_consultations: {
    id: number; prediction: string; triage_level: string;
    specialist: string; timestamp: string; symptoms_preview: string;
  }[];
}

interface AdminUser {
  id: number; username: string; role: string;
  created_at: string; consultation_count: number;
}

const StatCard = ({ icon: Icon, label, value, sub, color = "text-primary" }: {
  icon: React.ElementType; label: string; value: string | number;
  sub?: string; color?: string;
}) => (
  <div className="rounded-xl border border-primary/20 bg-muted/30 p-5 flex items-start gap-4">
    <div className="mt-0.5 rounded-lg bg-primary/10 p-2.5 shrink-0">
      <Icon className={`h-5 w-5 ${color}`} />
    </div>
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">{label}</p>
      <p className={`text-2xl font-bold mt-0.5 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  </div>
);

const TriagePill = ({ level }: { level: string }) => {
  const cfg: Record<string, string> = {
    Low:    "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    Medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    High:   "bg-red-500/15 text-red-400 border-red-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${cfg[level] ?? cfg.Medium}`}>
      {level}
    </span>
  );
};

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="rounded-xl border border-primary/20 bg-muted/20 p-5">
    <h3 className="text-sm font-semibold text-primary mb-4 uppercase tracking-wider">{title}</h3>
    {children}
  </div>
);

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-primary/20 bg-background/95 px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-primary mb-1">{payload[0]?.payload?.fullName ?? label}</p>
      <p className="text-muted-foreground">
        {payload[0]?.name ?? "Count"}:{" "}
        <span className="text-foreground font-medium">{payload[0]?.value}</span>
      </p>
    </div>
  );
};

const TABS = ["overview", "conditions", "users", "recent"] as const;
type Tab = typeof TABS[number];

// The admin key is stored in sessionStorage under this key
const ADMIN_KEY_STORAGE = "adminKey";

const AdminDashboard = () => {
  // We store the actual key string (admin2025) not a token
  const [adminKey,     setAdminKey]     = useState<string | null>(() => sessionStorage.getItem(ADMIN_KEY_STORAGE));
  const [password,     setPassword]     = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [analytics,    setAnalytics]    = useState<Analytics | null>(null);
  const [users,        setUsers]        = useState<AdminUser[]>([]);
  const [loading,      setLoading]      = useState(false);
  const [tab,          setTab]          = useState<Tab>("overview");

  const fetchData = useCallback(async (key: string) => {
    setLoading(true);
    try {
      // Both endpoints now use admin_key= (matches app.py exactly)
      const [aRes, uRes] = await Promise.all([
        fetch(`${API}/admin/analytics?admin_key=${encodeURIComponent(key)}`),
        fetch(`${API}/admin/users?admin_key=${encodeURIComponent(key)}`),
      ]);

      // If auth fails, clear the stored key and show login again
      if (aRes.status === 403 || uRes.status === 403) {
        toast.error("Admin session expired. Please log in again.");
        sessionStorage.removeItem(ADMIN_KEY_STORAGE);
        setAdminKey(null);
        setLoading(false);
        return;
      }

      if (!aRes.ok || !uRes.ok) throw new Error("Server error loading analytics.");

      const [a, u] = await Promise.all([aRes.json(), uRes.json()]);
      setAnalytics(a);
      setUsers(u);
    } catch (err: any) {
      toast.error(err.message || "Failed to load analytics. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (adminKey) fetchData(adminKey);
  }, [adminKey, fetchData]);

  const handleLogin = async () => {
    if (!password.trim()) {
      toast.error("Please enter the admin password.");
      return;
    }
    setLoginLoading(true);
    try {
      const res = await fetch(`${API}/admin/login`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ password }),
      });

      if (!res.ok) {
        toast.error("Incorrect admin password.");
        setLoginLoading(false);
        return;
      }

      // app.py returns { token: "admin2025" } — we store that as the key
      const body = await res.json();
      const key  = body.token || password;

      sessionStorage.setItem(ADMIN_KEY_STORAGE, key);
      setAdminKey(key);
      toast.success("Welcome, Admin.");
    } catch {
      toast.error("Could not reach backend. Make sure it is running on port 8000.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSignOut = () => {
    sessionStorage.removeItem(ADMIN_KEY_STORAGE);
    setAdminKey(null);
    setAnalytics(null);
    setUsers([]);
    setPassword("");
  };

  // ── Login gate ──────────────────────────────────────────────────────────────
  if (!adminKey) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="rounded-2xl border border-primary/25 bg-muted/30 backdrop-blur p-8 space-y-6">
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-xl bg-primary/15">
                <ShieldAlert className="h-7 w-7 text-primary" />
              </div>
              <h1 className="text-xl font-bold text-primary">Admin Access</h1>
              <p className="text-sm text-muted-foreground mt-1">Clinician / Administrator Portal</p>
            </div>
            <div className="space-y-3">
              <Input
                type="password"
                placeholder="Admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                className="bg-muted/50 border-primary/20 h-11"
                autoFocus
              />
              <Button
                className="w-full h-11 bg-primary hover:bg-primary/90"
                onClick={handleLogin}
                disabled={loginLoading}
              >
                {loginLoading
                  ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  : <LogIn className="h-4 w-4 mr-2" />
                }
                Sign In
              </Button>
            </div>
            <p className="text-center text-[11px] text-muted-foreground/60">
              Default password: <code className="text-primary">admin2025</code>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading state ───────────────────────────────────────────────────────────
  if (loading || !analytics) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const triageData = Object.entries(analytics.triage_distribution).map(([name, value]) => ({
    name, value, fill: TRIAGE_COLORS[name] ?? "#6366f1",
  }));

  const conditionsData = analytics.top_conditions.map((c) => ({
    name:     c.prediction.length > 18 ? c.prediction.slice(0, 16) + "…" : c.prediction,
    fullName: c.prediction,
    count:    c.count,
  }));

  const specialistsData = analytics.top_specialists.map((s) => ({
    name:     s.specialist.length > 22 ? s.specialist.slice(0, 20) + "…" : s.specialist,
    fullName: s.specialist,
    count:    s.count,
  }));

  const dailyData = analytics.daily_activity.map((d) => ({
    date:          d.date.slice(5),
    consultations: d.count,
  }));

  return (
    <div className="container max-w-6xl py-8 space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-bold glow-text">Admin Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Anonymized platform analytics · Clinician review panel
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline" size="sm"
            className="border-primary/30 gap-1.5"
            onClick={() => fetchData(adminKey!)}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={handleSignOut}>
            Sign Out
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Activity}    label="Total Consultations"  value={analytics.total_consultations} color="text-primary" />
        <StatCard icon={Users}       label="Registered Patients"  value={analytics.total_users}         color="text-blue-400" />
        <StatCard icon={Star}        label="Avg. Feedback Rating"
          value={analytics.avg_rating > 0 ? `${analytics.avg_rating} / 5` : "N/A"}
          sub={`${analytics.total_feedback} responses`}
          color="text-amber-400"
        />
        <StatCard icon={ShieldAlert} label="High Triage Cases"
          value={analytics.triage_distribution["High"] ?? 0}
          sub="urgent-care escalations"
          color="text-red-400"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg border border-primary/20 bg-muted/20 p-1 w-fit flex-wrap">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t === "recent" ? "Recent Activity" : t}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ── */}
      {tab === "overview" && (
        <div className="grid md:grid-cols-2 gap-5">
          <Section title="Triage Level Distribution">
            {triageData.length > 0 ? (
              <div className="flex flex-col items-center gap-4">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={triageData} cx="50%" cy="50%"
                      innerRadius={55} outerRadius={90}
                      paddingAngle={3} dataKey="value"
                    >
                      {triageData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background:"#0f0f0f", border:"1px solid #3b82f640", borderRadius:8, fontSize:12 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex gap-4 flex-wrap justify-center">
                  {triageData.map((d) => (
                    <div key={d.name} className="flex items-center gap-1.5 text-xs">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.fill }} />
                      <span className="text-muted-foreground">{d.name}</span>
                      <span className="font-semibold">{d.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No consultation data yet.</p>
            )}
          </Section>

          <Section title="Consultation Activity (Last 14 Days)">
            {dailyData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={dailyData} margin={{ top:5, right:10, left:-20, bottom:0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3b82f620" />
                  <XAxis dataKey="date" tick={{ fontSize:10, fill:"#64748b" }} />
                  <YAxis tick={{ fontSize:10, fill:"#64748b" }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background:"#0f0f0f", border:"1px solid #3b82f640", borderRadius:8, fontSize:12 }} />
                  <Line
                    type="monotone" dataKey="consultations"
                    stroke="#3b82f6" strokeWidth={2}
                    dot={{ r:3, fill:"#3b82f6" }} activeDot={{ r:5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No activity in last 14 days.</p>
            )}
          </Section>

          <Section title="Top Referred Specialists">
            {specialistsData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={specialistsData} layout="vertical" margin={{ left:0, right:10 }}>
                  <XAxis type="number" tick={{ fontSize:10, fill:"#64748b" }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize:10, fill:"#64748b" }} width={130} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" radius={[0,4,4,0]}>
                    {specialistsData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No specialist data yet.</p>
            )}
          </Section>

          <Section title="User Satisfaction">
            <div className="flex flex-col items-center justify-center h-[220px] gap-3">
              <div className="text-6xl font-bold text-primary">
                {analytics.avg_rating > 0 ? analytics.avg_rating.toFixed(1) : "—"}
              </div>
              <div className="flex gap-1">
                {[1,2,3,4,5].map((star) => (
                  <Star key={star} className={`h-6 w-6 ${
                    star <= Math.round(analytics.avg_rating)
                      ? "text-amber-400 fill-amber-400"
                      : "text-muted-foreground"
                  }`} />
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                Based on {analytics.total_feedback} {analytics.total_feedback === 1 ? "review" : "reviews"}
              </p>
            </div>
          </Section>
        </div>
      )}

      {/* ── CONDITIONS ── */}
      {tab === "conditions" && (
        <Section title="Top 10 Predicted Conditions (Anonymized)">
          {conditionsData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={380}>
                <BarChart data={conditionsData} margin={{ top:10, right:10, left:-10, bottom:60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3b82f620" />
                  <XAxis dataKey="name" tick={{ fontSize:11, fill:"#64748b" }} angle={-35} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize:11, fill:"#64748b" }} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" radius={[4,4,0,0]}>
                    {conditionsData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-6 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-primary/20 text-left">
                      {["Rank","Condition","Consultations"].map((h) => (
                        <th key={h} className="py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.top_conditions.map((c, i) => (
                      <tr key={i} className="border-b border-primary/10 hover:bg-primary/5 transition-colors">
                        <td className="py-2.5 pr-4 text-muted-foreground text-xs">#{i+1}</td>
                        <td className="py-2.5 pr-4 font-medium">{c.prediction}</td>
                        <td className="py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 rounded-full bg-primary/10 flex-1 max-w-[120px]">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{ width:`${(c.count / (analytics.top_conditions[0]?.count || 1)) * 100}%` }}
                              />
                            </div>
                            <span className="font-semibold text-primary">{c.count}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-12">No condition data yet.</p>
          )}
        </Section>
      )}

      {/* ── USERS ── */}
      {tab === "users" && (
        <Section title={`Registered Users (${users.length})`}>
          {users.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-primary/20 text-left">
                    {["ID","Username","Role","Consultations","Joined"].map((h) => (
                      <th key={h} className="py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-primary/10 hover:bg-primary/5 transition-colors">
                      <td className="py-2.5 pr-4 text-muted-foreground text-xs">#{u.id}</td>
                      <td className="py-2.5 pr-4 font-medium">{u.username}</td>
                      <td className="py-2.5 pr-4">
                        <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                          u.role === "Admin"
                            ? "bg-primary/15 text-primary border-primary/30"
                            : "bg-blue-500/15 text-blue-400 border-blue-500/30"
                        }`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-primary font-semibold">{u.consultation_count}</td>
                      <td className="py-2.5 text-xs text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-12">No registered users yet.</p>
          )}
        </Section>
      )}

      {/* ── RECENT ACTIVITY ── */}
      {tab === "recent" && (
        <Section title="Recent Consultations (Anonymized — No Patient PII)">
          {analytics.recent_consultations.length > 0 ? (
            <div className="space-y-3">
              {analytics.recent_consultations.map((c) => (
                <div
                  key={c.id}
                  className="rounded-lg border border-primary/15 bg-muted/20 p-4 flex flex-col sm:flex-row sm:items-start gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-xs text-muted-foreground font-mono">#{c.id}</span>
                      <TriagePill level={c.triage_level} />
                      <span className="text-xs text-muted-foreground ml-auto">
                        {new Date(c.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm font-medium">{c.prediction}</p>
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{c.symptoms_preview}…</p>
                  </div>
                  <div className="shrink-0 flex items-center gap-1.5 text-xs text-muted-foreground bg-primary/5 rounded-lg px-3 py-2 border border-primary/15">
                    <Stethoscope className="h-3.5 w-3.5 text-primary" />{c.specialist}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-12">No recent consultations.</p>
          )}
        </Section>
      )}

      <p className="text-center text-[11px] text-muted-foreground/50 pb-4">
        All data is anonymized — no patient names, emails or personal identifiers shown.
        · AI Smart Health Assistant Admin Portal · F25PROJECT664B0
      </p>
    </div>
  );
};

export default AdminDashboard;
