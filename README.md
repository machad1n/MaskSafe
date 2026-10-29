# MaskSafe

Projeto acadêmico do curso de Ciência da Computação do CEUB (Centro Universitário de Brasília), disciplina **Projeto Integrador III**.

O MaskSafe dá continuidade ao **SafeMask**, desenvolvido no semestre anterior. Este repositório parte do código do SafeMask e segue com ajustes, testes e novas funcionalidades. Por isso, alguns nomes internos do código ainda usam `safemask`.

**Proteção de dados sensíveis com IA:** o sistema detecta e censura automaticamente informações confidenciais em documentos PDF, em apoio à conformidade com a LGPD.

## 🔗 Acesso rápido

| Serviço | URL |
|---|---|
| 🌐 Frontend (Vercel) | https://masksafe.vercel.app |
| 🔙 Backend (Render) | https://masksafe-backend.onrender.com |
| 📄 API Docs (Swagger) | https://masksafe-backend.onrender.com/docs |
| 💾 Banco de dados | PostgreSQL serverless (Neon) |

> O backend roda no plano gratuito do Render e "dorme" quando fica ocioso. A primeira requisição pode levar mais de 60 s. Antes de uma demonstração, rode `scripts/warmup.sh`.

## 📖 Índice

- [Visão geral](#-visão-geral)
- [5W do projeto](#-5w-do-projeto)
- [Stack](#️-stack)
- [Estrutura do projeto](#-estrutura-do-projeto)
- [Instalação local](#-instalação-local)
- [Variáveis de ambiente](#-variáveis-de-ambiente)
- [Testes](#-testes)
- [API](#-api)
- [Deploy](#-deploy)
- [Segurança](#-segurança)
- [Conformidade LGPD](#-conformidade-lgpd)
- [Equipe](#-equipe)

## 🎯 Visão geral

O MaskSafe é uma plataforma full-stack para proteção de dados sensíveis:

- **Usuários e organizações:** cadastro e login imediatos com JWT (sem confirmação de email), recuperação de senha por e-mail e dados isolados por organização.
- **Equipes:** criação de equipes, membros e cargos (líder, supervisor e membro).
- **Upload de documentos:** PDFs de até 20 MB, com OCR (Tesseract) para páginas sem camada de texto.
- **Detecção de dados sensíveis:** expressões regulares (CPF, CNPJ, datas etc.) e, quando os pesos estão disponíveis, um modelo NER (rede neural).
- **Censura e descensura:** aplicação de tarjas no PDF, descensura parcial e compartilhamento entre equipes.
- **Auditoria:** registro das ações sobre documentos.

## 📌 5W do projeto

| 5W | Resposta |
|---|---|
| **What (o quê?)** | Plataforma web que detecta e censura automaticamente dados sensíveis em documentos usando IA. |
| **Why (por quê?)** | Reduzir o risco de vazamento de informações confidenciais, proteger dados pessoais e apoiar a conformidade com a LGPD. |
| **Who (quem?)** | Usuários, equipes e organizações que armazenam, analisam ou compartilham documentos com informações sensíveis. |
| **Where (onde?)** | Na web: frontend na Vercel, backend FastAPI no Render e PostgreSQL serverless no Neon. |
| **When (quando?)** | No upload, na análise, no armazenamento e no compartilhamento de documentos, especialmente antes de disponibilizá-los a terceiros. |

## 🛠️ Stack

**Backend**

- Python 3.11 (o CI também testa em 3.12)
- FastAPI 0.115 e Uvicorn
- SQLAlchemy 2.0 com PostgreSQL (psycopg2)
- Pydantic 2
- JWT (python-jose) e bcrypt (passlib)
- pdfplumber, pytesseract e Pillow para leitura de PDF e OCR
- torch e transformers para o NER (opcional, em `requirements-ia.txt`)
- Brevo (sib-api-v3-sdk) para envio de e-mails

**Frontend**

- HTML5, CSS3 e JavaScript puro, sem build

**Infra e qualidade**

- Vercel (frontend), Render (backend) e Neon (banco)
- GitHub Actions: pytest e ruff a cada push ou PR
- Deploy automático na Vercel e no Render a cada push na `main`

## 📁 Estrutura do projeto

```
masksafe/
├── index.html                 # Landing page (raiz do site na Vercel)
├── render.yaml                # Blueprint do backend no Render
├── vercel.json                # Configuração do site estático
├── .github/workflows/
│   └── ci-backend.yml         # pytest + ruff
├── backend/
│   ├── Dockerfile             # Imagem do backend (Render)
│   ├── requirements.txt       # Dependências de produção (sem IA)
│   ├── requirements-ia.txt    # torch + transformers (NER local)
│   ├── requirements-dev.txt   # Dependências de teste e lint
│   ├── pytest.ini
│   ├── ruff.toml
│   ├── app/
│   │   ├── main.py            # App FastAPI, CORS, criação do schema e seed de cargos
│   │   ├── database.py
│   │   ├── core/              # auth, segurança, config, auditoria, tenancy, uploads, e-mail
│   │   ├── models/            # usuario, organizacao, equipe, cargo, documentos, dado_sensivel, log_auditoria
│   │   ├── routes/            # auth, dashboard, equipes, documentos
│   │   └── schemas/
│   ├── scanner/
│   │   ├── scanner.py         # Detecção: regex + NER (com fallback para regex)
│   │   ├── patterns.py        # Padrões regex
│   │   ├── redaction.py       # Aplicação das tarjas no PDF
│   │   ├── coordenadas.py
│   │   └── safemask-ner/      # Config e tokenizer do modelo (pesos fora do git)
│   └── tests/                 # Testes pytest
├── frontend/
│   ├── css/
│   ├── html/                  # auth/, documentos/, equipes/, dashboard.html
│   └── js/                    # config.js define a URL da API
├── scripts/
│   ├── e2e.py                 # Smoke test ponta a ponta da API
│   ├── gerar_pdf_exemplo.py
│   └── warmup.sh              # Aquece o backend no Render
└── documentation/             # Documentos do PI, checklists de sprint e Daily Scrum
```

## 🚀 Instalação local

**Pré-requisitos:** Python 3.11+, um banco PostgreSQL (local ou Neon) e, para o OCR, o Tesseract com o idioma português (`tesseract-ocr` e `tesseract-ocr-por`).

### 1. Clone o repositório

```bash
git clone https://github.com/VictorOleskovicz/masksafe.git
cd masksafe
```

### 2. Banco de dados

Use o Neon (crie um projeto em https://neon.tech e copie a connection string) ou suba um PostgreSQL local com Docker:

```bash
docker run --name masksafe-postgres \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=masksafe_db \
  -p 5432:5432 -d postgres:15
```

As tabelas são criadas automaticamente quando a API sobe.

### 3. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
# Opcional, só para rodar o NER localmente:
pip install -r requirements-ia.txt
```

Crie `backend/.env` com pelo menos:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/masksafe_db
SECRET_KEY=gere-uma-chave-aleatoria-forte
BREVO_API_KEY=chave-da-api-brevo
SMTP_FROM=email-remetente-verificado-na-brevo
SMTP_FROM_NAME=SafeMask
```

Para gerar a `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Suba a API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Sobre a IA:** o scanner carrega o NER automaticamente quando existe `backend/scanner/safemask-ner/model.safetensors` e o `requirements-ia.txt` está instalado. Sem os pesos, ele usa só regex e registra um aviso no boot, que é o mesmo comportamento da produção (o plano gratuito do Render tem 1 GB de disco). Os pesos ficam fora do git por causa do tamanho.

### 4. Frontend

Sirva a **raiz do repositório**, não a pasta `frontend/`, para reproduzir o deploy da Vercel:

```bash
# Na raiz do repositório
python -m http.server 8080
```

- Landing: http://localhost:8080
- Login: http://localhost:8080/frontend/html/auth/login.html

O `frontend/js/config.js` aponta para `http://localhost:8000` quando o host é `localhost`/`127.0.0.1` e para `https://masksafe-backend.onrender.com` nos demais casos. Em desenvolvimento, o backend aceita qualquer porta de localhost via CORS.

## 🔧 Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | Sim | Connection string do PostgreSQL |
| `SECRET_KEY` | Sim | Chave de assinatura dos JWT |
| `ENVIRONMENT` | Não | `development` (padrão) ou `production`. Em produção, as origens de localhost saem do CORS |
| `FRONTEND_ORIGINS` | Não | Origens extras para o CORS, separadas por vírgula |
| `FRONTEND_URL` | Não | URL usada nos e-mails de recuperação e confirmação de contas legadas (padrão: `https://masksafe.vercel.app`) |
| `BREVO_API_KEY` | Necessária para envio de email | Chave privada da API transacional da Brevo (não é SMTP key) |
| `SMTP_FROM` | Necessária para envio de email | Endereço remetente verificado na Brevo (não é servidor/login SMTP) |
| `SMTP_FROM_NAME`, `SUPPORT_EMAIL` | Não | Nome do remetente e endereço de suporte |
| `MAX_UPLOAD_BYTES` | Não | Tamanho máximo do upload (padrão: 20 MB) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Não | Validade do token de acesso (padrão: 120) |
| `RESET_TOKEN_EXPIRE_MINUTES` | Não | Validade do token de redefinição de senha (padrão: 30) |
| `TRUSTED_PROXY_IPS` | Não | IPs/CIDRs separados por vírgula dos proxies que podem fornecer `X-Forwarded-For`; sem configuração, usa o IP da conexão direta |
| `SLOW_QUERY_MS` | Não | Limite para registrar consultas lentas no log (padrão: 100) |

## 🧪 Testes

```bash
cd backend
pip install -r requirements-dev.txt
# Os testes precisam de DATABASE_URL e SECRET_KEY (veja .github/workflows/ci-backend.yml)
python -m pytest -q
ruff check app scanner tests
```

Smoke test ponta a ponta contra um backend rodando:

```bash
python scripts/e2e.py --base-url http://localhost:8000
```

## 📡 API

A documentação interativa completa fica em `/docs`. Resumo das rotas:

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Status da API |
| POST | `/auth/cadastro` | Cria imediatamente usuário, organização e equipe; não exige confirmação por email |
| POST | `/auth/confirmar-email` | Compatibilidade para concluir solicitações de confirmação legadas |
| POST | `/auth/reenviar-confirmacao` | Compatibilidade para reenviar confirmação de solicitações legadas pendentes |
| POST | `/auth/login` | Login (retorna JWT) |
| GET | `/auth/me` | Dados do usuário autenticado |
| POST | `/auth/recuperar-senha` | Envia e-mail de recuperação |
| POST | `/auth/reset-senha` | Redefine a senha |
| GET | `/dashboard/overview` | Métricas do dashboard |
| GET | `/equipes/overview` | Equipes do usuário |
| GET | `/equipes/form-data` | Dados para o formulário de equipe |
| POST | `/equipes` | Cria equipe |
| GET | `/equipes/{team_id}` | Detalhe da equipe |
| PATCH | `/equipes/{team_id}` | Edita nome/descrição (liderança/supervisão na organização) |
| POST | `/equipes/{team_id}/membros` | Adiciona membro da organização à equipe |
| PATCH | `/equipes/{team_id}/membros/{user_team_id}` | Altera cargo respeitando hierarquia |
| DELETE | `/equipes/{team_id}/membros/{user_team_id}` | Remove vínculo, salvo quando há documentos vinculados |
| DELETE | `/equipes/{team_id}` | Exclui equipe sem documentos vinculados |
| POST | `/documentos/upload` | Upload e varredura de PDF |
| POST | `/documentos/salvar-censurado` | Salva a versão censurada |
| GET | `/documentos/censurados` | Lista documentos censurados |
| GET | `/documentos/censurados/{doc_id}` | Detalhe do documento censurado |
| GET | `/documentos/censurados/{doc_id}/arquivo` | Baixa o PDF censurado |
| GET | `/documentos/{doc_id}/original` | PDF original (conforme permissão) |
| GET | `/documentos/{doc_id}/parcial` | Descensura parcial |
| GET | `/documentos/listar/{team_id}` | Documentos de uma equipe |

## ☁️ Deploy

**Frontend (Vercel):** site estático com a raiz do repositório como diretório raiz, sem comando de build. O projeto está ligado ao repositório pela integração nativa da Vercel com o GitHub: cada push na `main` publica em produção e cada PR ganha uma URL de preview.

**Backend (Render):** criado a partir do Blueprint `render.yaml` (runtime Docker com `backend/Dockerfile`, que instala o Tesseract para o OCR). O Blueprint define `ENVIRONMENT`, `FRONTEND_URL` e `FRONTEND_ORIGINS`, gera a `SECRET_KEY` e solicita `DATABASE_URL`, `BREVO_API_KEY` e `SMTP_FROM` como valores privados no painel. `SMTP_FROM` deve ser um remetente verificado na Brevo. Toda alteração no `render.yaml` exige um "Sync" do Blueprint e o preenchimento dos novos segredos no Render.

**Banco (Neon):** PostgreSQL serverless. Basta apontar `DATABASE_URL` para ele.

## 🔐 Segurança

- Senhas com hash bcrypt
- JWT com expiração configurável (padrão de 120 min)
- CORS com lista explícita de origens em produção
- Headers de segurança HTTP em todas as respostas
- Isolamento de dados por organização (multi-tenant)
- Autorização por cargo na equipe
- Validação de upload (assinatura `%PDF-`, extensão e tamanho)
- Originais são mantidos no armazenamento da aplicação e **não são criptografados em repouso**; restrinja o acesso ao storage e configure retenção adequada
- Log de auditoria
- Proteção contra SQL Injection via ORM (SQLAlchemy)

## 📋 Conformidade LGPD

- **Confidencialidade:** dados sensíveis censurados antes do compartilhamento
- **Segurança:** controle de acesso por organização, equipe e cargo
- **Transparência e rastreabilidade:** log de auditoria das ações sobre documentos

## 👥 Equipe

- **Victor Oleskovicz**
- **Pedro**

Projeto baseado no SafeMask, desenvolvido no semestre anterior no CEUB.

---

Desenvolvido com 🔒 para proteção de dados.
#   M a s k S a f e  
 