import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, GripVertical, Zap, Euro, Settings2, Trophy, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/common";

const EVENTS = [
  { v: "deal_created", l: "Negócio criado" },
  { v: "stage_changed", l: "Mudou de etapa" },
  { v: "deal_won", l: "Negócio ganho" },
  { v: "deal_lost", l: "Negócio perdido" },
];
const ACTIONS = [
  { v: "send_email", l: "Enviar email" },
  { v: "create_task", l: "Criar tarefa" },
  { v: "change_stage", l: "Alterar etapa" },
  { v: "add_tag", l: "Adicionar etiqueta" },
  { v: "create_project", l: "Criar projeto" },
];

export default function Negocios() {
  const [pipelines, setPipelines] = useState([]);
  const [pid, setPid] = useState("");
  const [deals, setDeals] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [automations, setAutomations] = useState([]);
  const [dealOpen, setDealOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [drag, setDrag] = useState(null);
  const [autoOpen, setAutoOpen] = useState(false);
  const [autoForm, setAutoForm] = useState(null);
  const [dealToDelete, setDealToDelete] = useState(null);

  const pipeline = pipelines.find((p) => p.id === pid);

  const loadPipelines = useCallback(async () => {
    const { data } = await api.get("/pipelines");
    setPipelines(data);
    if (data.length && !pid) setPid(data[0].id);
  }, [pid]);

  const loadDeals = useCallback(() => { if (pid) api.get("/deals", { params: { pipeline_id: pid } }).then((r) => setDeals(r.data)); }, [pid]);
  const loadAutos = useCallback(() => { if (pid) api.get("/automations", { params: { pipeline_id: pid } }).then((r) => setAutomations(r.data)); }, [pid]);

  useEffect(() => { loadPipelines(); api.get("/templates").then((r) => setTemplates(r.data)); }, [loadPipelines]);
  useEffect(() => { loadDeals(); loadAutos(); }, [loadDeals, loadAutos]);

  const openNew = () => { setEditing(null); setForm({ name: "", company: "", email: "", phone: "", value: 0, probability: 0, owner: "", notes: "", pipeline_id: pid }); setDealOpen(true); };
  const openEdit = (d) => { setEditing(d); setForm({ ...d }); setDealOpen(true); };

  const saveDeal = async () => {
    if (!form.name?.trim()) return toast.error("Nome obrigatório");
    try {
      const body = { ...form, value: Number(form.value) || 0, probability: Number(form.probability) || 0 };
      if (editing) await api.put(`/deals/${editing.id}`, body);
      else await api.post("/deals", { ...body, pipeline_id: pid });
      toast.success(editing ? "Negócio atualizado" : "Negócio criado");
      setDealOpen(false); loadDeals();
    } catch (e) { toast.error(apiError(e)); }
  };

  const removeDeal = async (d) => { try { await api.delete(`/deals/${d.id}`); toast.success("Negócio eliminado"); setDealToDelete(null); loadDeals(); } catch (e) { toast.error(apiError(e)); } };

  const onDrop = async (stageId) => {
    if (!drag || drag.stage_id === stageId) { setDrag(null); return; }
    const stage = pipeline.stages.find((st) => st.id === stageId);
    let lost_reason = null;
    if (stage.type === "lost") lost_reason = prompt("Motivo da perda:", "") || "";
    try {
      await api.post(`/deals/${drag.id}/move`, { stage_id: stageId, lost_reason });
      toast.success(`Movido para ${stage.name}`);
      loadDeals();
    } catch (e) { toast.error(apiError(e)); }
    setDrag(null);
  };

  const openAuto = (a) => { setAutoForm(a || { pipeline_id: pid, name: "", event: "stage_changed", stage_id: pipeline?.stages[0]?.id, action: "send_email", config: {}, delay_days: 0, enabled: true }); setAutoOpen(true); };
  const saveAuto = async () => {
    try {
      const body = { ...autoForm, delay_days: Number(autoForm.delay_days) || 0 };
      if (autoForm.id) await api.put(`/automations/${autoForm.id}`, body);
      else await api.post("/automations", body);
      toast.success("Automação guardada"); setAutoOpen(false); loadAutos();
    } catch (e) { toast.error(apiError(e)); }
  };
  const removeAuto = async (a) => { try { await api.delete(`/automations/${a.id}`); toast.success("Automação eliminada"); loadAutos(); } catch (e) { toast.error(apiError(e)); } };

  const stageDeals = (sid) => deals.filter((d) => d.stage_id === sid);

  return (
    <div data-testid="negocios-page">
      <PageHeader title="Negócios" subtitle="CRM comercial visual (Kanban).">
        <Select value={pid} onValueChange={setPid}>
          <SelectTrigger className="w-56" data-testid="pipeline-select"><SelectValue placeholder="Pipeline" /></SelectTrigger>
          <SelectContent>{pipelines.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}</SelectContent>
        </Select>
        <Button onClick={openNew} data-testid="new-deal-button"><Plus size={16} className="mr-1.5" /> Novo negócio</Button>
      </PageHeader>

      <Tabs defaultValue="kanban">
        <TabsList>
          <TabsTrigger value="kanban" data-testid="tab-kanban">Pipeline</TabsTrigger>
          <TabsTrigger value="auto" data-testid="tab-automacoes"><Zap size={14} className="mr-1.5" /> Automações</TabsTrigger>
        </TabsList>

        <TabsContent value="kanban" className="mt-5">
          <div className="flex gap-4 overflow-x-auto pb-4">
            {pipeline?.stages.map((st) => (
              <div key={st.id} className="w-72 shrink-0" data-testid={`stage-${st.id}`}
                onDragOver={(e) => e.preventDefault()} onDrop={() => onDrop(st.id)}>
                <div className="flex items-center justify-between mb-2 px-1">
                  <span className="font-heading font-bold text-sm flex items-center gap-1.5">
                    {st.type === "won" && <Trophy size={14} className="text-emerald-600" />}
                    {st.type === "lost" && <XCircle size={14} className="text-red-600" />}
                    {st.name}
                  </span>
                  <span className="text-xs text-muted-foreground bg-secondary rounded px-1.5">{stageDeals(st.id).length}</span>
                </div>
                <div className="space-y-2 min-h-[120px] bg-secondary/40 rounded-md p-2">
                  {stageDeals(st.id).map((d) => (
                    <div key={d.id} draggable onDragStart={() => setDrag(d)}
                      data-testid={`deal-card-${d.id}`}
                      className="bg-card border border-border rounded-md p-3 cursor-grab active:cursor-grabbing hover:border-primary transition-colors">
                      <div className="flex items-start justify-between gap-1">
                        <span className="font-semibold text-sm truncate">{d.name}</span>
                        <GripVertical size={14} className="text-muted-foreground shrink-0" />
                      </div>
                      {d.company && <div className="text-xs text-muted-foreground truncate">{d.company}</div>}
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-xs font-mono text-primary flex items-center gap-0.5"><Euro size={11} />{Number(d.value || 0).toLocaleString("pt-PT")}</span>
                        <div className="flex gap-0.5">
                          <button onClick={() => openEdit(d)} data-testid={`edit-deal-${d.id}`} className="p-1 rounded hover:bg-secondary text-muted-foreground"><Pencil size={13} /></button>
                          <button onClick={() => setDealToDelete(d)} data-testid={`delete-deal-${d.id}`} className="p-1 rounded hover:bg-secondary text-destructive"><Trash2 size={13} /></button>
                        </div>
                      </div>
                      {d.tags?.length > 0 && <div className="flex flex-wrap gap-1 mt-2">{d.tags.map((t) => <span key={t} className="text-[10px] bg-primary/10 text-primary rounded px-1.5">{t}</span>)}</div>}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="auto" className="mt-5">
          <div className="flex justify-end mb-3"><Button onClick={() => openAuto(null)} data-testid="new-automation-button"><Plus size={16} className="mr-1.5" /> Nova automação</Button></div>
          <div className="space-y-2">
            {automations.length === 0 && <p className="text-sm text-muted-foreground">Sem automações neste pipeline.</p>}
            {automations.map((a) => (
              <div key={a.id} className="bg-card border border-border rounded-md p-4 flex items-center justify-between" data-testid={`automation-${a.id}`}>
                <div className="text-sm">
                  <div className="font-semibold">{a.name}</div>
                  <div className="text-xs text-muted-foreground">QUANDO {EVENTS.find((e) => e.v === a.event)?.l} → {ACTIONS.find((x) => x.v === a.action)?.l}{a.delay_days ? ` (após ${a.delay_days}d)` : ""}</div>
                </div>
                <div className="flex gap-1">
                  <Button variant="outline" size="sm" onClick={() => openAuto(a)} data-testid={`edit-automation-${a.id}`}><Pencil size={14} /></Button>
                  <Button variant="outline" size="sm" onClick={() => removeAuto(a)} className="text-destructive"><Trash2 size={14} /></Button>
                </div>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={dealOpen} onOpenChange={setDealOpen}>
        <DialogContent className="max-w-lg" data-testid="deal-dialog">
          <DialogHeader><DialogTitle>{editing ? "Editar negócio" : "Novo negócio"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3 max-h-[60vh] overflow-y-auto pr-1">
            <div className="col-span-2"><Label>Nome do negócio</Label><Input value={form.name || ""} data-testid="deal-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Empresa</Label><Input value={form.company || ""} onChange={(e) => setForm({ ...form, company: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Email</Label><Input value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Telefone</Label><Input value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Responsável</Label><Input value={form.owner || ""} onChange={(e) => setForm({ ...form, owner: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Valor (€)</Label><Input type="number" value={form.value ?? 0} data-testid="deal-value-input" onChange={(e) => setForm({ ...form, value: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Probabilidade (%)</Label><Input type="number" value={form.probability ?? 0} onChange={(e) => setForm({ ...form, probability: e.target.value })} className="mt-1.5" /></div>
            <div className="col-span-2"><Label>Data prevista de fecho</Label><Input type="date" value={(form.expected_close || "").slice(0,10)} onChange={(e) => setForm({ ...form, expected_close: e.target.value })} className="mt-1.5" /></div>
            <div className="col-span-2"><Label>Notas</Label><Textarea value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1.5" /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setDealOpen(false)}>Cancelar</Button><Button onClick={saveDeal} data-testid="save-deal-button">Guardar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={autoOpen} onOpenChange={setAutoOpen}>
        <DialogContent data-testid="automation-dialog">
          <DialogHeader><DialogTitle>{autoForm?.id ? "Editar automação" : "Nova automação"}</DialogTitle></DialogHeader>
          {autoForm && (
            <div className="space-y-3">
              <div><Label>Nome</Label><Input value={autoForm.name} data-testid="automation-name-input" onChange={(e) => setAutoForm({ ...autoForm, name: e.target.value })} className="mt-1.5" /></div>
              <div><Label>QUANDO (evento)</Label>
                <Select value={autoForm.event} onValueChange={(v) => setAutoForm({ ...autoForm, event: v })}>
                  <SelectTrigger className="mt-1.5" data-testid="automation-event-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{EVENTS.map((e) => <SelectItem key={e.v} value={e.v}>{e.l}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              {autoForm.event === "stage_changed" && (
                <div><Label>Etapa</Label>
                  <Select value={autoForm.stage_id} onValueChange={(v) => setAutoForm({ ...autoForm, stage_id: v })}>
                    <SelectTrigger className="mt-1.5" data-testid="automation-stage-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{pipeline?.stages.map((st) => <SelectItem key={st.id} value={st.id}>{st.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              )}
              <div><Label>EXECUTAR (ação)</Label>
                <Select value={autoForm.action} onValueChange={(v) => setAutoForm({ ...autoForm, action: v })}>
                  <SelectTrigger className="mt-1.5" data-testid="automation-action-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{ACTIONS.map((x) => <SelectItem key={x.v} value={x.v}>{x.l}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              {autoForm.action === "send_email" && (
                <>
                  <div><Label>Template</Label>
                    <Select value={autoForm.config?.template_id || ""} onValueChange={(v) => setAutoForm({ ...autoForm, config: { ...autoForm.config, template_id: v } })}>
                      <SelectTrigger className="mt-1.5" data-testid="automation-template-select"><SelectValue placeholder="Selecionar template" /></SelectTrigger>
                      <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div><Label>Atraso (dias) — 0 = imediato</Label><Input type="number" value={autoForm.delay_days} onChange={(e) => setAutoForm({ ...autoForm, delay_days: e.target.value })} className="mt-1.5" /></div>
                </>
              )}
              {autoForm.action === "add_tag" && <div><Label>Etiqueta</Label><Input value={autoForm.config?.tag || ""} onChange={(e) => setAutoForm({ ...autoForm, config: { ...autoForm.config, tag: e.target.value } })} className="mt-1.5" /></div>}
              {autoForm.action === "create_task" && <div><Label>Título da tarefa</Label><Input value={autoForm.config?.title || ""} onChange={(e) => setAutoForm({ ...autoForm, config: { ...autoForm.config, title: e.target.value } })} className="mt-1.5" /></div>}
              {autoForm.action === "change_stage" && <div><Label>Etapa destino</Label>
                <Select value={autoForm.config?.stage_id || ""} onValueChange={(v) => setAutoForm({ ...autoForm, config: { ...autoForm.config, stage_id: v } })}>
                  <SelectTrigger className="mt-1.5"><SelectValue placeholder="Selecionar etapa" /></SelectTrigger>
                  <SelectContent>{pipeline?.stages.map((st) => <SelectItem key={st.id} value={st.id}>{st.name}</SelectItem>)}</SelectContent>
                </Select></div>}
            </div>
          )}
          <DialogFooter><Button variant="outline" onClick={() => setAutoOpen(false)}>Cancelar</Button><Button onClick={saveAuto} data-testid="save-automation-button">Guardar</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!dealToDelete} onOpenChange={(o) => !o && setDealToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar negócio?</AlertDialogTitle>
            <AlertDialogDescription>Esta ação não pode ser revertida. O negócio "{dealToDelete?.name}" será removido.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => removeDeal(dealToDelete)} data-testid="confirm-delete-deal">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
