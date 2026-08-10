import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Copy, Eye, Variable, FileText } from "lucide-react";
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
const EMPTY = { name: "", subject: "", content_html: "", content_text: "" };

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [preview, setPreview] = useState(null);

  const subjectRef = useRef(null);
  const bodyRef = useRef(null);

  const load = () => api.get("/templates").then((r) => setTemplates(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const htmlToPlain = (html) => {
    if (!html) return "";
    let t = html.replace(/<br\s*\/?>/gi, "\n").replace(/<\/p>/gi, "\n\n").replace(/<\/div>/gi, "\n");
    const tmp = document.createElement("div");
    tmp.innerHTML = t;
    return (tmp.textContent || tmp.innerText || "").replace(/\n{3,}/g, "\n\n").trim();
  };

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (t) => {
    // Legacy templates may keep a richer body in content_html — prefer whichever text is longer.
    const fromHtml = htmlToPlain(t.content_html);
    const existing = t.content_text || "";
    const text = fromHtml.length > existing.trim().length ? fromHtml : existing;
    setEditing(t);
    setForm({ name: t.name, subject: t.subject, content_html: "", content_text: text });
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

  const save = async () => {
    if (!form.name.trim()) return toast.error("Nome obrigatório");
    try {
      // Templates são apenas Plain Text: content_html fica sempre vazio.
      const payload = { name: form.name, subject: form.subject, content_text: form.content_text, content_html: "" };
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
        subject: form.subject, content_html: "", content_text: form.content_text,
      });
      setPreview(data);
    } catch (e) { toast.error(apiError(e)); }
  };

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
                <FileText size={18} className="text-primary mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <h3 className="font-heading font-bold tracking-tight truncate">{t.name}</h3>
                  <p className="text-xs text-muted-foreground truncate">{t.subject || "Sem assunto"}</p>
                </div>
              </div>
              <div className="flex gap-1 mt-4 pt-3 border-t border-border">
                <Button variant="outline" size="sm" onClick={() => openEdit(t)} data-testid={`edit-template-${t.id}`}><Pencil size={14} className="mr-1" /> Editar</Button>
                <Button variant="outline" size="sm" onClick={() => duplicate(t)} data-testid={`duplicate-template-${t.id}`}><Copy size={14} /></Button>
                <Button variant="outline" size="sm" onClick={() => setToDelete(t)} data-testid={`delete-template-${t.id}`} className="text-destructive"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] grid-rows-[auto_1fr_auto] overflow-hidden" data-testid="template-dialog">
          <DialogHeader className="shrink-0">
            <DialogTitle>{editing ? "Editar template" : "Novo template"}</DialogTitle>
            <DialogDescription>Email de texto simples com variáveis de personalização.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 min-h-0 overflow-y-auto pr-1 -mr-1">
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
          </div>
          <DialogFooter className="gap-2 shrink-0 border-t border-border pt-4 mt-2">
            <Button variant="outline" onClick={doPreview} data-testid="preview-template-button"><Eye size={16} className="mr-1.5" /> Preview</Button>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-template-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl" data-testid="preview-dialog">
          <DialogHeader><DialogTitle>Pré-visualização do email (dados de exemplo)</DialogTitle>
            <DialogDescription>Aspeto do email de texto simples que será enviado.</DialogDescription>
          </DialogHeader>
          <div className="text-sm mb-2 truncate"><span className="text-muted-foreground">Assunto: </span><span className="font-semibold">{preview?.subject || "—"}</span></div>
          <div className="bg-white border border-border rounded-md p-6 max-h-[55vh] overflow-y-auto" data-testid="preview-body">
            <pre className="whitespace-pre-wrap break-words text-sm text-black m-0" style={{ fontFamily: "Arial, Helvetica, sans-serif", lineHeight: 1.6 }}>{preview?.content_text || ""}</pre>
          </div>
          <p className="text-xs text-muted-foreground mt-1">Enviado como texto simples (text/plain), sem HTML — inclui a assinatura da conta predefinida no fim.</p>
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
