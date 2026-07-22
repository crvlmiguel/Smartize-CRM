import { ShieldCheck, CheckCircle2, Mail, Clock, Rotate3d, Bug, Ban } from "lucide-react";
import { PageHeader } from "@/components/common";

const RECORDS = [
  {
    name: "SPF", type: "TXT", host: "@",
    value: "v=spf1 include:_spf.google.com ~all",
    desc: "Autoriza os servidores que podem enviar email em nome do seu domínio.",
  },
  {
    name: "DKIM", type: "TXT", host: "google._domainkey",
    value: "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQ...",
    desc: "Assina digitalmente os emails para provar que não foram alterados.",
  },
  {
    name: "DMARC", type: "TXT", host: "_dmarc",
    value: "v=DMARC1; p=quarantine; rua=mailto:dmarc@seudominio.pt",
    desc: "Define a política para emails que falham SPF/DKIM e recebe relatórios.",
  },
];

const PRACTICES = [
  { icon: Clock, title: "Envio distribuído", text: "Emails enviados em fila com atrasos aleatórios (ex.: 30–90s), nunca todos em simultâneo." },
  { icon: Rotate3d, title: "Limite por conta", text: "Limite diário configurável por conta SMTP para proteger a reputação." },
  { icon: Mail, title: "Cabeçalhos RFC", text: "Message-ID, Date, MIME-Version e Content-Type corretos para Gmail, Outlook e Apple Mail." },
  { icon: Bug, title: "Gestão de bounces", text: "Contactos com bounce são marcados automaticamente e excluídos de novos envios." },
  { icon: Ban, title: "Cancelamento automático", text: "Contactos que respondem podem ser parados para não receber novos envios." },
  { icon: CheckCircle2, title: "Validação de emails", text: "Emails vazios, inválidos ou duplicados são removidos antes do envio." },
];

export default function Deliverability() {
  return (
    <div data-testid="deliverability-page">
      <PageHeader title="Deliverability" subtitle="Configure o domínio e siga as boas práticas para máxima entrega." />

      <div className="bg-primary/5 border border-primary/20 rounded-md p-5 mb-6 flex gap-3">
        <ShieldCheck className="text-primary shrink-0" size={22} />
        <div>
          <h2 className="font-heading font-bold">Configure o seu domínio antes de enviar</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Adicione os registos DNS abaixo no seu fornecedor de domínio. Sem SPF, DKIM e DMARC os emails têm maior risco de ir para spam.
          </p>
        </div>
      </div>

      <div className="space-y-4 mb-8">
        {RECORDS.map((r) => (
          <div key={r.name} className="bg-card border border-border rounded-md p-5" data-testid={`dns-record-${r.name.toLowerCase()}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold bg-primary text-primary-foreground">{r.name}</span>
              <span className="text-sm text-muted-foreground">{r.desc}</span>
            </div>
            <div className="grid md:grid-cols-3 gap-3 mt-3 text-xs">
              <div><div className="text-muted-foreground uppercase tracking-wide mb-1">Tipo</div><div className="font-mono bg-secondary rounded px-2 py-1.5">{r.type}</div></div>
              <div><div className="text-muted-foreground uppercase tracking-wide mb-1">Host</div><div className="font-mono bg-secondary rounded px-2 py-1.5">{r.host}</div></div>
              <div><div className="text-muted-foreground uppercase tracking-wide mb-1">Valor</div><div className="font-mono bg-secondary rounded px-2 py-1.5 break-all">{r.value}</div></div>
            </div>
          </div>
        ))}
      </div>

      <h2 className="font-heading font-bold text-xl mb-4">Boas práticas implementadas</h2>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {PRACTICES.map((p) => (
          <div key={p.title} className="bg-card border border-border rounded-md p-5">
            <p.icon className="text-primary mb-2" size={20} />
            <h3 className="font-heading font-bold text-sm">{p.title}</h3>
            <p className="text-sm text-muted-foreground mt-1">{p.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
