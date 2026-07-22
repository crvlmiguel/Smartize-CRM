import { useEffect, useRef, useState } from "react";
import {
  Bold, Italic, Underline, Link2, Image as ImageIcon,
  AlignLeft, AlignCenter, AlignRight, AlignJustify, List, ListOrdered,
  Code2, Eye, PenTool, Type, Highlighter, Variable,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const VARIABLES = [
  "first_name", "last_name", "full_name", "company", "position",
  "email", "phone", "city", "country", "website", "today",
];
const FONTS = ["Arial", "Helvetica", "Georgia", "Times New Roman", "Verdana", "Tahoma", "Courier New"];
const SIZES = [
  { label: "Pequeno", v: "2" }, { label: "Normal", v: "3" },
  { label: "Médio", v: "4" }, { label: "Grande", v: "5" }, { label: "Enorme", v: "6" },
];

export function RichTextEditor({ value, onChange, minHeight = "260px" }) {
  const [mode, setMode] = useState("visual");
  const editorRef = useRef(null);

  const hydrate = (node) => {
    editorRef.current = node;
    if (node && node.innerHTML !== (value || "")) node.innerHTML = value || "";
  };

  useEffect(() => {
    if (mode === "visual" && editorRef.current && editorRef.current.innerHTML !== (value || "")) {
      editorRef.current.innerHTML = value || "";
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const exec = (command, val = null) => {
    editorRef.current?.focus();
    document.execCommand(command, false, val);
    if (editorRef.current) onChange(editorRef.current.innerHTML);
  };
  const insertHtml = (snippet) => {
    editorRef.current?.focus();
    document.execCommand("insertHTML", false, snippet);
    if (editorRef.current) onChange(editorRef.current.innerHTML);
  };
  const addLink = () => { const url = prompt("URL do link:", "https://"); if (url) exec("createLink", url); };
  const addImage = () => { const url = prompt("URL da imagem (alojada externamente):", "https://"); if (url) insertHtml(`<img src="${url}" style="max-width:100%" alt="" />`); };

  const Btn = ({ onClick, title, children, testid }) => (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={onClick} title={title}
      data-testid={testid} className="h-8 w-8 flex items-center justify-center rounded hover:bg-secondary text-foreground">
      {children}
    </button>
  );
  const Sep = () => <div className="w-px h-5 bg-border mx-1" />;

  return (
    <div>
      <Tabs value={mode} onValueChange={setMode}>
        <TabsList>
          <TabsTrigger value="visual" data-testid="rte-tab-visual"><PenTool size={14} className="mr-1.5" /> Visual</TabsTrigger>
          <TabsTrigger value="code" data-testid="rte-tab-code"><Code2 size={14} className="mr-1.5" /> Código HTML</TabsTrigger>
          <TabsTrigger value="preview" data-testid="rte-tab-preview"><Eye size={14} className="mr-1.5" /> Pré-visualizar</TabsTrigger>
        </TabsList>

        <TabsContent value="visual" className="mt-3">
          <div className="flex flex-wrap items-center gap-0.5 border border-border rounded-t-md p-1 bg-secondary/50">
            <Btn onClick={() => exec("bold")} title="Negrito" testid="rte-bold"><Bold size={15} /></Btn>
            <Btn onClick={() => exec("italic")} title="Itálico" testid="rte-italic"><Italic size={15} /></Btn>
            <Btn onClick={() => exec("underline")} title="Sublinhado" testid="rte-underline"><Underline size={15} /></Btn>
            <Sep />
            <select onChange={(e) => { if (e.target.value) exec("fontName", e.target.value); }} data-testid="rte-font" className="h-8 text-xs border border-border rounded px-1 bg-white" title="Tipo de letra">
              <option value="">Tipo de letra</option>
              {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <select onChange={(e) => { if (e.target.value) exec("fontSize", e.target.value); }} data-testid="rte-size" className="h-8 text-xs border border-border rounded px-1 bg-white" title="Tamanho">
              <option value="">Tamanho</option>
              {SIZES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
            </select>
            <Sep />
            <label className="h-8 px-1 flex items-center rounded hover:bg-secondary cursor-pointer" title="Cor do texto" data-testid="rte-color-wrap">
              <Type size={13} className="mr-0.5" />
              <input type="color" data-testid="rte-color" onChange={(e) => exec("foreColor", e.target.value)} className="w-4 h-4 border-0 bg-transparent cursor-pointer" />
            </label>
            <label className="h-8 px-1 flex items-center rounded hover:bg-secondary cursor-pointer" title="Cor de destaque" data-testid="rte-highlight-wrap">
              <Highlighter size={13} className="mr-0.5" />
              <input type="color" data-testid="rte-highlight" onChange={(e) => exec("hiliteColor", e.target.value) || exec("backColor", e.target.value)} className="w-4 h-4 border-0 bg-transparent cursor-pointer" />
            </label>
            <Sep />
            <Btn onClick={() => exec("insertUnorderedList")} title="Lista com pontos" testid="rte-ul"><List size={15} /></Btn>
            <Btn onClick={() => exec("insertOrderedList")} title="Lista numerada" testid="rte-ol"><ListOrdered size={15} /></Btn>
            <Sep />
            <Btn onClick={() => exec("justifyLeft")} title="Esquerda" testid="rte-left"><AlignLeft size={15} /></Btn>
            <Btn onClick={() => exec("justifyCenter")} title="Centro" testid="rte-center"><AlignCenter size={15} /></Btn>
            <Btn onClick={() => exec("justifyRight")} title="Direita" testid="rte-right"><AlignRight size={15} /></Btn>
            <Btn onClick={() => exec("justifyFull")} title="Justificado" testid="rte-justify"><AlignJustify size={15} /></Btn>
            <Sep />
            <Btn onClick={addLink} title="Inserir link" testid="rte-link"><Link2 size={15} /></Btn>
            <Btn onClick={addImage} title="Inserir imagem" testid="rte-image"><ImageIcon size={15} /></Btn>
            <select onChange={(e) => { if (e.target.value) { insertHtml(`{${e.target.value}}`); e.target.value = ""; } }} data-testid="rte-variable" className="h-8 text-xs border border-border rounded px-1 bg-white" title="Inserir variável">
              <option value="">Variável</option>
              {VARIABLES.map((v) => <option key={v} value={v}>{`{${v}}`}</option>)}
            </select>
          </div>
          <div
            ref={hydrate}
            contentEditable
            data-testid="rte-editor"
            onInput={() => onChange(editorRef.current.innerHTML)}
            style={{ minHeight }}
            className="border border-t-0 border-border rounded-b-md p-4 bg-white focus:outline-none focus:ring-1 focus:ring-primary overflow-auto text-sm"
            suppressContentEditableWarning
          />
          <p className="text-[11px] text-muted-foreground mt-1.5 flex items-center gap-1"><Variable size={12} /> A assinatura da conta de email é adicionada automaticamente no envio.</p>
        </TabsContent>

        <TabsContent value="code" className="mt-3">
          <textarea
            value={value || ""}
            data-testid="rte-html-input"
            onChange={(e) => onChange(e.target.value)}
            rows={14}
            spellCheck={false}
            style={{ minHeight }}
            className="w-full border border-border rounded-md p-3 font-mono text-xs bg-white focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </TabsContent>

        <TabsContent value="preview" className="mt-3">
          <div className="border border-border rounded-md p-4 bg-white overflow-auto text-sm" style={{ minHeight }} data-testid="rte-preview" dangerouslySetInnerHTML={{ __html: value || "<span class='text-muted-foreground'>Sem conteúdo</span>" }} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
