import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/common";

const TIMEZONES = ["Europe/Lisbon", "Europe/Madrid", "Europe/London", "America/Sao_Paulo", "UTC"];

export default function Settings() {
  const [form, setForm] = useState(null);

  useEffect(() => { api.get("/settings").then((r) => setForm(r.data)).catch(() => {}); }, []);

  const save = async () => {
    try {
      const { data } = await api.put("/settings", {
        company_name: form.company_name, logo_url: form.logo_url,
        language: form.language, timezone: form.timezone,
        default_signature: form.default_signature, footer: form.footer,
      });
      setForm(data);
      toast.success("Configurações guardadas");
    } catch (e) { toast.error(apiError(e)); }
  };

  if (!form) return <div className="text-muted-foreground">A carregar…</div>;
  const set = (k, v) => setForm({ ...form, [k]: v });

  return (
    <div data-testid="settings-page" className="max-w-2xl">
      <PageHeader title="Configurações" subtitle="Preferências da empresa e envio.">
        <Button onClick={save} data-testid="save-settings-button"><Save size={16} className="mr-1.5" /> Guardar</Button>
      </PageHeader>

      <div className="bg-card border border-border rounded-md p-6 space-y-5">
        <div><Label>Nome da empresa</Label><Input value={form.company_name || ""} data-testid="company-name-input" onChange={(e) => set("company_name", e.target.value)} className="mt-1.5" /></div>
        <div><Label>Logo (URL)</Label><Input value={form.logo_url || ""} data-testid="logo-url-input" onChange={(e) => set("logo_url", e.target.value)} className="mt-1.5" placeholder="https://…" /></div>
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
        <div><Label>Assinatura padrão</Label><Textarea value={form.default_signature || ""} data-testid="signature-input" onChange={(e) => set("default_signature", e.target.value)} className="mt-1.5" rows={3} /></div>
        <div><Label>Rodapé</Label><Textarea value={form.footer || ""} data-testid="footer-input" onChange={(e) => set("footer", e.target.value)} className="mt-1.5" rows={2} /></div>
      </div>
    </div>
  );
}
