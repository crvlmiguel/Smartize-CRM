import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common";

export default function Statistics() {
  const [campaigns, setCampaigns] = useState([]);
  const navigate = useNavigate();

  useEffect(() => { api.get("/campaigns").then((r) => setCampaigns(r.data)).catch(() => {}); }, []);

  return (
    <div data-testid="statistics-page">
      <PageHeader title="Estatísticas" subtitle="Desempenho de todas as campanhas." />
      {campaigns.length === 0 ? (
        <EmptyState title="Sem dados" description="Ainda não existem campanhas para analisar." />
      ) : (
        <div className="bg-card border border-border rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campanha</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Enviados</TableHead>
                <TableHead className="text-right">Abertos</TableHead>
                <TableHead className="text-right">Cliques</TableHead>
                <TableHead className="text-right">Bounces</TableHead>
                <TableHead className="text-right">T. Entrega</TableHead>
                <TableHead className="text-right">T. Abertura</TableHead>
                <TableHead className="text-right">T. Resposta</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((c) => (
                <TableRow key={c.id} className="cursor-pointer" onClick={() => navigate(`/campanhas/${c.id}`)} data-testid={`stats-row-${c.id}`}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell><StatusBadge status={c.status} /></TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.sent || 0}</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.opened || 0}</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.clicked || 0}</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.bounced || 0}</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.delivery_rate || 0}%</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.open_rate || 0}%</TableCell>
                  <TableCell className="text-right font-mono">{c.stats?.reply_rate || 0}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
