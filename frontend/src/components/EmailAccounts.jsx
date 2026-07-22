import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Plus, Pencil, Trash2, Server, PlugZap, Loader2, Send, Zap, Star,
  Power, Mail, CheckCircle2, XCircle, HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";
import { StatusBadge } from "@/components/common";
import { SignatureEditor, SIGNATURE_TEMPLATE } from "@/components/SignatureEditor";

const EMPTY = {
  name: "", account_type: "smtp", from_name: "", from_email: "", host: "", port: 587,
  use_ssl: false, use_tls: true, username: "", password: "", reply_to: "",
  signature_html: "", daily_limit: 200, status: "ativo", is_default: false,
  imap_host: "", imap_port: 993, imap_username: "", imap_password: "",
};

const GOOGLE_DEFAULTS = { host: "smtp.gmail.com", port: 465, use_ssl: true, use_tls: false, imap_host: "imap.gmail.com", imap_port: 993 };

export default function EmailAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [open, setOpen] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [toDelete, setToDelete] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testSendOpen, setTestSendOpen] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [sendingTest, setSendingTest] = useState(false);

  const load = () => api.get("/smtp").then((r) => setAccounts(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const startNew = () => { setEditing(null); setForm(EMPTY); setChoosing(true); };
  const pickType = (type) => {
    setForm(type === "google" ? { ...EMPTY, account_type: "google", ...GOOGLE_DEFAULTS } : { ...EMPTY, account_type: "smtp" });
    setChoosing(false); setOpen(true);
  };
  const openEdit = (a) => { setEditing(a); setForm({ ...EMPTY, ...a, password: "", imap_password: "" }); setOpen(true); };
  const applyHostinger = () => setForm((f) => ({ ...f, host: "smtp.hostinger.com", port: 465, use_ssl: true, use_tls: false }));

  const save = async () => {
    if (!form.name.trim() || !form.from_email.trim()) return toast.error("Nome e email são obrigatórios");
    if (form.account_type === "google" && !form.username) form.username = form.from_email;
    try {
      const payload = { ...form, port: Number(form.port), daily_limit: Number(form.daily_limit), imap_port: Number(form.imap_port) || null };
      if (editing) {
        if (!payload.password) delete payload.password;
        if (!payload.imap_password) delete payload.imap_password;
        await api.put(`/smtp/${editing.id}`, payload);
      } else {
        await api.post("/smtp", payload);
      }
      toast.success(editing ? "Conta atualizada" : "Conta criada");
      setOpen(false); load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const { data } = await api.post("/smtp/test", {
        host: form.host, port: Number(form.port), username: form.username || form.from_email,
        password: form.password, use_ssl: form.use_ssl, use_tls: form.use_tls,
        from_email: form.from_email, smtp_account_id: editing?.id,
      });
      data.success ? toast.success(data.message) : toast.error(data.message);
      if (editing) load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setTesting(false); }
  };

  const sendTest = async () => {
    if (!editing) return toast.error("Guarde a conta antes de enviar um teste");
    if (!testEmail) return toast.error("Indique o email de destino");
    setSendingTest(true);
    try {
      const { data } = await api.post("/smtp/test-send", { smtp_account_id: editing.id, to_email: testEmail, signature_html: form.signature_html });
      data.success ? toast.success(data.message) : toast.error(data.message);
      if (data.success) setTestSendOpen(false);
    } catch (e) { toast.error(apiError(e)); }
    finally { setSendingTest(false); }
  };

  const setDefault = async (a) => { try { await api.post(`/smtp/${a.id}/set-default`); toast.success("Conta predefinida atualizada"); load(); } catch (e) { toast.error(apiError(e)); } };
  const disconnect = async (a) => { try { await api.post(`/smtp/${a.id}/disconnect`); toast.success("Conta desligada"); load(); } catch (e) { toast.error(apiError(e)); } };
  const confirmDelete = async () => { try { await api.delete(`/smtp/${toDelete.id}`); toast.success("Conta eliminada"); setToDelete(null); load(); } catch (e) { toast.error(apiError(e)); } };

  const isGoogle = form.account_type === "google";

  const connBadge = (a) => {
    if (a.connection_status === "connected") return <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><CheckCircle2 size={13} /> Ligada</span>;
    if (a.connection_status === "disconnected") return <span className="inline-flex items-center gap-1 text-xs text-red-600"><XCircle size={13} /> Desligada</span>;
    return <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><HelpCircle size={13} /> Por testar</span>;
  };

  return (
    <div data-testid="email-accounts">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-heading font-bold text-lg">Contas de Email</h2>
          <p className="text-sm text-muted-foreground">Faça a gestão das contas de envio (SMTP e Google).</p>
        </div>
        <Button onClick={startNew} data-testid="new-smtp-button"><Plus size={16} className="mr-1.5" /> Nova conta</Button>
      </div>

      {accounts.length === 0 ? (
        <div className="border border-dashed border-border rounded-md p-10 text-center text-sm text-muted-foreground">
          Sem contas de email. Adicione a primeira para começar a enviar.
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {accounts.map((a) => (
            <div key={a.id} className="bg-card border border-border rounded-md p-5" data-testid={`smtp-card-${a.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="h-9 w-9 rounded-md bg-secondary flex items-center justify-center shrink-0">
                    {a.account_type === "google" ? <Mail size={18} className="text-primary" /> : <Server size={18} className="text-primary" />}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-heading font-bold tracking-tight truncate">{a.name}</h3>
                      {a.is_default && <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-primary bg-primary/10 px-1.5 py-0.5 rounded" data-testid={`default-badge-${a.id}`}><Star size={10} /> Predefinida</span>}
                    </div>
                    <p className="text-xs text-muted-foreground truncate font-mono">{a.from_email}</p>
                  </div>
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wide bg-secondary px-1.5 py-0.5 rounded">{a.account_type === "google" ? "Google" : "SMTP"}</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs">
                {connBadge(a)}
                <span className="text-muted-foreground">{a.last_sync ? `Sync: ${new Date(a.last_sync).toLocaleString("pt-PT")}` : "—"}</span>
              </div>
              <div className="flex flex-wrap gap-1 mt-4 pt-3 border-t border-border">
                <Button variant="outline" size="sm" onClick={() => openEdit(a)} data-testid={`edit-smtp-${a.id}`}><Pencil size={14} className="mr-1" /> Editar</Button>
                {!a.is_default && <Button variant="outline" size="sm" onClick={() => setDefault(a)} data-testid={`set-default-${a.id}`}><Star size={14} className="mr-1" /> Predefinir</Button>}
                <Button variant="outline" size="sm" onClick={() => disconnect(a)} data-testid={`disconnect-${a.id}`}><Power size={14} /></Button>
                <Button variant="outline" size="sm" onClick={() => setToDelete(a)} data-testid={`delete-smtp-${a.id}`} className="text-destructive"><Trash2 size={14} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Choose type */}
      <Dialog open={choosing} onOpenChange={setChoosing}>
        <DialogContent data-testid="choose-type-dialog">
          <DialogHeader><DialogTitle>Tipo de conta</DialogTitle><DialogDescription>Como pretende ligar esta conta de envio?</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <button onClick={() => pickType("smtp")} data-testid="type-smtp" className="p-5 rounded-md border border-border hover:border-primary text-left transition-colors">
              <Server size={20} className="text-primary mb-2" />
              <div className="font-semibold text-sm">SMTP Personalizado</div>
              <div className="text-xs text-muted-foreground mt-1">Hostinger, cPanel, ou qualquer servidor SMTP.</div>
            </button>
            <button onClick={() => pickType("google")} data-testid="type-google" className="p-5 rounded-md border border-border hover:border-primary text-left transition-colors">
              <Mail size={20} className="text-primary mb-2" />
              <div className="font-semibold text-sm">Google Workspace / Gmail</div>
              <div className="text-xs text-muted-foreground mt-1">Envie a partir da sua conta Google.</div>
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Editor */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-4xl" data-testid="smtp-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar conta" : (isGoogle ? "Nova conta Google" : "Nova conta SMTP")}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[68vh] overflow-y-auto pr-1 space-y-5">
            {isGoogle && (
              <div className="bg-primary/5 border border-primary/20 rounded-md p-4">
                <div className="flex items-center gap-2 font-semibold text-sm"><Mail size={16} className="text-primary" /> Ligar Conta Google</div>
                <p className="text-xs text-muted-foreground mt-1">A ligação OAuth "Iniciar sessão com Google" será ativada em breve. Por agora, use uma <b>App Password</b> do Google (Conta Google → Segurança → Palavras-passe de aplicações). O servidor é configurado automaticamente (smtp.gmail.com).</p>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Configuração</span>
              {!isGoogle && <Button variant="outline" size="sm" onClick={applyHostinger} data-testid="hostinger-preset-button"><Zap size={14} className="mr-1.5" /> Preencher Hostinger</Button>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Nome da conta</Label><Input value={form.name} data-testid="smtp-name-input" onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1.5" placeholder="Comercial" /></div>
              <div><Label>Nome do remetente</Label><Input value={form.from_name} data-testid="smtp-fromname-input" onChange={(e) => setForm({ ...form, from_name: e.target.value })} className="mt-1.5" /></div>
              <div><Label>Email remetente</Label><Input type="email" value={form.from_email} data-testid="smtp-fromemail-input" onChange={(e) => setForm({ ...form, from_email: e.target.value, username: isGoogle ? e.target.value : form.username })} className="mt-1.5" placeholder={isGoogle ? "voce@gmail.com" : "comercial@empresa.pt"} /></div>
              <div><Label>Reply-To (opcional)</Label><Input type="email" value={form.reply_to} data-testid="smtp-replyto-input" onChange={(e) => setForm({ ...form, reply_to: e.target.value })} className="mt-1.5" /></div>
              {!isGoogle && <>
                <div><Label>Servidor SMTP</Label><Input value={form.host} data-testid="smtp-host-input" onChange={(e) => setForm({ ...form, host: e.target.value })} className="mt-1.5" placeholder="smtp.hostinger.com" /></div>
                <div><Label>Porta</Label><Input type="number" value={form.port} data-testid="smtp-port-input" onChange={(e) => setForm({ ...form, port: e.target.value })} className="mt-1.5" /></div>
                <div><Label>Username</Label><Input value={form.username} data-testid="smtp-username-input" onChange={(e) => setForm({ ...form, username: e.target.value })} className="mt-1.5" /></div>
              </>}
              <div><Label>{isGoogle ? "App Password" : "Password"} {editing && <span className="text-muted-foreground text-xs">(vazio mantém)</span>}</Label><Input type="password" value={form.password} data-testid="smtp-password-input" onChange={(e) => setForm({ ...form, password: e.target.value })} className="mt-1.5" /></div>
              <div><Label>Limite diário</Label><Input type="number" value={form.daily_limit} data-testid="smtp-limit-input" onChange={(e) => setForm({ ...form, daily_limit: e.target.value })} className="mt-1.5" /></div>
              {!isGoogle && (
                <div className="flex items-center gap-6 pt-6">
                  <div className="flex items-center gap-2"><Switch checked={form.use_ssl} data-testid="smtp-ssl-switch" onCheckedChange={(v) => setForm({ ...form, use_ssl: v, use_tls: v ? false : form.use_tls })} /><Label>SSL (465)</Label></div>
                  <div className="flex items-center gap-2"><Switch checked={form.use_tls} data-testid="smtp-tls-switch" onCheckedChange={(v) => setForm({ ...form, use_tls: v, use_ssl: v ? false : form.use_ssl })} /><Label>TLS (587)</Label></div>
                </div>
              )}
              <div className="flex items-center gap-2 pt-6"><Switch checked={form.is_default} data-testid="smtp-default-switch" onCheckedChange={(v) => setForm({ ...form, is_default: v })} /><Label>Conta predefinida</Label></div>
            </div>

            <details className="border border-border rounded-md p-3">
              <summary className="text-sm font-medium cursor-pointer">IMAP — leitura de respostas (opcional)</summary>
              <div className="grid grid-cols-2 gap-4 mt-3">
                <div><Label>Servidor IMAP</Label><Input value={form.imap_host || ""} data-testid="imap-host-input" onChange={(e) => setForm({ ...form, imap_host: e.target.value })} className="mt-1.5" placeholder="imap.hostinger.com" /></div>
                <div><Label>Porta IMAP</Label><Input type="number" value={form.imap_port || ""} data-testid="imap-port-input" onChange={(e) => setForm({ ...form, imap_port: e.target.value })} className="mt-1.5" /></div>
                <div><Label>Username IMAP</Label><Input value={form.imap_username || ""} data-testid="imap-username-input" onChange={(e) => setForm({ ...form, imap_username: e.target.value })} className="mt-1.5" /></div>
                <div><Label>Password IMAP {editing && <span className="text-muted-foreground text-xs">(vazio mantém)</span>}</Label><Input type="password" value={form.imap_password || ""} data-testid="imap-password-input" onChange={(e) => setForm({ ...form, imap_password: e.target.value })} className="mt-1.5" /></div>
              </div>
            </details>

            <div className="pt-2 border-t border-border">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Assinatura HTML desta conta</span>
                {!form.signature_html && <Button variant="outline" size="sm" onClick={() => setForm({ ...form, signature_html: SIGNATURE_TEMPLATE })} data-testid="use-signature-template">Usar modelo</Button>}
              </div>
              <SignatureEditor value={form.signature_html} onChange={(v) => setForm((f) => ({ ...f, signature_html: v }))} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={testConnection} disabled={testing} data-testid="test-smtp-button">
              {testing ? <Loader2 size={16} className="mr-1.5 animate-spin" /> : <PlugZap size={16} className="mr-1.5" />} Testar ligação
            </Button>
            {editing && <Button variant="outline" onClick={() => setTestSendOpen(true)} data-testid="open-test-send-button"><Send size={16} className="mr-1.5" /> Enviar teste</Button>}
            <Button variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button onClick={save} data-testid="save-smtp-button">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={testSendOpen} onOpenChange={setTestSendOpen}>
        <DialogContent data-testid="smtp-test-send-dialog">
          <DialogHeader><DialogTitle>Enviar email de teste</DialogTitle><DialogDescription>Enviamos uma mensagem de teste com a assinatura desta conta.</DialogDescription></DialogHeader>
          <div><Label>Email de destino</Label><Input type="email" value={testEmail} data-testid="smtp-test-email-input" onChange={(e) => setTestEmail(e.target.value)} className="mt-1.5" placeholder="eu@exemplo.pt" /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTestSendOpen(false)}>Cancelar</Button>
            <Button onClick={sendTest} disabled={sendingTest} data-testid="send-smtp-test-button">{sendingTest ? "A enviar…" : "Enviar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Eliminar conta de email?</AlertDialogTitle></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} data-testid="confirm-delete-smtp">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
