export function PageHeader({ title, subtitle, children, testid }) {
  return (
    <div className="flex items-start justify-between mb-8" data-testid={testid}>
      <div>
        <h1 className="font-heading font-black text-3xl tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted-foreground mt-1 text-sm">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

const STATUS_STYLES = {
  ativo: "bg-emerald-50 text-emerald-700 border-emerald-200",
  respondido: "bg-blue-50 text-blue-700 border-blue-200",
  bounce: "bg-red-50 text-red-700 border-red-200",
  descadastrado: "bg-zinc-100 text-zinc-600 border-zinc-200",
  sent: "bg-blue-50 text-blue-700 border-blue-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  bounced: "bg-red-50 text-red-700 border-red-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-zinc-100 text-zinc-600 border-zinc-200",
  rascunho: "bg-zinc-100 text-zinc-600 border-zinc-200",
  sending: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  cancelada: "bg-red-50 text-red-700 border-red-200",
  arquivada: "bg-zinc-100 text-zinc-500 border-zinc-200",
};

const STATUS_LABELS = {
  sent: "Enviado", pending: "Pendente", bounced: "Bounce", failed: "Falhou",
  cancelled: "Cancelado", rascunho: "Rascunho", sending: "A enviar",
  completed: "Concluída", cancelada: "Cancelada", arquivada: "Arquivada",
  ativo: "Ativo", respondido: "Respondido", bounce: "Bounce", descadastrado: "Descadastrado",
};

export function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] || "bg-zinc-100 text-zinc-600 border-zinc-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${cls}`}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center border border-dashed border-border rounded-md bg-card">
      <img
        src="https://images.pexels.com/photos/36352473/pexels-photo-36352473.jpeg?auto=compress&cs=tinysrgb&w=200"
        alt=""
        className="w-24 h-24 object-cover rounded-md mb-5 grayscale opacity-80"
      />
      <h3 className="font-heading font-bold text-lg">{title}</h3>
      {description && <p className="text-sm text-muted-foreground mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
