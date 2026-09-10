import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Download, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import api from "@/lib/api";
import { PageHeader, EmptyState } from "@/components/common";

export default function Bounces() {
  const [bounces, setBounces] = useState([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    api.get("/bounces").then((r) => setBounces(r.data)).catch(() => {});
  }, []);

  const filtered = useMemo(() => bounces.filter((b) => {
    if (typeFilter !== "all" && (b.type || "") !== typeFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (b.email || "").toLowerCase().includes(s)
        || (b.contact_name || "").toLowerCase().includes(s)
        || (b.reason || "").toLowerCase().includes(s)
        || (b.campaign_name || "").toLowerCase().includes(s);
    }
    return true;
  }), [bounces, search, typeFilter]);

  const fmtDate = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString("pt-PT", { dateStyle: "short", timeStyle: "short" }); }
    catch { return iso; }
  };

  const exportCsv = () => {
    if (!filtered.length) return toast.error("Nada para exportar");
    const headers = ["Email", "Contacto", "Tipo", "Motivo", "Origem", "Campanha", "Data"];
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const rows = filtered.map((b) => [
      b.email, b.contact_name, b.type, b.reason, b.source, b.campaign_name, b.created_at,
    ].map(esc).join(","));
    const csv = [headers.map(esc).join(","), ...rows].join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bounces_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`${filtered.length} bounces exportados`);
  };

  const TypeBadge = ({ t }) => (
    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${t === "hard" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
      {t === "hard" ? "Hard" : "Soft"}
    </span>
  );

  return (
    <div data-testid="bounces-page">
      <PageHeader title="Bounces" subtitle={`${bounces.length} bounces registados`}>
        <Button variant="outline" onClick={exportCsv} data-testid="export-bounces-button"><Download size={16} className="mr-1.5" /> Exportar CSV</Button>
      </PageHeader>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Pesquisar por email, contacto, motivo, campanha…" value={search} data-testid="bounce-search-input"
            onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[160px]" data-testid="bounce-type-filter"><SelectValue placeholder="Tipo" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os tipos</SelectItem>
            <SelectItem value="hard">Hard bounce</SelectItem>
            <SelectItem value="soft">Soft bounce</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="Sem bounces" description="Os emails devolvidos aparecem aqui automaticamente, com motivo e tipo." />
      ) : (
        <div className="bg-card border border-border rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Contacto</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Motivo</TableHead>
                <TableHead>Origem</TableHead>
                <TableHead>Campanha</TableHead>
                <TableHead className="text-right">Data</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((b) => (
                <TableRow key={b.id} data-testid={`bounce-row-${b.id}`}>
                  <TableCell className="font-mono text-xs">{b.email}</TableCell>
                  <TableCell>{b.contact_name || "—"}</TableCell>
                  <TableCell><TypeBadge t={b.type} /></TableCell>
                  <TableCell className="max-w-[280px] truncate text-muted-foreground" title={b.reason}>{b.reason || "—"}</TableCell>
                  <TableCell className="uppercase text-[10px] text-muted-foreground">{b.source || "—"}</TableCell>
                  <TableCell>{b.campaign_name || "—"}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground whitespace-nowrap">{fmtDate(b.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
