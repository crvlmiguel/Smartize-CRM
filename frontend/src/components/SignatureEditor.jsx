import { useEffect, useRef, useState } from "react";
import {
  Bold, Italic, Underline, Link2, Image as ImageIcon,
  AlignLeft, AlignCenter, AlignRight, Code2, Eye, PenTool,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const VARIABLES = [
  "first_name", "last_name", "full_name", "company", "position",
  "email", "phone", "city", "country", "website", "today",
];
const FONTS = ["Arial", "Helvetica", "Georgia", "Times New Roman", "Verdana", "Tahoma", "Courier New"];

export const SIGNATURE_TEMPLATE = `<table cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;color:#0A0A0A">
  <tr>
    <td style="padding-right:16px;border-right:2px solid #0055FF">
      <img src="https://via.placeholder.com/64" width="64" height="64" style="border-radius:6px" alt="logo" />
    </td>
    <td style="padding-left:16px">
      <div style="font-weight:bold;font-size:16px">{full_name}</div>
      <div style="color:#52525B;font-size:13px">{position} · {company}</div>
      <div style="margin-top:6px;font-size:12px">
        <a href="mailto:{email}" style="color:#0055FF;text-decoration:none">{email}</a> ·
        <span>{phone}</span><br/>
        <a href="https://{website}" style="color:#0055FF;text-decoration:none">{website}</a>
      </div>
    </td>
  </tr>
</table>`;

export function SignatureEditor({ value, onChange }) {
  const [mode, setMode] = useState("visual");
  const editorRef = useRef(null);

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

  const ToolBtn = ({ onClick, title, children, testid }) => (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={onClick} title={title}
      data-testid={testid} className="h-8 w-8 flex items-center justify-center rounded hover:bg-secondary text-foreground">
      {children}
    </button>
  );

  return (
    <div className="grid lg:grid-cols-2 gap-5">
      <div>
        <Tabs value={mode} onValueChange={setMode}>
          <TabsList>
            <TabsTrigger value="visual" data-testid="sig-tab-visual"><PenTool size={14} className="mr-1.5" /> Visual</TabsTrigger>
            <TabsTrigger value="code" data-testid="sig-tab-code"><Code2 size={14} className="mr-1.5" /> Código HTML</TabsTrigger>
          </TabsList>
          <TabsContent value="visual" className="mt-3">
            <div className="flex flex-wrap items-center gap-0.5 border border-border rounded-t-md p-1 bg-secondary/50">
              <ToolBtn onClick={() => exec("bold")} title="Negrito" testid="sig-bold"><Bold size={15} /></ToolBtn>
              <ToolBtn onClick={() => exec("italic")} title="Itálico" testid="sig-italic"><Italic size={15} /></ToolBtn>
              <ToolBtn onClick={() => exec("underline")} title="Sublinhado" testid="sig-underline"><Underline size={15} /></ToolBtn>
              <div className="w-px h-5 bg-border mx-1" />
              <ToolBtn onClick={addLink} title="Link" testid="sig-link"><Link2 size={15} /></ToolBtn>
              <ToolBtn onClick={addImage} title="Imagem" testid="sig-image"><ImageIcon size={15} /></ToolBtn>
              <div className="w-px h-5 bg-border mx-1" />
              <ToolBtn onClick={() => exec("justifyLeft")} title="Esquerda" testid="sig-left"><AlignLeft size={15} /></ToolBtn>
              <ToolBtn onClick={() => exec("justifyCenter")} title="Centro" testid="sig-center"><AlignCenter size={15} /></ToolBtn>
              <ToolBtn onClick={() => exec("justifyRight")} title="Direita" testid="sig-right"><AlignRight size={15} /></ToolBtn>
              <div className="w-px h-5 bg-border mx-1" />
              <label className="h-8 px-1 flex items-center rounded hover:bg-secondary cursor-pointer" title="Cor do texto">
                <input type="color" data-testid="sig-color" onChange={(e) => exec("foreColor", e.target.value)} className="w-5 h-5 border-0 bg-transparent cursor-pointer" />
              </label>
              <select onChange={(e) => exec("fontName", e.target.value)} data-testid="sig-font" className="h-8 text-xs border border-border rounded px-1 bg-white">
                <option value="">Tipografia</option>
                {FONTS.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              <select onChange={(e) => { if (e.target.value) { insertHtml(`{${e.target.value}}`); e.target.value = ""; } }} data-testid="sig-variable" className="h-8 text-xs border border-border rounded px-1 bg-white">
                <option value="">Inserir variável</option>
                {VARIABLES.map((v) => <option key={v} value={v}>{`{${v}}`}</option>)}
              </select>
            </div>
            <div
              ref={editorRef}
              contentEditable
              data-testid="signature-visual-editor"
              onInput={() => onChange(editorRef.current.innerHTML)}
              className="border border-t-0 border-border rounded-b-md p-4 min-h-[200px] bg-white focus:outline-none focus:ring-1 focus:ring-primary overflow-auto"
              suppressContentEditableWarning
            />
          </TabsContent>
          <TabsContent value="code" className="mt-3">
            <textarea
              value={value || ""}
              data-testid="signature-html-input"
              onChange={(e) => onChange(e.target.value)}
              rows={12}
              spellCheck={false}
              className="w-full border border-border rounded-md p-3 font-mono text-xs bg-white focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </TabsContent>
        </Tabs>
      </div>
      <div>
        <div className="flex items-center gap-1.5 mb-3 text-sm font-medium"><Eye size={15} className="text-primary" /> Pré-visualização em tempo real</div>
        <div className="border border-border rounded-md p-4 bg-white min-h-[200px] overflow-auto" data-testid="signature-preview" dangerouslySetInnerHTML={{ __html: value || "" }} />
        <p className="text-xs text-muted-foreground mt-2">Adicionada automaticamente ao fim de cada email desta conta. Use imagens externas (URL) para compatibilidade com Gmail, Outlook e Apple Mail.</p>
      </div>
    </div>
  );
}
