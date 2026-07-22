import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Reply, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import api, { apiError } from "@/lib/api";
import { StatusBadge } from "@/components/common";

const METRICS = [
  { key: "sent", label: "Enviados" },
  { key: "delivered", label: "Entregues" },
  { key: "opened", label: "Abertos" },
  { key: "clicked", label: "Cliques" },
  { key: "replied", label: "Respostas" },
  { key: "bounced", label: "Bounces" },
];
const RATES = [
  { key: "delivery_rate", label: "Taxa de entrega" },
  { key: "open_rate", label: "Taxa de abertura" },
  { key: "click_rate", label: "Taxa de cliques" },
  { key: "reply_rate", label: "Taxa de resposta" },
];

export default function CampaignDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    api.get(`/campaigns/${id}/stats`).then((r) => setData(r.data)).catch((e) => toast.error(apiError(e)));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const markReplied = async (contactId) => {
    try { await api.post(`/campaigns/${id}/contacts/${contactId}/reply`); toast.success("Marcado como respondido"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  if (!data) return <div className="text-muted-foreground">A carregar…</div>;
  const { campaign, stats, recipients } = data;

  return (
    <div data-testid="campaign-detail-page">
      <button onClick={() => navigate("/campanhas")} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-4" data-testid="back-button">
        <ArrowLeft size={16} /> Campanhas
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-heading font-black text-3xl tracking-tight">{campaign.name}</h1>
            <StatusBadge status={campaign.status} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">{stats.total} destinatários · {stats.pending} na fila</p>
        </div>
        <Button variant="outline" onClick={load} data-testid="refresh-stats-button"><RefreshCw size={16} className="mr-1.5" /> Atualizar</Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
        {METRICS.map((m) => (
          <div key={m.key} className="bg-card border border-border rounded-md p-4" data-testid={`metric-${m.key}`}>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{m.label}</div>
            <div className="font-heading font-black text-2xl mt-1.5">{stats[m.key] ?? 0}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {RATES.map((r) => (
          <div key={r.key} className="bg-primary/5 border border-primary/20 rounded-md p-4" data-testid={`rate-${r.key}`}>
            <div className="text-xs font-medium text-primary uppercase tracking-wide">{r.label}</div>
            <div className="font-heading font-black text-2xl mt-1.5 text-primary">{stats[r.key] ?? 0}%</div>
          </div>
        ))}
      </div>

      <div className="bg-card border border-border rounded-md overflow-hidden">
        <div className="px-4 py-3 border-b border-border"><h2 className="font-heading font-bold">Destinatários</h2></div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Enviado</TableHead>
              <TableHead>Aberto</TableHead>
              <TableHead>Clique</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {recipients.map((r) => (
              <TableRow key={r.job_id} data-testid={`recipient-row-${r.job_id}`}>
                <TableCell className="font-medium">{r.name || "—"}</TableCell>
                <TableCell className="font-mono text-xs">{r.email}</TableCell>
                <TableCell>{r.replied ? <StatusBadge status="respondido" /> : <StatusBadge status={r.status} />}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{r.sent_at ? new Date(r.sent_at).toLocaleString("pt-PT") : "—"}</TableCell>
                <TableCell>{r.opened_at ? "✓" : "—"}</TableCell>
                <TableCell>{r.clicked_at ? "✓" : "—"}</TableCell>
                <TableCell className="text-right">
                  {!r.replied && (
                    <Button variant="outline" size="sm" onClick={() => markReplied(r.contact_id)} data-testid={`mark-replied-${r.job_id}`}>
                      <Reply size={14} className="mr-1" /> Respondeu
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
