# Configuração e deploy do MaskSafe

Este projeto usa uma arquitetura simples:

- **Frontend:** arquivos HTML/CSS/JavaScript estáticos publicados na Vercel.
- **Backend:** FastAPI em Docker publicado no Render.
- **Banco:** PostgreSQL gerenciado no Neon.
- **E-mail transacional:** Brevo, opcional para recuperação de senha.

## 1. Desenvolvimento local

1. Crie uma base PostgreSQL de desenvolvimento.
2. Copie `backend/.env.example` para `backend/.env` e preencha ao menos:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/masksafe_db
SECRET_KEY=uma-chave-aleatoria-com-pelo-menos-32-bytes
ENVIRONMENT=development
FRONTEND_URL=http://localhost:8080
FRONTEND_ORIGINS=http://localhost:8080
```

Gere uma chave segura com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

3. Instale as dependências e suba a API:

```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Em outro terminal, na raiz do projeto, sirva o frontend:

```bash
python -m http.server 8080
```

Abra `http://localhost:8080`. O frontend seleciona automaticamente `http://localhost:8000` em `localhost` e `127.0.0.1`.

Para OCR local, instale também o Tesseract e o idioma português (`tesseract-ocr-por`). Sem os pesos do NER, o scanner funciona em modo regex.

## 2. Banco Neon

Crie um projeto no Neon e copie a connection string de produção para o Render. Ela deve ser usada somente como `DATABASE_URL` no serviço do backend; não coloque essa URL em arquivos versionados.

Use uma base separada para desenvolvimento e testes. A aplicação cria e ajusta o schema na inicialização, mas isso não substitui migrações formais para mudanças futuras.

## 3. Backend no Render

No Render, escolha **New > Blueprint** e selecione o repositório. O arquivo `render.yaml` já define:

- serviço Docker `masksafe-backend`;
- contexto `backend/`;
- instalação do Tesseract OCR;
- health check em `/`;
- plano gratuito;
- geração automática da `SECRET_KEY`.

Preencha no painel do Render as variáveis marcadas como privadas:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | connection string do Neon |
| `SECRET_KEY` | gerada pelo Render ou uma chave forte exclusiva |
| `BREVO_API_KEY` | chave privada da API transacional da Brevo |
| `SMTP_FROM` | remetente verificado na Brevo |

As demais devem ficar assim:

```env
ENVIRONMENT=production
FRONTEND_URL=https://masksafe.vercel.app
FRONTEND_ORIGINS=https://masksafe.vercel.app
SMTP_FROM_NAME=SafeMask
```

Se o frontend usar domínio próprio, substitua `FRONTEND_URL` e `FRONTEND_ORIGINS` pela origem HTTPS real. Para mais de uma origem, separe por vírgulas.

Depois do primeiro deploy, valide:

- `https://masksafe-backend.onrender.com/`
- `https://masksafe-backend.onrender.com/docs`

O plano gratuito pode suspender o serviço por inatividade; a primeira requisição após isso pode ser lenta.

## 4. Frontend na Vercel

Importe o repositório na Vercel usando estas configurações:

- **Framework Preset:** Other
- **Build Command:** vazio
- **Output Directory:** vazio
- **Root Directory:** raiz do repositório

O `vercel.json` já mantém o site como estático. Não publique apenas a pasta `frontend/`, pois a landing page e os caminhos relativos estão na raiz.

O frontend usa `https://masksafe-backend.onrender.com` como fallback em qualquer host que não seja local. Para uma URL de backend diferente, defina `window.MASKSAFE_API_URL` antes de carregar `frontend/js/config.js` nas páginas HTML, ou altere o fallback desse arquivo antes do deploy.

## 5. E-mail pela Brevo

O envio de recuperação de senha depende de `BREVO_API_KEY` e `SMTP_FROM`. A chave deve ser da API transacional da Brevo, não uma senha SMTP. O endereço de `SMTP_FROM` precisa estar validado na conta da Brevo.

Sem essas variáveis, a aplicação sobe normalmente, mas os fluxos que precisam enviar e-mail falham com erro de configuração.

## 6. Segurança e armazenamento

Nunca versione `backend/.env`, tokens, connection strings ou arquivos de upload. O `.gitignore` já exclui arquivos `.env`.

O backend atual grava PDFs no armazenamento local do serviço. No Render, o disco do serviço gratuito não deve ser tratado como armazenamento persistente: documentos podem ser perdidos em redeploy, reinício ou alteração de infraestrutura. Para uso real, configure um storage persistente compatível (por exemplo, S3/R2/Cloud Storage) antes de armazenar documentos de produção.

## 7. Validação antes de publicar

```bash
python -m compileall -q backend/app backend/scanner
node --check frontend/js/config.js
```

Com a API em execução e os PDFs de exemplo gerados:

```bash
python scripts/gerar_pdf_exemplo.py
python scripts/e2e.py --base-url http://localhost:8000
```
