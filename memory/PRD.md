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
- **P2**: Deteção automática de respostas (IMAP) para parar sequências; verificação externa de emails.
- **P2**: Campos personalizados na UI de contactos; slugs ASCII nos nav-testids.
- **P3 (futuro)**: CRM, IA, sequências multi-step, SMS/WhatsApp.
