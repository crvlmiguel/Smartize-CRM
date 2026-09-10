import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Copy, Eye, Variable, FileText, Code, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";
import { PageHeader, EmptyState } from "@/components/common";

const VARIABLES = [
  "first_name", "last_name", "saudacao", "full_name", "company", "position",
  "email", "phone", "city", "country", "website", "today",
];
const EMPTY = { name: "", subject: "", content_html: "", content_text: "", type: "plain" };

const NEWSLETTER_SAMPLE = `<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
  <h1 style="color:#0055FF;">Olá {{first_name}}!</h1>
  <p>Esta é a nossa newsletter. Escreva aqui o seu conteúdo em HTML — imagens, cores, botões e layout são preservados exatamente.</p>
  <p style="text-align:center;margin:32px 0;">
    <a href="https://smartize.pt" style="background:#0055FF;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;">Saber mais</a>
  </p>
  <p>Com os melhores cumprimentos,<br/>Equipa Smartize</p>
</div>`;

const NEWSLETTER_MODELS = [
  {
    name: "Anúncio",
    html: `<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
  <div style="background:#0055FF;padding:28px 32px;border-radius:8px 8px 0 0;">
    <div style="color:#ffffff;font-size:22px;font-weight:bold;letter-spacing:1px;">SMARTIZE</div>
  </div>
  <div style="border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;padding:32px;">
    <h1 style="margin:0 0 12px;font-size:24px;color:#0f172a;">Olá {{first_name}}, temos novidades!</h1>
    <p style="font-size:15px;line-height:1.6;color:#334155;">Escreva aqui o anúncio principal. Explique de forma clara e breve o que está a apresentar e porque é relevante para {{company}}.</p>
    <p style="text-align:center;margin:32px 0;">
      <a href="https://smartize.pt" style="background:#0055FF;color:#ffffff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;">Saber mais</a>
    </p>
    <p style="font-size:15px;line-height:1.6;color:#334155;">Com os melhores cumprimentos,<br/>Equipa Smartize</p>
  </div>
  <p style="text-align:center;font-size:12px;color:#94a3b8;padding:16px;">Smartize · Lisboa, Portugal · <a href="https://smartize.pt" style="color:#94a3b8;">smartize.pt</a></p>
</div>`,
  },
  {
    name: "Promoção",
    html: `<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
  <div style="background:#0f172a;padding:40px 32px;border-radius:8px;text-align:center;">
    <div style="color:#38bdf8;font-size:13px;letter-spacing:3px;text-transform:uppercase;">Oferta exclusiva</div>
    <div style="color:#ffffff;font-size:34px;font-weight:bold;margin:10px 0;">-25% este mês</div>
    <p style="color:#cbd5e1;font-size:15px;margin:0 0 24px;">Caro {{saudacao}} {{first_name}}, aproveite antes que acabe.</p>
    <a href="https://smartize.pt" style="background:#38bdf8;color:#0f172a;padding:14px 30px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;">Aproveitar agora</a>
  </div>
  <p style="text-align:center;font-size:12px;color:#94a3b8;padding:16px;">Smartize · <a href="https://smartize.pt" style="color:#94a3b8;">smartize.pt</a></p>
</div>`,
  },
  {
    name: "Novidades",
    html: `<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
  <div style="padding:24px 0;text-align:center;border-bottom:3px solid #0055FF;">
    <span style="font-size:20px;font-weight:bold;color:#0055FF;">SMARTIZE</span>
    <span style="color:#64748b;font-size:13px;"> · Novidades</span>
  </div>
  <div style="padding:28px 8px;">
    <p style="font-size:15px;color:#334155;">Olá {{first_name}}, eis o que há de novo:</p>
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:18px;margin:14px 0;">
      <h3 style="margin:0 0 6px;color:#0f172a;font-size:17px;">Título da novidade 1</h3>
      <p style="margin:0;font-size:14px;line-height:1.6;color:#475569;">Descrição breve da primeira novidade.</p>
    </div>
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:18px;margin:14px 0;">
      <h3 style="margin:0 0 6px;color:#0f172a;font-size:17px;">Título da novidade 2</h3>
      <p style="margin:0;font-size:14px;line-height:1.6;color:#475569;">Descrição breve da segunda novidade.</p>
    </div>
    <p style="text-align:center;margin:26px 0;">
      <a href="https://smartize.pt" style="background:#0055FF;color:#ffffff;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;">Ver tudo</a>
    </p>
  </div>
  <p style="text-align:center;font-size:12px;color:#94a3b8;padding:16px;border-top:1px solid #e5e7eb;">Smartize · <a href="https://smartize.pt" style="color:#94a3b8;">smartize.pt</a></p>
</div>`,
  },
];

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [preview, setPreview] = useState(null);
  const [sending, setSending] = useState(false);

  const subjectRef = useRef(null);
  const bodyRef = useRef(null);
  const htmlRef = useRef(null);

  const load = () => api.get("/templates").then((r) => setTemplates(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const htmlToPlain = (html) => {
    if (!html) return "";
    let t = html.replace(/<br\s*\/?>/gi, "\n").replace(/<\/p>/gi, "\n\n").replace(/<\/div>/gi, "\n");
    const tmp = document.createElement("div");
    tmp.innerHTML = t;
    return (tmp.textContent || tmp.innerText || "").replace(/\n{3,}/g, "\n\n").trim();
  };

  const openNew = () => { setEditing(null); setForm(EMPTY); setPreview(null); setOpen(true); };
  const openEdit = (t) => {
    setEditing(t);
    setPreview(null);
    if ((t.type || "plain") === "html") {
      setForm({ name: t.name, subject: t.subject || "", content_html: t.content_html || "", content_text: "", type: "html" });
    } else {
      const fromHtml = htmlToPlain(t.content_html);
      const existing = t.content_text || "";
      const text = fromHtml.length > existing.trim().length ? fromHtml : existing;
      setForm({ name: t.name, subject: t.subject || "", content_html: "", content_text: text, type: "plain" });
    }
    setOpen(true);
  };

  const insertAtCursor = (ref, field, v) => {
    const el = ref.current;
    const token = `{{${v}}}`;
    const val = form[field] || "";
    if (!el) { setForm((f) => ({ ...f, [field]: val + token })); return; }
    const start = el.selectionStart ?? val.length;
    const end = el.selectionEnd ?? start;
    const next = val.slice(0, start) + token + val.slice(end);
    setForm((f) => ({ ...f, [field]: next }));
    setTimeout(() => { el.focus(); el.selectionStart = el.selectionEnd = start + token.length; }, 0);
  };
  const insertSubjectVariable = (v) => insertAtCursor(subjectRef, "subject", v);
  const insertBodyVariable = (v) => insertAtCursor(bodyRef, "content_text", v);
  const insertHtmlVariable = (v) => insertAtCursor(htmlRef, "content_html", v);

  const save = async () => {
    if (!form.name.trim()) return toast.error("Nome obrigatório");
    try {
      const payload = form.type === "html"
        ? { name: form.name, subject: form.subject, content_html: form.content_html, content_text: "", type: "html" }
        : { name: form.name, subject: form.subject, content_text: form.content_text, content_html: "", type: "plain" };
      if (editing) await api.put(`/templates/${editing.id}`, payload);
      else await api.post("/templates", payload);
      toast.success(editing ? "Template atualizado" : "Template criado");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const duplicate = async (t) => {
    try { await api.post(`/templates/${t.id}/duplicate`); toast.success("Template duplicado"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const confirmDelete = async () => {
    try { await api.delete(`/templates/${toDelete.id}`); toast.success("Template eliminado"); setToDelete(null); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const doPreview = async () => {
    try {
      const { data } = await api.post("/templates/preview", {
        subject: form.subject,
        content_html: form.type === "html" ? form.content_html : "",
        content_text: form.type === "html" ? "" : form.content_text,
        type: form.type,
      });
      setPreview({ ...data, type: form.type });
    } catch (e) { toast.error(apiError(e)); }
  };

  const sendTest = async () => {
    const email = window.prompt("Enviar email de teste para:");
    if (!email) return;
    setSending(true);
    try {
      const { data } = await api.post("/templates/test-send", {
        to_email: email.trim(), subject: form.subject,
        content_html: form.content_html, content_text: form.content_text, type: form.type,
      });
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (e) { toast.error(apiError(e)); }
    finally { setSending(false); }
  };

  const applyModel = (html) => {
    if (form.content_html && form.content_html.trim() && !window.confirm("Substituir o conteúdo HTML atual por este modelo?")) return;
    setForm((f) => ({ ...f, content_html: html }));
    toast.success("Modelo aplicado");
  };

  const typeLabel = (t) => (t?.type === "html" ? "Newsletter HTML" : "Texto simples");

  return (
    <div data-testid="templates-page">
      <PageHeader title="Templates" subtitle="Modelos de email reutilizáveis.">
        <Button onClick={openNew} data-testid="new-template-button"><Plus size={16} className="mr-1.5" /> Novo template</Button>
      </PageHeader>

      {templates.length === 0 ? (
        <EmptyState title="Sem templates" description="Crie o seu primeiro modelo de email."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Novo template</Button>} />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <div key={t.id} className="bg-card border border-border rounded-md p-5 flex flex-col" data-testid={`template-card-${t.id}`}>
              <div className="flex items-start gap-2">
                {t.type === "html" ? <Code size={18} className="text-primary mt-0.5 shrink-0" /> : <FileText size={18} className="text-primary mt-0.5 shrink-0" />}
                <div className="min-w-0">
                  <h3 className="font-heading font-bold tracking-tight truncate">{t.name}</h3>
                  <p className="text-xs text-muted-foreground truncate">{t.subject || "Sem assunto"}</p>
                </div>
              </div>
              <span className={`mt-3 self-start text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border ${t.type === "html" ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-zinc-100 text-zinc-600 border-zinc-200"}`} data-testid={`template-type-${t.id}`}>{typeLabel(t)}</span>
              <div className="flex gap-1 mt-4 pt-3 border-t border-border">
                <Button variant="outline" size="sm" onClick={() => openEdit(t)} data-testid={`edit-template-${t.id}`}><Pencil size={14} className="mr-1" /> Editar</Button>
                <Button variant="outline" size="sm" onClick={() => duplicate(t)} data-testid={`duplicate-template-${t.id}`}><Copy size={14} /></Button>
                <Button variant="outline" size="sm" onClick={() => setToDelete(t)} data-testid={`delete-template-${t.id}`} className="text-destructive"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setPreview(null); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] grid-rows-[auto_1fr_auto] overflow-hidden" data-testid="template-dialog">
          <DialogHeader className="shrink-0">
            <DialogTitle>{editing ? "Editar template" : "Novo template"}</DialogTitle>
            <DialogDescription>{form.type === "html" ? "Newsletter em HTML — enviada exatamente como criada." : "Email de texto simples com variáveis de personalização."}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 min-h-0 overflow-y-auto pr-1 -mr-1">
            {preview && (
              <div className="border border-border rounded-md bg-white" data-testid="preview-panel">
                <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-secondary/40">
                  <div className="text-xs truncate"><span className="text-muted-foreground">Preview · Assunto: </span><span className="font-semibold">{preview.subject || "—"}</span></div>
                  <button onClick={() => setPreview(null)} data-testid="close-preview-button" className="text-xs text-muted-foreground hover:text-foreground">Fechar preview ✕</button>
                </div>
                <iframe
                  title="email-preview"
                  data-testid="preview-iframe"
                  srcDoc={preview.email_html || `<pre style="white-space:pre-wrap;font-family:Arial;padding:16px">${preview.content_text || ""}</pre>`}
                  style={{ width: "100%", height: 360, border: "none", background: "#ffffff" }}
                />
              </div>
            )}
            {!editing && (
              <div>
                <Label>Tipo de template</Label>
                <div className="grid grid-cols-2 gap-3 mt-1.5">
                  <button type="button" onClick={() => setForm((f) => ({ ...f, type: "plain" }))} data-testid="template-type-plain"
                    className={`p-3 rounded-md border text-left ${form.type === "plain" ? "border-primary bg-primary/5" : "border-border"}`}>
                    <FileText size={16} className="text-primary mb-1" />
                    <div className="font-semibold text-sm">Texto simples</div>
                    <div className="text-xs text-muted-foreground">Email natural, como escrito por uma pessoa.</div>
                  </button>
                  <button type="button" onClick={() => setForm((f) => ({ ...f, type: "html", content_html: f.content_html || NEWSLETTER_SAMPLE }))} data-testid="template-type-html"
                    className={`p-3 rounded-md border text-left ${form.type === "html" ? "border-primary bg-primary/5" : "border-border"}`}>
                    <Code size={16} className="text-primary mb-1" />
                    <div className="font-semibold text-sm">Newsletter HTML</div>
                    <div className="text-xs text-muted-foreground">Layout completo em HTML, com imagens e estilos.</div>
                  </button>
                </div>
              </div>
            )}

            <div><Label>Nome</Label><Input value={form.name} data-testid="template-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>

            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Label>Assunto</Label>
                <Input ref={subjectRef} value={form.subject} data-testid="template-subject-input"
                  onChange={(e) => setForm({ ...form, subject: e.target.value })} className="mt-1.5" />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" data-testid="insert-subject-variable-button"><Variable size={16} className="mr-1.5" /> Variável</Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                  {VARIABLES.map((v) => (
                    <DropdownMenuItem key={v} onClick={() => insertSubjectVariable(v)} data-testid={`subject-variable-${v}`} className="font-mono text-xs">{`{{${v}}}`}</DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {form.type === "html" ? (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <Label>Código HTML da newsletter</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" data-testid="insert-html-variable-button"><Variable size={14} className="mr-1.5" /> Inserir variável</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                      {VARIABLES.map((v) => (
                        <DropdownMenuItem key={v} onClick={() => insertHtmlVariable(v)} data-testid={`html-variable-${v}`} className="font-mono text-xs">{`{{${v}}}`}</DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <Textarea ref={htmlRef} value={form.content_html} rows={16} data-testid="template-html-input"
                  onChange={(e) => setForm({ ...form, content_html: e.target.value })}
                  className="font-mono text-xs leading-relaxed"
                  placeholder="<div>...o seu HTML...</div>" />
                <div className="flex flex-wrap items-center gap-2 mt-2" data-testid="newsletter-models">
                  <span className="text-xs text-muted-foreground">Modelos prontos:</span>
                  {NEWSLETTER_MODELS.map((m) => (
                    <Button key={m.name} type="button" variant="outline" size="sm" onClick={() => applyModel(m.html)} data-testid={`newsletter-model-${m.name.toLowerCase()}`}>{m.name}</Button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">O HTML é enviado exatamente como criado — estrutura, imagens, estilos e espaçamentos são preservados. Use variáveis como {"{{first_name}}"}, {"{{saudacao}}"}.</p>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <Label>Mensagem (texto simples)</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" data-testid="insert-variable-button"><Variable size={14} className="mr-1.5" /> Inserir variável</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                      {VARIABLES.map((v) => (
                        <DropdownMenuItem key={v} onClick={() => insertBodyVariable(v)} data-testid={`variable-${v}`} className="font-mono text-xs">{`{{${v}}}`}</DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                <Textarea ref={bodyRef} value={form.content_text} rows={12} data-testid="template-text-input"
                  onChange={(e) => setForm({ ...form, content_text: e.target.value })}
                  className="font-mono text-sm leading-relaxed"
                  placeholder={"Caro {{saudacao}} {{first_name}},\n\nEspero que esteja bem.\n\n...\n\nCom os melhores cumprimentos,\nMiguel\nSmartize"} />
                <p className="text-xs text-muted-foreground mt-1.5">O email é enviado como texto simples (text/plain), sem HTML nem formatação — parece um email escrito por uma pessoa. A assinatura de texto da conta é adicionada no fim (se tiver texto). Use variáveis como {"{{first_name}}"}, {"{{company}}"}, {"{{saudacao}}"}.</p>
              </div>
            )}
          </div>
          <DialogFooter className="gap-2 shrink-0 border-t border-border pt-4 mt-2">
            <Button variant="outline" onClick={doPreview} data-testid="preview-template-button"><Eye size={16} className="mr-1.5" /> Preview</Button>
            {form.type === "html" && (
              <Button variant="outline" onClick={sendTest} disabled={sending} data-testid="template-test-send-button"><Send size={16} className="mr-1.5" /> {sending ? "A enviar…" : "Enviar teste"}</Button>
            )}
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-template-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Eliminar template?</AlertDialogTitle></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="confirm-delete-template">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
