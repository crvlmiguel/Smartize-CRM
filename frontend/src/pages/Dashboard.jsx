import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, FolderKanban, Send, MailCheck, MailOpen, MousePointerClick,
  Reply, AlertTriangle, TrendingUp,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import api from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/common";

const CARDS = [
  { key: "contacts", label: "Contactos", icon: Users, color: "text-primary" },
  { key: "groups", label: "Grupos", icon: FolderKanban, color: "text-primary" },
  { key: "campaigns", label: "Campanhas", icon: Send, color: "text-primary" },
  { key: "sent", label: "Enviados", icon: MailCheck, color: "text-blue-600" },
  { key: "delivered", label: "Entregues", icon: MailCheck, color: "text-emerald-600" },
  { key: "opened", label: "Abertos", icon: MailOpen, color: "text-amber-600" },
  { key: "clicked", label: "Cliques", icon: MousePointerClick, color: "text-violet-600" },
  { key: "replied", label: "Respostas", icon: Reply, color: "text-emerald-600" },
  { key: "bounced", label: "Bounces", icon: AlertTriangle, color: "text-red-600" },
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/dashboard").then((r) => setData(r.data)).catch(() => {});
  }, []);

  const totals = data?.totals || {};

  return (
    <div data-testid="dashboard-page">
      <PageHeader title="Dashboard" subtitle="Visão geral da atividade de outreach." />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        {CARDS.map((c) => (
          <div key={c.key} className="bg-card border border-border rounded-md p-4" data-testid={`stat-${c.key}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{c.label}</span>
              <c.icon size={16} className={c.color} />
            </div>
            <div className="font-heading font-black text-3xl mt-2 tracking-tight">
              {data ? (totals[c.key] ?? 0) : "—"}
            </div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-card border border-border rounded-md p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-primary" />
            <h2 className="font-heading font-bold text-lg">Evolução diária</h2>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={data?.daily || []} margin={{ left: -20, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="gSent" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0055FF" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#0055FF" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gOpen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} fontSize={11} tickLine={false} axisLine={false} />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ borderRadius: 6, border: "1px solid #E4E4E7", fontSize: 12 }} />
              <Area type="monotone" dataKey="enviados" stroke="#0055FF" strokeWidth={2} fill="url(#gSent)" name="Enviados" />
              <Area type="monotone" dataKey="abertos" stroke="#F59E0B" strokeWidth={2} fill="url(#gOpen)" name="Abertos" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-card border border-border rounded-md p-5">
          <h2 className="font-heading font-bold text-lg mb-4">Últimas campanhas</h2>
          <div className="space-y-2">
            {(data?.recent_campaigns || []).length === 0 && (
              <p className="text-sm text-muted-foreground">Sem campanhas ainda.</p>
            )}
            {(data?.recent_campaigns || []).map((c) => (
              <button
                key={c.id}
                onClick={() => navigate(`/campanhas/${c.id}`)}
                data-testid={`recent-campaign-${c.id}`}
                className="w-full text-left p-3 rounded-md border border-border hover:bg-secondary transition-colors duration-150"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-sm truncate">{c.name}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {c.stats?.sent || 0} enviados · {c.stats?.open_rate || 0}% abertura
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
