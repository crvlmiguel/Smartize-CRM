import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Server, PlugZap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";
import { PageHeader, StatusBadge, EmptyState } from "@/components/common";

const EMPTY = {
  name: "", from_name: "", from_email: "", host: "", port: 587,
  use_ssl: false, use_tls: true, username: "", password: "", signature: "",
  daily_limit: 200, status: "ativo",
};

export default function Smtp() {
  const [accounts, setAccounts] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [testing, setTesting] = useState(false);

  const load = () => api.get("/smtp").then((r) => setAccounts(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (a) => { setEditing(a); setForm({ ...EMPTY, ...a, password: "" }); setOpen(true); };

  const save = async () => {
    if (!form.name.trim() || !form.host.trim() || !form.from_email.trim())
      return toast.error("Nome, servidor e email são obrigatórios");
    try {
      const payload = { ...form, port: Number(form.port), daily_limit: Number(form.daily_limit) };
      if (editing) {
        if (!payload.password) delete payload.password;
        await api.put(`/smtp/${editing.id}`, payload);
      } else {
        await api.post("/smtp", payload);
      }
      toast.success(editing ? "Conta SMTP atualizada" : "Conta SMTP criada");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const { data } = await api.post("/smtp/test", {
        host: form.host, port: Number(form.port), username: form.username,
        password: form.password, use_ssl: form.use_ssl, use_tls: form.use_tls,
        from_email: form.from_email, smtp_account_id: editing?.id,
      });
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (e) { toast.error(apiError(e)); }
    finally { setTesting(false); }
  };

  const confirmDelete = async () => {
    try { await api.delete(`/smtp/${toDelete.id}`); toast.success("Conta eliminada"); setToDelete(null); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div data-testid="smtp-page">
      <PageHeader title="SMTP" subtitle="Contas de envio de email. As passwords são encriptadas.">
        <Button onClick={openNew} data-testid="new-smtp-button"><Plus size={16} className="mr-1.5" /> Nova conta</Button>
      </PageHeader>

      {accounts.length === 0 ? (
        <EmptyState title="Sem contas SMTP" description="Adicione uma conta de envio para começar."
          action={<Button onClick={openNew}><Plus size={16} className="mr-1.5" /> Nova conta</Button>} />
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {accounts.map((a) => (
            <div key={a.id} className="bg-card border border-border rounded-md p-5" data-testid={`smtp-card-${a.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="h-9 w-9 rounded-md bg-secondary flex items-center justify-center shrink-0"><Server size={18} className="text-primary" /></div>
                  <div className="min-w-0">
                    <h3 className="font-heading font-bold tracking-tight truncate">{a.name}</h3>
                    <p className="text-xs text-muted-foreground truncate font-mono">{a.from_email}</p>
                  </div>
                </div>
                <StatusBadge status={a.status} />
              </div>
              <div className="mt-4 text-xs text-muted-foreground font-mono space-y-1">
                <div>{a.host}:{a.port} · {a.use_ssl ? "SSL" : a.use_tls ? "TLS" : "sem encriptação"}</div>
                <div>Limite diário: {a.daily_limit}</div>
              </div>
              <div className="flex gap-1 mt-4 pt-3 border-t border-border">
                <Button variant="outline" size="sm" onClick={() => openEdit(a)} data-testid={`edit-smtp-${a.id}`}><Pencil size={14} className="mr-1" /> Editar</Button>
                <Button variant="outline" size="sm" onClick={() => setToDelete(a)} data-testid={`delete-smtp-${a.id}`} className="text-destructive"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="smtp-dialog">
          <DialogHeader><DialogTitle>{editing ? "Editar conta SMTP" : "Nova conta SMTP"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-4 max-h-[60vh] overflow-y-auto pr-1">
            <div><Label>Nome</Label><Input value={form.name} data-testid="smtp-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Nome do remetente</Label><Input value={form.from_name} data-testid="smtp-fromname-input" onChange={(e) => setForm({ ...form, from_name: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Email remetente</Label><Input type="email" value={form.from_email} data-testid="smtp-fromemail-input" onChange={(e) => setForm({ ...form, from_email: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Servidor SMTP</Label><Input value={form.host} data-testid="smtp-host-input" onChange={(e) => setForm({ ...form, host: e.target.value })} className="mt-1.5" placeholder="smtp.gmail.com" /></div>
            <div><Label>Porta</Label><Input type="number" value={form.port} data-testid="smtp-port-input" onChange={(e) => setForm({ ...form, port: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Limite diário</Label><Input type="number" value={form.daily_limit} data-testid="smtp-limit-input" onChange={(e) => setForm({ ...form, daily_limit: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Username</Label><Input value={form.username} data-testid="smtp-username-input" onChange={(e) => setForm({ ...form, username: e.target.value })} className="mt-1.5" /></div>
            <div><Label>Password {editing && <span className="text-muted-foreground text-xs">(deixe vazio para manter)</span>}</Label><Input type="password" value={form.password} data-testid="smtp-password-input" onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-1.5" /></div>
            <div className="flex items-center gap-3 pt-6"><Switch checked={form.use_ssl} data-testid="smtp-ssl-switch" onCheckedChange={(v) => setForm({ ...form, use_ssl: v, use_tls: v ? false : form.use_tls })} /><Label>SSL (porta 465)</Label></div>
            <div className="flex items-center gap-3 pt-6"><Switch checked={form.use_tls} data-testid="smtp-tls-switch" onCheckedChange={(v) => setForm({ ...form, use_tls: v, use_ssl: v ? false : form.use_ssl })} /><Label>TLS / STARTTLS (587)</Label></div>
            <div className="col-span-2"><Label>Assinatura</Label><Textarea value={form.signature} data-testid="smtp-signature-input" onChange={(e) => setForm({ ...form, signature: e.target.value })} className="mt-1.5" placeholder="Cumprimentos,&#10;Equipa Smartize" /></div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={testConnection} disabled={testing} data-testid="test-smtp-button">
              {testing ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <PlugZap size={16} className="mr-1.5" />} Testar ligação
            </Button>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-smtp-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Eliminar conta SMTP?</AlertDialogTitle></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="confirm-delete-smtp">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
