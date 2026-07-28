import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Upload, Search, X, Briefcase } from "lucide-react";
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
import api, { apiError } from "@/lib/api";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common";

const STATUSES = ["ativo", "respondido", "bounce", "descadastrado"];
const EMPTY = {
  first_name: "", last_name: "", company: "", position: "", email: "",
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
  const [importOpen, setImportOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importGroup, setImportGroup] = useState("none");
  const [importing, setImporting] = useState(false);

  const load = useCallback(() => {
    const params = {};
    if (search) params.search = search;
    if (groupFilter !== "all") params.group_id = groupFilter;
    if (statusFilter !== "all") params.status = statusFilter;
    api.get("/contacts", { params }).then((r) => setContacts(r.data)).catch(() => {});
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

  const createDealFromContact = (c) => {
    navigate("/negocios", { state: { contact: c } });
  };

  const doImport = async () => {
    if (!importFile) return toast.error("Selecione um ficheiro");
    setImporting(true);
    const fd = new FormData();
    fd.append("file", importFile);
    fd.append("group_id", importGroup === "none" ? "" : importGroup);
    try {
      const { data } = await api.post("/contacts/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${data.imported} importados, ${data.duplicates} duplicados, ${data.skipped} inválidos`);
      setImportOpen(false); setImportFile(null); load();
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
        <Button variant="outline" onClick={() => setImportOpen(true)} data-testid="import-contacts-button"><Upload size={16} className="mr-1.5" /> Importar</Button>
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

      {contacts.length === 0 ? (
        <EmptyState title="Sem contactos" description="Crie manualmente ou importe um ficheiro CSV/Excel."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Novo contacto</Button>} />
      ) : (
        <div className="bg-card border border-border rounded-md overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Empresa</TableHead>
                <TableHead>Grupo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {contacts.map((c) => (
                <TableRow key={c.id} data-testid={`contact-row-${c.id}`}>
                  <TableCell className="font-medium">{`${c.first_name || ""} ${c.last_name || ""}`.trim() || "—"}</TableCell>
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
        <DialogContent data-testid="import-dialog">
          <DialogHeader>
            <DialogTitle>Importar contactos</DialogTitle>
            <DialogDescription>Ficheiro CSV ou Excel. Duplicados e emails inválidos são removidos automaticamente.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
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
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)}>Cancelar</Button>
            <Button onClick={doImport} disabled={importing} data-testid="confirm-import-button">{importing ? "A importar…" : "Importar"}</Button>
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
    </div>
  );
}
