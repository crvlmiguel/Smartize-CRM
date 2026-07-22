import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Users, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";
import { PageHeader, EmptyState } from "@/components/common";

export default function Groups() {
  const [groups, setGroups] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", description: "" });
  const [toDelete, setToDelete] = useState(null);

  const load = () => api.get("/groups").then((r) => setGroups(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ name: "", description: "" }); setOpen(true); };
  const openEdit = (g) => { setEditing(g); setForm({ name: g.name, description: g.description || "" }); setOpen(true); };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Nome obrigatório");
    try {
      if (editing) await api.put(`/groups/${editing.id}`, form);
      else await api.post("/groups", form);
      toast.success(editing ? "Grupo atualizado" : "Grupo criado");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const confirmDelete = async () => {
    try {
      await api.delete(`/groups/${toDelete.id}`);
      toast.success("Grupo eliminado"); setToDelete(null); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div data-testid="groups-page">
      <PageHeader title="Grupos" subtitle="Organize os contactos em grupos.">
        <Button onClick={openNew} data-testid="new-group-button"><Plus size={16} className="mr-1.5" /> Novo grupo</Button>
      </PageHeader>

      {groups.length === 0 ? (
        <EmptyState title="Sem grupos" description="Crie o seu primeiro grupo de contactos."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Novo grupo</Button>} />
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((g) => (
            <div key={g.id} className="bg-card border border-border rounded-md p-5" data-testid={`group-card-${g.id}`}>
              <div className="flex items-start justify-between">
                <h3 className="font-heading font-bold text-lg tracking-tight">{g.name}</h3>
                <div className="flex gap-1">
                  <button onClick={() => openEdit(g)} data-testid={`edit-group-${g.id}`} className="p-1.5 rounded-md hover:bg-secondary text-muted-foreground"><Pencil size={15} /></button>
                  <button onClick={() => setToDelete(g)} data-testid={`delete-group-${g.id}`} className="p-1.5 rounded-md hover:bg-secondary text-destructive"><Trash2 size={15} /></button>
                </div>
              </div>
              <p className="text-sm text-muted-foreground mt-1 min-h-[20px]">{g.description}</p>
              <div className="flex items-center gap-4 mt-4 text-sm">
                <span className="inline-flex items-center gap-1.5 font-semibold"><Users size={15} className="text-primary" /> {g.contact_count} contactos</span>
                <span className="inline-flex items-center gap-1.5 text-muted-foreground text-xs"><Calendar size={13} /> {new Date(g.created_at).toLocaleDateString("pt-PT")}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="group-dialog">
          <DialogHeader><DialogTitle>{editing ? "Editar grupo" : "Novo grupo"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Nome</Label><Input value={form.name} data-testid="group-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Descrição</Label><Textarea value={form.description} data-testid="group-description-input" onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1.5" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-group-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar grupo?</AlertDialogTitle>
            <AlertDialogDescription>Os contactos deste grupo não serão eliminados, apenas desassociados.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="confirm-delete-group">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
