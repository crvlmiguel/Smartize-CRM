import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus, Play, Copy, Ban, Archive, Eye, Send, ChevronRight, ChevronLeft, Trash2, Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import api, { apiError } from "@/lib/api";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common";

const DEFAULT_SETTINGS = {
  min_interval_seconds: 30, max_interval_seconds: 90,
  emails_per_hour: 30, emails_per_day: 200,
  business_days_only: true, business_hour_start: 9, business_hour_end: 18,
  timezone: "Europe/Lisbon",
};

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [smtp, setSmtp] = useState([]);
  const [groups, setGroups] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(base());
  const [defaultSmtpId, setDefaultSmtpId] = useState("");
  const navigate = useNavigate();

  function base() {
    return {
      name: "", smtp_account_id: "", group_id: "", template_id: "",
      scheduleMode: "now", schedule_at: "", settings: { ...DEFAULT_SETTINGS },
      is_sequence: false, steps: [],
    };
  }

  const load = () => api.get("/campaigns").then((r) => setCampaigns(r.data)).catch(() => {});
  useEffect(() => {
    load();
    api.get("/smtp").then((r) => {
      setSmtp(r.data);
      const def = r.data.find((a) => a.is_default) || r.data[0];
      if (def) setDefaultSmtpId(def.id);
    }).catch(() => {});
    api.get("/groups").then((r) => setGroups(r.data)).catch(() => {});
    api.get("/templates").then((r) => setTemplates(r.data)).catch(() => {});
  }, []);

  const openNew = () => { setForm({ ...base(), smtp_account_id: defaultSmtpId }); setStep(1); setOpen(true); };

  const buildPayload = () => ({
    name: form.name,
    smtp_account_id: form.smtp_account_id,
    group_id: form.group_id,
    template_id: form.is_sequence ? null : form.template_id,
    is_sequence: form.is_sequence,
    steps: form.is_sequence
      ? form.steps.map((s) => ({
          template_id: s.template_id,
          subject: s.subject?.trim() ? s.subject : null,
          send_type: s.send_type || "new",
          delay_days: Number(s.delay_days) || 0,
          delay_hours: Number(s.delay_hours) || 0,
        }))
      : [],
    schedule_at: form.scheduleMode === "schedule" && form.schedule_at
      ? new Date(form.schedule_at).toISOString() : null,
    settings: {
      ...form.settings,
      min_interval_seconds: Number(form.settings.min_interval_seconds),
      max_interval_seconds: Number(form.settings.max_interval_seconds),
      emails_per_hour: Number(form.settings.emails_per_hour),
      emails_per_day: Number(form.settings.emails_per_day),
      business_hour_start: Number(form.settings.business_hour_start),
      business_hour_end: Number(form.settings.business_hour_end),
    },
  });

  const validate = () => {
    if (!form.name.trim()) return "Indique um nome";
    if (!form.smtp_account_id) return "Selecione uma conta SMTP";
    if (!form.group_id) return "Selecione um grupo";
    if (form.is_sequence) {
      if (!form.steps.length) return "Adicione pelo menos um passo à sequência";
      if (form.steps.some((s) => !s.template_id)) return "Cada passo precisa de um template";
    } else if (!form.template_id) {
      return "Selecione um template";
    }
    if (form.scheduleMode === "schedule" && !form.schedule_at) return "Indique data de agendamento";
    return null;
  };

  const addStep = () =>
    setForm((f) => ({
      ...f,
      steps: [
        ...f.steps,
        {
          template_id: "",
          subject: "",
          send_type: f.steps.length === 0 ? "new" : "reply",
          delay_days: f.steps.length === 0 ? 0 : 2,
          delay_hours: 0,
        },
      ],
    }));
  const updateStep = (i, k, v) =>
    setForm((f) => ({ ...f, steps: f.steps.map((s, idx) => (idx === i ? { ...s, [k]: v } : s)) }));
  const removeStep = (i) =>
    setForm((f) => ({ ...f, steps: f.steps.filter((_, idx) => idx !== i) }));
  const toggleSequence = (on) =>
    setForm((f) => ({
      ...f,
      is_sequence: on,
      steps: on && f.steps.length === 0
        ? [{ template_id: f.template_id || "", subject: "", send_type: "new", delay_days: 0, delay_hours: 0 }]
        : f.steps,
    }));

  const create = async (startNow) => {
    const err = validate();
    if (err) return toast.error(err);
    try {
      const { data } = await api.post("/campaigns", buildPayload());
      if (startNow) {
        const res = await api.post(`/campaigns/${data.id}/start`);
        toast.success(`Campanha iniciada · ${res.data.recipients} destinatários`);
      } else {
        toast.success("Campanha guardada como rascunho");
      }
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const action = async (id, verb, label) => {
    try {
      const res = await api.post(`/campaigns/${id}/${verb}`);
      toast.success(label + (res.data?.recipients != null ? ` · ${res.data.recipients} destinatários` : ""));
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const remove = async (id) => {
    try { await api.delete(`/campaigns/${id}`); toast.success("Campanha eliminada"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const setS = (k, v) => setForm({ ...form, settings: { ...form.settings, [k]: v } });

  return (
    <div data-testid="campaigns-page">
      <PageHeader title="Campanhas" subtitle="Crie e acompanhe campanhas de email outbound.">
        <Button onClick={openNew} data-testid="new-campaign-button"><Plus size={16} className="mr-1.5" /> Nova campanha</Button>
      </PageHeader>

      {campaigns.length === 0 ? (
        <EmptyState title="Sem campanhas" description="Crie a sua primeira campanha em poucos passos."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Nova campanha</Button>} />
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <div key={c.id} className="bg-card border border-border rounded-md p-4 flex items-center justify-between gap-4" data-testid={`campaign-row-${c.id}`}>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <button onClick={() => navigate(`/campanhas/${c.id}`)} className="font-heading font-bold tracking-tight truncate hover:text-primary" data-testid={`open-campaign-${c.id}`}>{c.name}</button>
                  <StatusBadge status={c.status} />
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-muted-foreground">
                  <span>{c.stats?.sent || 0}/{c.stats?.total || 0} enviados</span>
                  <span>{c.stats?.opened || 0} abertos ({c.stats?.open_rate || 0}%)</span>
                  <span>{c.stats?.clicked || 0} cliques</span>
                  <span>{c.stats?.bounced || 0} bounces</span>
                  {c.stats?.pending > 0 && <span className="text-amber-600">{c.stats.pending} na fila</span>}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button variant="outline" size="sm" onClick={() => navigate(`/campanhas/${c.id}`)} data-testid={`view-campaign-${c.id}`}><Eye size={14} /></Button>
                {["rascunho", "cancelada"].includes(c.status) && (
                  <Button size="sm" onClick={() => action(c.id, "start", "Campanha iniciada")} data-testid={`start-campaign-${c.id}`}><Play size={14} className="mr-1" /> Iniciar</Button>
                )}
                {c.status === "sending" && (
                  <Button variant="outline" size="sm" onClick={() => action(c.id, "cancel", "Campanha cancelada")} data-testid={`cancel-campaign-${c.id}`}><Ban size={14} /></Button>
                )}
                <Button variant="outline" size="sm" onClick={() => action(c.id, "duplicate", "Campanha duplicada")} data-testid={`duplicate-campaign-${c.id}`}><Copy size={14} /></Button>
                <Button variant="outline" size="sm" onClick={() => action(c.id, "archive", "Campanha arquivada")} data-testid={`archive-campaign-${c.id}`}><Archive size={14} /></Button>
                <Button variant="outline" size="sm" onClick={() => remove(c.id)} data-testid={`delete-campaign-${c.id}`} className="text-destructive"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl" data-testid="campaign-dialog">
          <DialogHeader>
            <DialogTitle>Nova campanha</DialogTitle>
            <DialogDescription>Configure o envio em poucos passos.</DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-2 mb-2">
            {[1, 2, 3].map((s) => (
              <div key={s} className={`h-1.5 flex-1 rounded-full ${step >= s ? "bg-primary" : "bg-border"}`} />
            ))}
          </div>

          {step === 1 && (
            <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1" data-testid="wizard-step-1">
              <div><Label>Nome da campanha</Label><Input value={form.name} data-testid="campaign-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>
              <div>
                <Label>Conta SMTP</Label>
                <Select value={form.smtp_account_id} onValueChange={(v) => setForm({ ...form, smtp_account_id: v })}>
                  <SelectTrigger className="mt-1.5" data-testid="campaign-smtp-select"><SelectValue placeholder="Selecionar conta SMTP" /></SelectTrigger>
                  <SelectContent>{smtp.map((s) => <SelectItem key={s.id} value={s.id}>{s.name} — {s.from_email}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Grupo de contactos</Label>
                <Select value={form.group_id} onValueChange={(v) => setForm({ ...form, group_id: v })}>
                  <SelectTrigger className="mt-1.5" data-testid="campaign-group-select"><SelectValue placeholder="Selecionar grupo" /></SelectTrigger>
                  <SelectContent>{groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name} ({g.contact_count})</SelectItem>)}</SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between rounded-md border border-border p-3">
                <div className="flex items-center gap-2">
                  <Layers size={16} className="text-primary" />
                  <div>
                    <Label className="cursor-pointer">Ativar sequência de emails</Label>
                    <p className="text-xs text-muted-foreground">Envie follow-ups automáticos que param quando o contacto responde.</p>
                  </div>
                </div>
                <Switch checked={form.is_sequence} data-testid="sequence-switch" onCheckedChange={toggleSequence} />
              </div>

              {!form.is_sequence ? (
                <div>
                  <Label>Template</Label>
                  <Select value={form.template_id} onValueChange={(v) => setForm({ ...form, template_id: v })}>
                    <SelectTrigger className="mt-1.5" data-testid="campaign-template-select"><SelectValue placeholder="Selecionar template" /></SelectTrigger>
                    <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              ) : (
                <div className="space-y-3" data-testid="sequence-builder">
                  {form.steps.map((st, i) => (
                    <div key={i} className="rounded-md border border-border p-3 space-y-3 bg-secondary/30" data-testid={`sequence-step-${i}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-heading font-bold flex items-center gap-1.5">
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-[11px]">{i + 1}</span>
                          {i === 0 ? "Email inicial" : `Follow-up ${i}`}
                        </span>
                        {form.steps.length > 1 && (
                          <button onClick={() => removeStep(i)} data-testid={`remove-step-${i}`} className="p-1 rounded hover:bg-secondary text-destructive"><Trash2 size={14} /></button>
                        )}
                      </div>
                      {i > 0 && (
                        <div className="grid grid-cols-2 gap-3">
                          <div><Label className="text-xs">Atraso (dias)</Label><Input type="number" min="0" value={st.delay_days} data-testid={`step-delay-days-${i}`} onChange={(e) => updateStep(i, "delay_days", e.target.value)} className="mt-1" /></div>
                          <div><Label className="text-xs">Atraso (horas)</Label><Input type="number" min="0" value={st.delay_hours} onChange={(e) => updateStep(i, "delay_hours", e.target.value)} className="mt-1" /></div>
                        </div>
                      )}
                      <div>
                        <Label className="text-xs">Template</Label>
                        <Select value={st.template_id} onValueChange={(v) => updateStep(i, "template_id", v)}>
                          <SelectTrigger className="mt-1" data-testid={`step-template-select-${i}`}><SelectValue placeholder="Selecionar template" /></SelectTrigger>
                          <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      {i > 0 && (
                        <div>
                          <Label className="text-xs">Tipo de envio</Label>
                          <Select value={st.send_type} onValueChange={(v) => updateStep(i, "send_type", v)}>
                            <SelectTrigger className="mt-1" data-testid={`step-sendtype-select-${i}`}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="reply">Responder ao email anterior (mesma thread)</SelectItem>
                              <SelectItem value="new">Novo email</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      )}
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={addStep} data-testid="add-step-button" className="w-full"><Plus size={14} className="mr-1" /> Adicionar passo</Button>
                </div>
              )}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4" data-testid="wizard-step-2">
              <p className="text-sm text-muted-foreground">Envio inteligente para maximizar a entregabilidade.</p>
              <div className="grid grid-cols-2 gap-4">
                <div><Label>Intervalo mín. (seg)</Label><Input type="number" value={form.settings.min_interval_seconds} data-testid="min-interval-input" onChange={(e) => setS("min_interval_seconds", e.target.value)} className="mt-1.5" /></div>
                <div><Label>Intervalo máx. (seg)</Label><Input type="number" value={form.settings.max_interval_seconds} data-testid="max-interval-input" onChange={(e) => setS("max_interval_seconds", e.target.value)} className="mt-1.5" /></div>
                <div><Label>Emails / hora</Label><Input type="number" value={form.settings.emails_per_hour} onChange={(e) => setS("emails_per_hour", e.target.value)} className="mt-1.5" /></div>
                <div><Label>Emails / dia</Label><Input type="number" value={form.settings.emails_per_day} onChange={(e) => setS("emails_per_day", e.target.value)} className="mt-1.5" /></div>
                <div><Label>Hora início</Label><Input type="number" value={form.settings.business_hour_start} onChange={(e) => setS("business_hour_start", e.target.value)} className="mt-1.5" /></div>
                <div><Label>Hora fim</Label><Input type="number" value={form.settings.business_hour_end} onChange={(e) => setS("business_hour_end", e.target.value)} className="mt-1.5" /></div>
              </div>
              <div className="flex items-center gap-3 pt-1">
                <Switch checked={form.settings.business_days_only} data-testid="business-days-switch" onCheckedChange={(v) => setS("business_days_only", v)} />
                <Label>Enviar apenas em dias úteis</Label>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4" data-testid="wizard-step-3">
              <div className="grid grid-cols-2 gap-3">
                <button onClick={() => setForm({ ...form, scheduleMode: "now" })} data-testid="mode-now"
                  className={`p-4 rounded-md border text-left ${form.scheduleMode === "now" ? "border-primary bg-primary/5" : "border-border"}`}>
                  <Send size={18} className="text-primary mb-1" />
                  <div className="font-semibold text-sm">Enviar agora</div>
                  <div className="text-xs text-muted-foreground">Inicia o envio imediatamente.</div>
                </button>
                <button onClick={() => setForm({ ...form, scheduleMode: "schedule" })} data-testid="mode-schedule"
                  className={`p-4 rounded-md border text-left ${form.scheduleMode === "schedule" ? "border-primary bg-primary/5" : "border-border"}`}>
                  <Play size={18} className="text-primary mb-1" />
                  <div className="font-semibold text-sm">Agendar</div>
                  <div className="text-xs text-muted-foreground">Escolha data e hora de início.</div>
                </button>
              </div>
              {form.scheduleMode === "schedule" && (
                <div><Label>Data e hora de início</Label><Input type="datetime-local" value={form.schedule_at} data-testid="schedule-datetime-input" onChange={(e) => setForm({ ...form, schedule_at: e.target.value })} className="mt-1.5" /></div>
              )}
            </div>
          )}

          <DialogFooter className="justify-between sm:justify-between">
            <div>
              {step > 1 && <Button variant="outline" onClick={() => setStep(step - 1)} data-testid="wizard-back"><ChevronLeft size={16} className="mr-1" /> Voltar</Button>}
            </div>
            <div className="flex gap-2">
              {step < 3 && <Button onClick={() => setStep(step + 1)} data-testid="wizard-next">Seguinte <ChevronRight size={16} className="ml-1" /></Button>}
              {step === 3 && (
                <>
                  <Button variant="outline" onClick={() => create(false)} data-testid="save-draft-button">Guardar rascunho</Button>
                  <Button onClick={() => create(true)} data-testid="create-start-button">
                    {form.scheduleMode === "now" ? "Criar e iniciar" : "Criar e agendar"}
                  </Button>
                </>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
