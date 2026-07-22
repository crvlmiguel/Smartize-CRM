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
- SMTP: CRUD, testar ligação, password encriptada (Fernet), limite diário.
- Campanhas: wizard 3 passos (config/velocidade/envio), iniciar/agendar/duplicar/cancelar/arquivar/eliminar.
- Envio real via SMTP com fila (APScheduler, atrasos aleatórios, horário comercial, limite diário, bounce auto).
- Tracking: pixel de abertura + redirect de cliques (verificado E2E).
- Estatísticas por campanha (taxas) + detalhe com destinatários e marcar "respondeu".
- Configurações (empresa, logo, idioma, timezone, assinatura, rodapé). Deliverability (SPF/DKIM/DMARC + boas práticas).
- Testado: 31/31 testes backend, fluxos frontend core OK.

## Backlog / Próximos passos
- **P1**: Paginação em /contacts; validar 404 em cancel/archive/delete/reply de campanha inexistente; agregação para dashboard daily (perf).
- **P1**: Rotação automática entre várias contas SMTP na mesma campanha.
- **P2**: Deteção automática de respostas (IMAP) para parar sequências; verificação externa de emails.
- **P2**: Campos personalizados na UI de contactos; slugs ASCII nos nav-testids.
- **P3 (futuro)**: CRM, IA, sequências multi-step, SMS/WhatsApp.
