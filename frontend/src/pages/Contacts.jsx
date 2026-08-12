import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Upload, Search, X, Briefcase, HelpCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import api, { apiError } from "@/lib/api";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common";

const STATUSES = ["ativo", "respondido", "bounce", "descadastrado"];
const EMPTY = {
  first_name: "", last_name: "", saudacao: "", company: "", position: "", email: "",
  phone: "", city: "", country: "", website: "", group_id: "none", status: "ativo", notes: "",
};

export default function Contacts() {
  const navigate = useNavigate();
  const [contacts, setContacts] = useState([]);
  const [groups, setGroups] = useState([]);
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [bulkOpen, setBulkOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importGroup, setImportGroup] = useState("none");
  const [importing, setImporting] = useState(false);
  const [importStep, setImportStep] = useState(1);
  const [analyzing, setAnalyzing] = useState(false);
  const [importPreview, setImportPreview] = useState(null);
  const [importMapping, setImportMapping] = useState({});

  const IMPORT_FIELDS = [
    { k: "first_name", l: "Primeiro nome" },
    { k: "last_name", l: "Apelido" },
    { k: "saudacao", l: "Saudação" },
    { k: "email", l: "Email (obrigatório)" },
    { k: "company", l: "Empresa" },
    { k: "position", l: "Cargo" },
    { k: "phone", l: "Telefone" },
    { k: "city", l: "Cidade" },
    { k: "country", l: "País" },
    { k: "website", l: "Website" },
  ];

  const load = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (groupFilter !== "all") params.group_id = groupFilter;
    if (statusFilter !== "all") params.status = statusFilter;
    api.get("/contacts", { params }).then((r) => { setContacts(r.data); setSelected(new Set()); }).catch(() => {});
  }, [search, groupFilter, statusFilter]);

  useEffect(() => { api.get("/groups").then((r) => setGroups(r.data)).catch(() => {}); }, []);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const groupName = (id) => groups.find((g) => g.id === id)?.name || "—";

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ ...EMPTY, ...c, group_id: c.group_id || "none" });
    setOpen(true);
  };

  const save = async () => {
    if (!form.email.trim()) return toast.error("Email obrigatório");
    const payload = { ...form, group_id: form.group_id === "none" ? null : form.group_id };
    try {
      if (editing) await api.put(`/contacts/${editing.id}`, payload);
      else await api.post("/contacts", payload);
      toast.success(editing ? "Contacto atualizado" : "Contacto criado");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const confirmDelete = async () => {
    try { await api.delete(`/contacts/${toDelete.id}`); toast.success("Contacto eliminado"); setToDelete(null); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const allSelected = contacts.length > 0 && contacts.every((c) => selected.has(c.id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(contacts.map((c) => c.id)));
  const toggleOne = (id) => setSelected((s) => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });
  const confirmBulkDelete = async () => {
    try {
      const { data } = await api.post("/contacts/bulk-delete", { ids: [...selected] });
      toast.success(`${data.deleted} contacto(s) eliminado(s)`);
      setBulkOpen(false); setSelected(new Set()); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const createDealFromContact = (c) => {
    navigate("/negocios", { state: { contact: c } });
  };

  const openImport = () => {
    setImportFile(null); setImportGroup("none"); setImportStep(1);
    setImportPreview(null); setImportMapping({}); setImportOpen(true);
  };

  const analyzeImport = async () => {
    if (!importFile) return toast.error("Selecione um ficheiro");
    setAnalyzing(true);
    const fd = new FormData();
    fd.append("file", importFile);
    try {
      const { data } = await api.post("/contacts/import/preview", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setImportPreview(data);
      setImportMapping(data.mapping || {});
      setImportStep(2);
    } catch (e) { toast.error(apiError(e)); }
    finally { setAnalyzing(false); }
  };

  const doImport = async () => {
    if (!importMapping.email) return toast.error("Mapeie a coluna do Email");
    setImporting(true);
    const fd = new FormData();
    fd.append("file", importFile);
    fd.append("group_id", importGroup === "none" ? "" : importGroup);
    fd.append("mapping", JSON.stringify(importMapping));
    try {
      const { data } = await api.post("/contacts/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${data.imported} importados, ${data.duplicates} duplicados, ${data.skipped} inválidos`);
      setImportOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setImporting(false); }
  };

  const field = (key, label, type = "text") => (
    <div>
      <Label>{label}</Label>
      <Input type={type} value={form[key] || ""} data-testid={`contact-${key}-input`}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="mt-1.5" />
    </div>
  );

  return (
    <div data-testid="contacts-page">
      <PageHeader title="Contactos" subtitle={`${contacts.length} contactos`}>
        <Button variant="outline" onClick={openImport} data-testid="import-contacts-button"><Upload size={16} className="mr-1.5" /> Importar</Button>
        <Button onClick={openNew} data-testid="new-contact-button"><Plus size={16} className="mr-1.5" /> Novo contacto</Button>
      </PageHeader>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Pesquisar por nome, email, empresa…" value={search} data-testid="contact-search-input"
            onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={groupFilter} onValueChange={setGroupFilter}>
          <SelectTrigger className="w-[180px]" data-testid="filter-group-select"><SelectValue placeholder="Grupo" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os grupos</SelectItem>
            <SelectItem value="none">Sem grupo</SelectItem>
            {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px]" data-testid="filter-status-select"><SelectValue placeholder="Estado" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os estados</SelectItem>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center justify-between bg-secondary/50 border border-border rounded-md px-4 py-2 mb-3" data-testid="bulk-actions-bar">
          <span className="text-sm font-medium">{selected.size} contacto(s) selecionado(s)</span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())} data-testid="clear-selection-button">Limpar seleção</Button>
            <Button variant="destructive" size="sm" onClick={() => setBulkOpen(true)} data-testid="bulk-delete-button"><Trash2 size={15} className="mr-1.5" /> Eliminar selecionados</Button>
          </div>
        </div>
      )}

      {contacts.length === 0 ? (
        <EmptyState title="Sem contactos" description="Crie manualmente ou importe um ficheiro CSV/Excel."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Novo contacto</Button>} />
      ) : (
        <div className="bg-card border border-border rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[44px]">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} data-testid="select-all-contacts" aria-label="Selecionar todos" />
                </TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Saudação</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Empresa</TableHead>
                <TableHead>Grupo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {contacts.map((c) => (
                <TableRow key={c.id} data-testid={`contact-row-${c.id}`} data-state={selected.has(c.id) ? "selected" : undefined}>
                  <TableCell>
                    <Checkbox checked={selected.has(c.id)} onCheckedChange={() => toggleOne(c.id)} data-testid={`select-contact-${c.id}`} aria-label="Selecionar contacto" />
                  </TableCell>
                  <TableCell className="font-medium">{`${c.first_name || ""} ${c.last_name || ""}`.trim() || "—"}</TableCell>
                  <TableCell className="text-muted-foreground" data-testid={`contact-saudacao-${c.id}`}>{c.saudacao || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{c.email}</TableCell>
                  <TableCell>{c.company || "—"}</TableCell>
                  <TableCell>{groupName(c.group_id)}</TableCell>
                  <TableCell><StatusBadge status={c.status} /></TableCell>
                  <TableCell className="text-right">
                    <button onClick={() => createDealFromContact(c)} data-testid={`convert-contact-${c.id}`} title="Criar negócio" className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground hover:text-primary"><Briefcase size={15} /></button>
                    <button onClick={() => openEdit(c)} data-testid={`edit-contact-${c.id}`} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground"><Pencil size={15} /></button>
                    <button onClick={() => setToDelete(c)} data-testid={`delete-contact-${c.id}`} className="p-1.5 rounded-md hover:bg-secondary text-destructive"><Trash2 size={15} /></button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="contact-dialog">
          <DialogHeader><DialogTitle>{editing ? "Editar contacto" : "Novo contacto"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 max-h-[60vh] overflow-y-auto pr-1">
            {field("first_name", "Primeiro nome")}
            {field("last_name", "Apelido")}
            {field("saudacao", "Saudação (ex.: Caro, Cara, Exmo.)")}
            {field("email", "Email", "email")}
            {field("phone", "Telefone")}
            {field("company", "Empresa")}
            {field("position", "Cargo")}
            {field("city", "Cidade")}
            {field("country", "País")}
            {field("website", "Website")}
            <div>
              <Label>Grupo</Label>
              <Select value={form.group_id} onValueChange={(v) => setForm({ ...form, group_id: v })}>
                <SelectTrigger className="mt-1.5" data-testid="contact-group-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sem grupo</SelectItem>
                  {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Estado</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1.5" data-testid="contact-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="col-span-2">
              <Label>Notas</Label>
              <Textarea value={form.notes} data-testid="contact-notes-input" onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1.5" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-contact-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-2xl" data-testid="import-dialog">
          <DialogHeader>
            <DialogTitle>Importar contactos</DialogTitle>
            <DialogDescription>{importStep === 1 ? "Prepare o ficheiro e analise antes de importar." : "Confirme o mapeamento das colunas e reveja o resumo."}</DialogDescription>
          </DialogHeader>

          {importStep === 1 ? (
            <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
              <div className="bg-secondary/40 border border-border rounded-md p-4 text-sm space-y-2" data-testid="import-help">
                <div className="font-semibold flex items-center gap-1.5"><HelpCircle size={15} className="text-primary" /> Como preparar o ficheiro</div>
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-1">
                  <li>Formatos aceites: <b>.csv</b> (recomendado, UTF-8) ou <b>.xlsx</b>.</li>
                  <li>A primeira linha deve conter os <b>nomes das colunas</b>.</li>
                  <li>Coluna <b>obrigatória</b>: <code>email</code>. As restantes são opcionais.</li>
                  <li>Colunas suportadas: <code>first_name</code>, <code>last_name</code>, <code>saudacao</code>, <code>email</code>, <code>company</code>, <code>job_title</code>, <code>phone</code>, <code>city</code>, <code>country</code>, <code>website</code>.</li>
                  <li>O campo <b>saudacao</b> é usado tal como está no ficheiro (ex.: "Caro", "Cara", "Exmo.") e fica disponível como variável <code>{"{{saudacao}}"}</code> nos templates.</li>
                  <li>Campos vazios ficam em branco. <b>Emails inválidos</b> são ignorados. <b>Duplicados</b> (já existentes ou repetidos no ficheiro) são descartados automaticamente.</li>
                  <li>Colunas não reconhecidas não são eliminadas em silêncio — serão indicadas no passo seguinte.</li>
                </ul>
                <div className="text-xs font-medium mt-2">Exemplo de CSV:</div>
                <pre className="text-[11px] bg-card border border-border rounded p-2 overflow-x-auto" data-testid="import-example">first_name,last_name,saudacao,email,company,job_title,phone
João,Silva,Caro,joao@empresa.pt,Empresa XYZ,CEO,+351900000000
Maria,Costa,Cara,maria@empresa.pt,Empresa ABC,Marketing Director,+351911111111</pre>
              </div>
              <div>
                <Label>Ficheiro (.csv, .xlsx)</Label>
                <Input type="file" accept=".csv,.xlsx,.xls" data-testid="import-file-input"
                  onChange={(e) => setImportFile(e.target.files[0])} className="mt-1.5" />
              </div>
              <div>
                <Label>Adicionar ao grupo</Label>
                <Select value={importGroup} onValueChange={setImportGroup}>
                  <SelectTrigger className="mt-1.5" data-testid="import-group-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Sem grupo</SelectItem>
                    {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : (
            <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
              <div className="text-xs text-muted-foreground" data-testid="import-file-info">
                Ficheiro: <b className="text-foreground">{importFile?.name}</b>
                {importGroup !== "none" && <> · Grupo: <b className="text-foreground">{groups.find((g) => g.id === importGroup)?.name}</b></>}
              </div>
              <div className="grid grid-cols-5 gap-2 text-center" data-testid="import-summary">
                {[
                  { l: "Encontrados", v: importPreview?.counts.total, c: "text-foreground" },
                  { l: "Válidos", v: importPreview?.counts.valid, c: "text-emerald-600" },
                  { l: "Inválidos", v: importPreview?.counts.invalid, c: "text-red-600" },
                  { l: "Duplicados", v: importPreview?.counts.duplicates, c: "text-amber-600" },
                  { l: "Incompletos", v: importPreview?.counts.incomplete, c: "text-muted-foreground" },
                ].map((s) => (
                  <div key={s.l} className="bg-card border border-border rounded-md p-2">
                    <div className={`font-heading font-black text-xl ${s.c}`}>{s.v ?? 0}</div>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{s.l}</div>
                  </div>
                ))}
              </div>

              {importPreview?.unknown_columns?.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-800" data-testid="import-unknown-cols">
                  Colunas não reconhecidas (serão ignoradas): {importPreview.unknown_columns.map((c) => <code key={c} className="mx-0.5">{c}</code>)}
                </div>
              )}

              <div>
                <div className="text-sm font-semibold mb-2">Mapeamento de colunas</div>
                <div className="space-y-1.5">
                  {IMPORT_FIELDS.map((f) => (
                    <div key={f.k} className="grid grid-cols-2 items-center gap-3" data-testid={`map-row-${f.k}`}>
                      <span className="text-sm">{f.l}</span>
                      <Select value={importMapping[f.k] || "none"} onValueChange={(v) => setImportMapping((m) => ({ ...m, [f.k]: v === "none" ? undefined : v }))}>
                        <SelectTrigger data-testid={`map-select-${f.k}`}><SelectValue placeholder="— (ignorar)" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">— (ignorar)</SelectItem>
                          {(importPreview?.columns || []).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
                {!importMapping.email && <p className="text-xs text-red-600 mt-2">É obrigatório mapear a coluna do Email.</p>}
              </div>

              {importPreview?.sample?.length > 0 && (
                <div data-testid="import-sample">
                  <div className="text-sm font-semibold mb-2">Pré-visualização (primeiras linhas)</div>
                  <div className="overflow-x-auto border border-border rounded-md">
                    <table className="w-full text-xs">
                      <thead className="bg-secondary/60">
                        <tr>{IMPORT_FIELDS.filter((f) => importMapping[f.k]).map((f) => <th key={f.k} className="px-2 py-1 text-left font-medium whitespace-nowrap">{f.l.replace(" (obrigatório)", "")}</th>)}</tr>
                      </thead>
                      <tbody>
                        {importPreview.sample.map((row, i) => (
                          <tr key={i} className="border-t border-border">
                            {IMPORT_FIELDS.filter((f) => importMapping[f.k]).map((f) => <td key={f.k} className="px-2 py-1 whitespace-nowrap">{row[f.k] || "—"}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            {importStep === 2 && <Button variant="outline" onClick={() => setImportStep(1)} data-testid="import-back-button">Voltar</Button>}
            <Button variant="outline" onClick={() => setImportOpen(false)}>Cancelar</Button>
            {importStep === 1 ? (
              <Button onClick={analyzeImport} disabled={analyzing || !importFile} data-testid="analyze-import-button">{analyzing ? "A analisar…" : "Analisar ficheiro"}</Button>
            ) : (
              <Button onClick={doImport} disabled={importing || !importMapping.email} data-testid="confirm-import-button">{importing ? "A importar…" : `Importar ${importPreview?.counts.valid ?? 0} contactos`}</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Eliminar contacto?</AlertDialogTitle>
            <AlertDialogDescription>Esta ação não pode ser revertida.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="confirm-delete-contact">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <AlertDialogContent data-testid="bulk-delete-dialog">
          <AlertDialogHeader><AlertDialogTitle>Eliminar {selected.size} contacto(s)?</AlertDialogTitle>
            <AlertDialogDescription>Vai eliminar {selected.size} contacto(s) de forma permanente. Esta ação não pode ser revertida.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmBulkDelete} data-testid="confirm-bulk-delete">Eliminar selecionados</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
