# Smartize Outreach — PRD

## Problema Original
Plataforma profissional de Email Outreach (tipo Instantly/Smartlead/Lemlist) para a Smartize. MVP focado em criar campanhas outbound simples, organizadas e com elevada entregabilidade. UI em Português. Preparada para crescer (CRM, IA, SMS, WhatsApp) sem reescrever.

## Arquitetura
- **Backend**: FastAPI modular — `server.py` (app + startup + APScheduler), `auth.py` (JWT Bearer, seed users), `api.py` (CRUD + import + preview + smtp test + campanhas + dashboard + settings + tracking), `worker.py` (fila de envio com APScheduler, atrasos aleatórios, horário comercial, limite diário, deteção de bounce), `email_service.py` (substituição de variáveis, rewrite de links, pixel de abertura, envio via aiosmtplib), `core.py` (Mongo, encriptação Fernet, PyObjectId/BaseDocument), `models.py`.
- **Frontend**: React (CRA/craco), Tailwind, Shadcn UI, recharts, Chivo/IBM Plex Sans/JetBrains Mono. Auth via token JWT em localStorage. Layout com sidebar PT.
- **DB**: MongoDB (users, contacts, groups, templates, smtp_accounts, campaigns, email_jobs, settings).

## Personas
- Equipa comercial/marketing Smartize a gerir campanhas de email outbound.

## Requisitos Core (estáticos)
Fluxo: SMTP → Contactos → Grupos → Template → Campanha → Enviar/Agendar → Acompanhar. Deliverability: fila, atrasos aleatórios, limite diário por SMTP, horário comercial/dias úteis, validação e dedupe de emails, gestão de bounces, tracking discreto, cabeçalhos RFC, ajuda SPF/DKIM/DMARC.

## Implementado (2026-07-22)
- Auth JWT email/password; 2 admins seeded (miguel.carvalho@ / carlos.miguel@ smartize.pt, pass 100%Smartize).
- Dashboard: KPIs + evolução diária (14 dias) + últimas campanhas.
- Contactos: CRUD, pesquisa, filtros (grupo/estado), importar CSV/Excel com dedupe e validação.
- Grupos: CRUD com contagem de contactos.
- Templates: editor HTML/Texto, inserir variáveis dinâmicas, preview, duplicar, eliminar.
- Contas de Email (em Configurações → Contas de Email): tipos SMTP Personalizado e Google Workspace/Gmail; testar ligação; enviar email de teste; password/IMAP encriptadas (Fernet); limite diário; conta predefinida; desligar; assinatura HTML por conta (editor WYSIWYG + código + preview); Reply-To; IMAP opcional; preset Hostinger; Google pré-configura smtp.gmail.com (OAuth "em breve", usa App Password).
- Campanhas: wizard 3 passos, iniciar/agendar/duplicar/cancelar/arquivar/eliminar; usa conta predefinida quando não indicada.
- Envio real via SMTP com fila (APScheduler, atrasos aleatórios, horário comercial, limite diário, bounce auto); assinatura da conta anexada automaticamente.
- Tracking: pixel de abertura + redirect de cliques (verificado E2E).
- Estatísticas por campanha (taxas) + detalhe com destinatários e marcar "respondeu".
- Configurações com separadores Geral (empresa, upload de logótipo base64, idioma, timezone, rodapé) e Contas de Email.
- Identidade visual Smartize: logótipo (upload dinâmico via /api/public/branding) em Login, sidebar, rodapé, loading e 404; favicon; logo nos emails de teste.
- Testado: iteração 1 (31/31), iteração 2 (38/38), iteração 3 (46/46) backend + fluxos frontend verdes.

## Removido
- Módulo Deliverability (menu, página, rotas) — removido da UI.
- Menu SMTP autónomo (movido para Configurações → Contas de Email; /smtp e /deliverability redirecionam para /configuracoes).
- "Assinatura padrão" das Configurações Gerais (assinaturas agora só por conta).

## Backlog / Próximos passos
- **P1**: Paginação em /contacts; validar 404 em cancel/archive/delete/reply de campanha inexistente; agregação para dashboard daily (perf).
- **P1**: Rotação automática entre várias contas SMTP na mesma campanha.
- **P2**: Campos personalizados na UI de contactos; slugs ASCII nos nav-testids.
- **P3 (futuro)**: IA, SMS/WhatsApp.

## Iteração 16 — Assinatura HTML enviada como HTML real (fix definitivo) (2026-08-10)
- **Problema**: como os templates são texto simples, o email ia só como text/plain e a assinatura HTML era achatada em texto (colada).
- **Fix**: os emails passam a ser SEMPRE `multipart/alternative` — parte `text/plain` (corpo + assinatura em texto, fallback) **e** parte `text/html` (corpo natural via `text_to_html` + **assinatura HTML preservada** por `compose_email_html`, sem `html_to_text` no caminho HTML). Novo `text_to_html` (escape + `<br>`). Worker (_send_job e _send_sequence_step) e `/api/templates/preview` alinhados; preview no frontend voltou a renderizar `email_html` num iframe.
- **Verificação do MIME (requisito #8)**: inspecionado o objeto real — `multipart/alternative` com 2 partes; `text/html` mantém `<table>/<img> logo/<a> links/cores inline`; `text/plain` com assinatura uma info por linha e zero `<`.
- **Testado**: iteração 16 100% (9 testes novos + 218 regressão; testes antigos que codificavam o comportamento anterior — email_html vazio — foram atualizados à nova spec, só código de teste).
- **Notas cosméticas (backlog)**: altura fixa do iframe de preview deixa espaço branco em emails curtos; na assinatura guardada pelo utilizador o link do website envolve só 'www.smartize.' e o email não é link (vem do editor, não do envio — não alterado por indicação de não mexer no design).


- **Bug**: em emails text/plain a assinatura chegava toda colada numa linha porque `html_to_text` só quebrava em `<br>`/`</p>`.
- **Fix conversor**: `html_to_text` reescrito — trata `</p></div></tr></td></th></table></h1-6></li></ul></ol>` e `<br>` como quebras de linha, remove `<script>/<style>/<head>`, decodifica entidades e colapsa linhas vazias → cada informação (Nome/Cargo/Telefone/Email/Website) numa linha.
- **Dois formatos de assinatura**: novo campo `signature_text` por conta SMTP (models + endpoints). Envio: HTML usa `signature_html`; text/plain usa `signature_text` (própria) ou, se vazia, gera limpa a partir do HTML. UI: campo "Assinatura em texto simples" + botão "Gerar a partir do HTML" (`htmlToPlainSig` espelha o backend).
- **Testado**: iteração 15 backend 100% (14 novos + 206 regressão), frontend 100% (uma info por linha, sem tags). Pendências opcionais: preview de templates HTML não anexa a assinatura de texto (cosmético; envio correto); DialogDescription a11y no dialog de conta.


- **Editor de templates responsivo**: modal com grid `auto/1fr/auto` + `max-h-[90vh]`, scroll interno só no conteúdo, botões (Preview/Cancelar/Guardar) sempre acessíveis (testado 768/700/600px). (iter11 100%)
- **Email com aspeto natural**: `wrap_email_html` deixou de criar caixa/cartão (sem tabela container, fundo cinzento ou borda); assinatura separada por espaçamento. (iter12)
- **Templates = apenas Plain Text**: removido editor visual/HTML; editor agora é Nome + Assunto + Textarea de texto simples + Inserir variável ({{var}}) + Preview + Guardar. Envio efetivo em `text/plain` (sem HTML) quando não há conteúdo HTML visível (`html_has_visible_content`). Variáveis {{first_name}}/{{company}}/{{saudacao}} funcionam. (iter13 backend 100%)
- **Migração de templates legados**: `openEdit` converte `content_html`→texto (prefere o texto mais rico) para não perder o corpo ao guardar; ao guardar, `content_html` fica sempre "". (iter14 HIGH corrigido)
- **a11y + branding**: DialogDescription nos diálogos de template/preview; nome da empresa reposto para "Smartize" (dados de teste antigos limpos).
- **Trade-offs conhecidos (backlog)**: emails plain text não têm tracking de abertura/cliques (inerente a text/plain); assinaturas só-imagem não aparecem em modo texto → falta um campo de assinatura em texto por conta SMTP.


- **Assinatura/logótipo**: upload direto de imagem (POST /api/uploads/image, servida em /api/public/image/{id}), inserção email-safe com largura fixa + `max-width:100%`; removido placeholder externo via.placeholder.com.
- **HTML email-safe**: `compose_email_html`/`wrap_email_html` (container de tabela 600px, CSS inline) aplicado no envio (worker) e test-send; `_ensure_img_email_safe` normaliza `<img>` (remove border-* injetado, adiciona border:0/max-width/height:auto). Plain Text intacto.
- **Preview realista**: /api/templates/preview devolve `email_html` (documento final); Templates mostra iframe com toggle Desktop 640px / Mobile 380px.
- **Importação de contactos**: painel de ajuda + exemplo CSV; POST /api/contacts/import/preview (contagens encontrados/válidos/inválidos/duplicados/incompletos, mapeamento auto, colunas desconhecidas, sample); import em 2 passos com mapeamento confirmável (Form `mapping` JSON) e pré-visualização das primeiras linhas.
- **Campo Saudação (novo)**: coluna `saudacao` na importação (aliases saudacao/saudação/greeting/salutation/tratamento), guardada verbatim; variável `{{saudacao}}`/`{saudacao}` nos templates/assinatura; campo no formulário e coluna na tabela de contactos.
- **Correções**: contador "incompletos" (pd.isna); warning React `value` null nas contas de email (openEdit normaliza null→"").
- **Testado**: iter8 20/21→corrigido, iter9 22/22 (100%), iter10 frontend 100%. SMTP do preview é fictício (envio real não validado).
- **Backlog não bloqueante**: a11y DialogDescription (contact/smtp/template dialogs); escala do preview Mobile; import com insert_many + índice único; lockout de login + CORS explícito.

## Pendente — Ligação automática do Gmail (OAuth 2.0 / Gmail API)
- **PAUSADO — a aguardar credenciais do utilizador**: GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET (Google Cloud, Gmail API + OAuth consent). Redirect URIs a registar: `https://outreach.smartize.pt/api/oauth/gmail/callback` e o do preview. Objetivo: botão "Ligar Gmail" (OAuth, sem App Password) para enviar via Gmail API, mantendo contas SMTP a funcionar em paralelo.

## Iteração 7 — Pipelines editáveis (Pipedrive-like) + Criação de negócios (2026-07-28)


- **Pipelines totalmente configuráveis** (`/negocios` → "Gerir pipelines", `PipelineManager.jsx`): criar/renomear/eliminar pipelines (ilimitados), definir padrão (`is_default`), editor de etapas com nome, **cor** (color picker), **probabilidade (%)**, **tipo** (aberta/ganho/perdido), **reordenar por drag&drop**, inserir no topo/entre/no fim e eliminar. Backend `Stage` com `color`+`probability` (Field ge=0/le=100, type Literal); `list_pipelines` enriquece etapas legadas; endpoints CRUD + `/pipelines/{id}/set-default`; delete promove novo padrão.
- **Criação de negócios (2 formas)**: (1) a partir de um Contacto — botão "+ Criar Negócio" navega para /negocios e abre o `deal-dialog` **pré-preenchido** (nome, empresa, email, telefone, cargo, website; histórico de emails + campanha de origem copiados no backend ao guardar); (2) diretamente em Negócios com Pipeline + Etapa inicial selecionáveis. Deal herda a probabilidade da etapa; cards do Kanban mostram contacto + probabilidade; colunas com ponto colorido da etapa.
- **Correções (test iter7)**: PUT pipeline inexistente → 404; validação de probabilidade (422 se >100); remover etapa **realoca deals órfãos** para a 1ª etapa; `move_deal` atualiza probabilidade e limpa `lost_reason`, guarda contra pipeline inexistente; `create_pipeline` usa deepcopy + `is_default:false`; PipelineManager oculta delete com 1 pipeline e avisa alterações não guardadas ao trocar de pipeline.
- **Testado**: frontend 100% dos fluxos (iteration_7.json); backend 20/22 (as 2 falhas eram gaps de validação, agora corrigidos e verificados via curl: 404/422/realocação/herança de probabilidade).
- **Backlog design (não crítico)**: usar Calendar shadcn em vez de input date nativo; extrair deal-dialog para componente; lockout de brute force no login (fora de âmbito, requer integração de auth).

## Iteração 6 — CRM + Sequências (2026-07-28)
- **Campanhas com Sequências**: wizard passo 1 com interruptor "Ativar sequência de emails"; construtor de passos (email inicial + N follow-ups) com template, atraso (dias/horas) e tipo de envio (novo email / responder na mesma thread). Backend `is_sequence`+`steps` (SequenceStep). Worker `process_sequences`/`build_enrollments` envia por contacto e para automaticamente quando o contacto responde (respondido/bounce/descadastrado).
- **CRM de Negócios (Kanban)** em `/negocios`: pipelines com etapas pt-PT, deals com valor/probabilidade/data de fecho, drag&drop entre etapas, histórico, converter contacto → negócio (botão nos Contactos, endpoint `/api/contacts/{id}/convert`).
- **Automações do CRM**: separador Automações (QUANDO evento → EXECUTAR ação por etapa): add_tag, create_task, change_stage, create_project, send_email (com atraso via `automation_jobs`).
- **Correções (test iter6)**: DELETE campanha remove `campaign_contacts`; worker marca enrollments órfãos como `stopped`; `_campaign_stats` conta enrollments para campanhas de sequência (fim do 0/0); página de detalhe mostra "Progresso da sequência" (passo/estado/próximo envio/motivo de paragem); PUT deal/automação inexistente → 404; `move_deal` limpa `lost_reason` em etapas won/open; confirmação ao eliminar negócio; conta SMTP default pré-selecionada no wizard.
- **Testado**: frontend 100% dos fluxos (iteration_6.json); backend 19/20 (1 falha = colisão de dados no ficheiro de teste, não código) + delete-enrollments verificado via API; regressão 46/46.

