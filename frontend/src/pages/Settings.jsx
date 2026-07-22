import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Save, Upload, Trash2, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/common";
import EmailAccounts from "@/components/EmailAccounts";
import { useBranding } from "@/context/BrandingContext";

const TIMEZONES = ["Europe/Lisbon", "Europe/Madrid", "Europe/London", "America/Sao_Paulo", "UTC"];
const ACCEPTED = "image/png,image/svg+xml,image/jpeg,image/jpg,image/webp";

export default function Settings() {
  const [form, setForm] = useState(null);
  const { refresh } = useBranding();
  const fileRef = useRef(null);

  useEffect(() => { api.get("/settings").then((r) => setForm(r.data)).catch(() => {}); }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onLogoFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 1024 * 1024) return toast.error("Imagem demasiado grande (máx. 1MB)");
    const reader = new FileReader();
    reader.onload = () => set("logo_url", reader.result);
    reader.readAsDataURL(file);
  };

  const save = async () => {
    try {
      const { data } = await api.put("/settings", {
        company_name: form.company_name, logo_url: form.logo_url,
        language: form.language, timezone: form.timezone, footer: form.footer,
      });
      setForm(data);
      refresh();
      toast.success("Configurações guardadas");
    } catch (e) { toast.error(apiError(e)); }
  };

  if (!form) return <div className="text-muted-foreground">A carregar…</div>;

  return (
    <div data-testid="settings-page">
      <PageHeader title="Configurações" subtitle="Preferências da empresa e contas de envio." />

      <Tabs defaultValue="geral">
        <TabsList>
          <TabsTrigger value="geral" data-testid="tab-geral">Geral</TabsTrigger>
          <TabsTrigger value="contas" data-testid="tab-contas">Contas de Email</TabsTrigger>
        </TabsList>

        <TabsContent value="geral" className="mt-5">
          <div className="max-w-2xl bg-card border border-border rounded-md p-6 space-y-5">
            <div><Label>Nome da empresa</Label><Input value={form.company_name || ""} data-testid="company-name-input" onChange={(e) => set("company_name", e.target.value)} className="mt-1.5" /></div>

            <div>
              <Label>Logótipo</Label>
              <div className="mt-1.5 flex items-center gap-4">
                <div className="h-16 w-40 border border-border rounded-md bg-white flex items-center justify-center overflow-hidden" data-testid="logo-preview">
                  {form.logo_url ? <img src={form.logo_url} alt="logo" className="max-h-12 max-w-[140px] object-contain" /> : <ImageIcon size={20} className="text-muted-foreground" />}
                </div>
                <div className="flex gap-2">
                  <input ref={fileRef} type="file" accept={ACCEPTED} className="hidden" data-testid="logo-file-input" onChange={onLogoFile} />
                  <Button variant="outline" onClick={() => fileRef.current?.click()} data-testid="upload-logo-button"><Upload size={16} className="mr-1.5" /> Carregar logótipo</Button>
                  {form.logo_url && <Button variant="outline" onClick={() => set("logo_url", "")} data-testid="remove-logo-button" className="text-destructive"><Trash2 size={16} /></Button>}
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-2">PNG, SVG, JPG ou WEBP (máx. 1MB). Aplicado em toda a plataforma após guardar.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Idioma</Label>
                <Select value={form.language || "pt"} onValueChange={(v) => set("language", v)}>
                  <SelectTrigger className="mt-1.5" data-testid="language-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pt">Português</SelectItem>
                    <SelectItem value="en">Inglês</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Fuso horário</Label>
                <Select value={form.timezone || "Europe/Lisbon"} onValueChange={(v) => set("timezone", v)}>
                  <SelectTrigger className="mt-1.5" data-testid="timezone-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{TIMEZONES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label>Rodapé</Label><Textarea value={form.footer || ""} data-testid="footer-input" onChange={(e) => set("footer", e.target.value)} className="mt-1.5" rows={2} /></div>
            <p className="text-xs text-muted-foreground">As assinaturas de email são geridas individualmente em cada Conta de Email.</p>
            <div className="pt-2">
              <Button onClick={save} data-testid="save-settings-button"><Save size={16} className="mr-1.5" /> Guardar</Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="contas" className="mt-5">
          <EmailAccounts />
        </TabsContent>
      </Tabs>
    </div>
  );
}
