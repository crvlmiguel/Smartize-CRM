import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Star, Check, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { apiError } from "@/lib/api";

const STAGE_COLORS = [
  "#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#eab308",
  "#14b8a6", "#10b981", "#ef4444", "#64748b", "#06b6d4",
];
const TYPES = [
  { v: "open", l: "Aberta" },
  { v: "won", l: "Ganho" },
  { v: "lost", l: "Perdido" },
];
const newId = () =>
  (window.crypto?.randomUUID?.() || `s${Date.now()}${Math.floor(Math.random() * 1e4)}`);

export default function PipelineManager({ open, onOpenChange, pipelines, selectedId, onChanged }) {
  const [pid, setPid] = useState(selectedId || "");
  const [name, setName] = useState("");
  const [stages, setStages] = useState([]);
  const [dragIdx, setDragIdx] = useState(null);
  const [toDelete, setToDelete] = useState(null);

  const current = pipelines.find((p) => p.id === pid);

  useEffect(() => {
    if (!open) return;
    const first = pipelines.find((p) => p.id === selectedId) || pipelines[0];
    if (first) selectPipeline(first);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectPipeline = (p) => {
    setPid(p.id);
    setName(p.name);
    setStages((p.stages || []).map((s) => ({ ...s })));
  };

  const createPipeline = async () => {
    try {
      const { data } = await api.post("/pipelines", { name: "Novo pipeline" });
      toast.success("Pipeline criado");
      await onChanged();
      selectPipeline(data);
    } catch (e) { toast.error(apiError(e)); }
  };

  const setDefault = async (p) => {
    try { await api.post(`/pipelines/${p.id}/set-default`); toast.success("Pipeline padrão definido"); await onChanged(); }
    catch (e) { toast.error(apiError(e)); }
  };

  const deletePipeline = async (p) => {
    try {
      await api.delete(`/pipelines/${p.id}`);
      toast.success("Pipeline eliminado");
      setToDelete(null);
      const remaining = pipelines.filter((x) => x.id !== p.id);
      await onChanged();
      if (remaining[0]) selectPipeline(remaining[0]);
    } catch (e) { toast.error(apiError(e)); }
  };

  const updateStage = (i, k, v) => setStages((s) => s.map((st, idx) => (idx === i ? { ...st, [k]: v } : st)));
  const removeStage = (i) => setStages((s) => s.filter((_, idx) => idx !== i));
  const addStageAt = (i) => {
    const st = { id: newId(), name: "Nova etapa", type: "open", color: STAGE_COLORS[stages.length % STAGE_COLORS.length], probability: 0 };
    setStages((s) => { const c = [...s]; c.splice(i, 0, st); return c; });
  };

  const onDrop = (i) => {
    if (dragIdx === null || dragIdx === i) { setDragIdx(null); return; }
    setStages((s) => {
      const c = [...s];
      const [moved] = c.splice(dragIdx, 1);
      c.splice(i, 0, moved);
      return c;
    });
    setDragIdx(null);
  };

  const save = async () => {
    if (!name.trim()) return toast.error("Indique o nome do pipeline");
    if (!stages.length) return toast.error("Adicione pelo menos uma etapa");
    if (stages.some((s) => !s.name.trim())) return toast.error("Todas as etapas precisam de nome");
    try {
      await api.put(`/pipelines/${pid}`, {
        name,
        stages: stages.map((s) => ({
          id: s.id, name: s.name, type: s.type || "open",
          color: s.color || "#64748b", probability: Number(s.probability) || 0,
        })),
      });
      toast.success("Pipeline guardado");
      await onChanged();
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl" data-testid="pipeline-manager-dialog">
          <DialogHeader>
            <DialogTitle>Gerir pipelines</DialogTitle>
            <DialogDescription>Crie, edite e organize os seus pipelines e etapas.</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-[220px_1fr] gap-4 max-h-[65vh]">
            {/* Pipelines list */}
            <div className="border-r border-border pr-3 space-y-1 overflow-y-auto">
              {pipelines.map((p) => (
                <div key={p.id}
                  onClick={() => selectPipeline(p)}
                  data-testid={`pm-pipeline-${p.id}`}
                  className={`group flex items-center justify-between gap-1 px-2 py-2 rounded-md cursor-pointer text-sm ${p.id === pid ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}>
                  <span className="truncate flex items-center gap-1.5">
                    {p.is_default && <Star size={12} className={p.id === pid ? "fill-current" : "fill-amber-400 text-amber-400"} />}
                    {p.name}
                  </span>
                  <div className={`flex gap-0.5 ${p.id === pid ? "" : "opacity-0 group-hover:opacity-100"}`}>
                    {!p.is_default && (
                      <button onClick={(e) => { e.stopPropagation(); setDefault(p); }} title="Definir como padrão" data-testid={`pm-setdefault-${p.id}`} className="p-1 rounded hover:bg-black/10"><Star size={13} /></button>
                    )}
                    <button onClick={(e) => { e.stopPropagation(); setToDelete(p); }} title="Eliminar" data-testid={`pm-delete-${p.id}`} className="p-1 rounded hover:bg-black/10"><Trash2 size={13} /></button>
                  </div>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={createPipeline} data-testid="pm-new-pipeline" className="w-full mt-2"><Plus size={14} className="mr-1" /> Novo pipeline</Button>
            </div>

            {/* Stage editor */}
            <div className="overflow-y-auto pr-1 space-y-3">
              {current ? (
                <>
                  <div>
                    <Label className="text-xs">Nome do pipeline</Label>
                    <Input value={name} data-testid="pm-pipeline-name" onChange={(e) => setName(e.target.value)} className="mt-1" />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label className="text-xs">Etapas</Label>
                    <button onClick={() => addStageAt(0)} data-testid="pm-insert-top" className="text-xs text-primary hover:underline">+ Inserir no topo</button>
                  </div>
                  <div className="space-y-2" data-testid="pm-stages">
                    {stages.map((st, i) => (
                      <div key={st.id} draggable onDragStart={() => setDragIdx(i)}
                        onDragOver={(e) => e.preventDefault()} onDrop={() => onDrop(i)}
                        data-testid={`pm-stage-${i}`}
                        className="flex items-center gap-2 bg-secondary/40 border border-border rounded-md p-2">
                        <GripVertical size={15} className="text-muted-foreground cursor-grab shrink-0" />
                        <input type="color" value={st.color || "#64748b"} data-testid={`pm-stage-color-${i}`}
                          onChange={(e) => updateStage(i, "color", e.target.value)}
                          className="w-7 h-7 rounded cursor-pointer border border-border shrink-0 bg-transparent" />
                        <Input value={st.name} data-testid={`pm-stage-name-${i}`} onChange={(e) => updateStage(i, "name", e.target.value)} className="h-8 flex-1" placeholder="Nome da etapa" />
                        <div className="flex items-center gap-1 shrink-0">
                          <Input type="number" min="0" max="100" value={st.probability ?? 0} data-testid={`pm-stage-prob-${i}`} onChange={(e) => updateStage(i, "probability", e.target.value)} className="h-8 w-16" />
                          <span className="text-xs text-muted-foreground">%</span>
                        </div>
                        <Select value={st.type || "open"} onValueChange={(v) => updateStage(i, "type", v)}>
                          <SelectTrigger className="h-8 w-28 shrink-0" data-testid={`pm-stage-type-${i}`}><SelectValue /></SelectTrigger>
                          <SelectContent>{TYPES.map((t) => <SelectItem key={t.v} value={t.v}>{t.l}</SelectItem>)}</SelectContent>
                        </Select>
                        <button onClick={() => removeStage(i)} data-testid={`pm-stage-remove-${i}`} className="p-1 rounded hover:bg-secondary text-destructive shrink-0"><Trash2 size={14} /></button>
                      </div>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" onClick={() => addStageAt(stages.length)} data-testid="pm-add-stage" className="w-full"><Plus size={14} className="mr-1" /> Adicionar etapa</Button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Selecione ou crie um pipeline.</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>Fechar</Button>
            <Button onClick={save} data-testid="pm-save"><Check size={15} className="mr-1" /> Guardar alterações</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar pipeline?</AlertDialogTitle>
            <AlertDialogDescription>Todos os negócios e automações de "{toDelete?.name}" serão eliminados. Esta ação não pode ser revertida.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => deletePipeline(toDelete)} data-testid="pm-confirm-delete">Eliminar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
