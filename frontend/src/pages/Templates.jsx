import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Copy, Eye, Variable, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
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
  "first_name", "last_name", "full_name", "company", "position",
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
  const [activeField, setActiveField] = useState("content_html");

  const subjectRef = useRef(null);
  const htmlRef = useRef(null);
  const textRef = useRef(null);
  const refs = { subject: subjectRef, content_html: htmlRef, content_text: textRef };

  const load = () => api.get("/templates").then((r) => setTemplates(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (t) => { setEditing(t); setForm({ name: t.name, subject: t.subject, content_html: t.content_html, content_text: t.content_text }); setOpen(true); };

  const insertVariable = (v) => {
    const key = activeField;
    const el = refs[key]?.current;
    const token = `{${v}}`;
    if (!el) { setForm((f) => ({ ...f, [key]: (f[key] || "") + token })); return; }
    const start = el.selectionStart ?? (form[key] || "").length;
    const end = el.selectionEnd ?? start;
    const val = form[key] || "";
    const next = val.slice(0, start) + token + val.slice(end);
    setForm((f) => ({ ...f, [key]: next }));
    setTimeout(() => { el.focus(); el.selectionStart = el.selectionEnd = start + token.length; }, 0);
  };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Nome obrigatório");
    try {
      if (editing) await api.put(`/templates/${editing.id}`, form);
      else await api.post("/templates", form);
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
        subject: form.subject, content_html: form.content_html, content_text: form.content_text,
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
        <DialogContent className="max-w-3xl" data-testid="template-dialog">
          <DialogHeader><DialogTitle>{editing ? "Editar template" : "Novo template"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Nome</Label><Input value={form.name} data-testid="template-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Label>Assunto</Label>
                <Input ref={subjectRef} value={form.subject} data-testid="template-subject-input"
                  onFocus={() => setActiveField("subject")}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })} className="mt-1.5" />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" data-testid="insert-variable-button"><Variable size={16} className="mr-1.5" /> Inserir variável</Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
                  {VARIABLES.map((v) => (
                    <DropdownMenuItem key={v} onClick={() => insertVariable(v)} data-testid={`variable-${v}`} className="font-mono text-xs">{`{${v}}`}</DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            <Tabs defaultValue="html">
              <TabsList>
                <TabsTrigger value="html" data-testid="tab-html">Editor HTML</TabsTrigger>
                <TabsTrigger value="text" data-testid="tab-text">Editor Texto</TabsTrigger>
              </TabsList>
              <TabsContent value="html">
                <Textarea ref={htmlRef} value={form.content_html} rows={10} data-testid="template-html-input"
                  onFocus={() => setActiveField("content_html")}
                  onChange={(e) => setForm({ ...form, content_html: e.target.value })}
                  className="font-mono text-sm" placeholder="<p>Olá {first_name},</p>" />
              </TabsContent>
              <TabsContent value="text">
                <Textarea ref={textRef} value={form.content_text} rows={10} data-testid="template-text-input"
                  onFocus={() => setActiveField("content_text")}
                  onChange={(e) => setForm({ ...form, content_text: e.target.value })}
                  placeholder="Olá {first_name}," />
              </TabsContent>
            </Tabs>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={doPreview} data-testid="preview-template-button"><Eye size={16} className="mr-1.5" /> Preview</Button>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-template-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-2xl" data-testid="preview-dialog">
          <DialogHeader><DialogTitle>Preview (dados de exemplo)</DialogTitle></DialogHeader>
          <div className="border border-border rounded-md">
            <div className="px-4 py-2 border-b border-border bg-secondary text-sm"><span className="text-muted-foreground">Assunto: </span><span className="font-semibold">{preview?.subject}</span></div>
            <div className="p-4 max-h-[50vh] overflow-y-auto" dangerouslySetInnerHTML={{ __html: preview?.content_html || `<pre style="white-space:pre-wrap">${preview?.content_text || ""}</pre>` }} />
          </div>
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
