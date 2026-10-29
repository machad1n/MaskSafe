# Executar o SafeMask no VS Code

## Pré-requisitos

- Python 3.11 ou superior.
- PostgreSQL local ou remoto acessível. O projeto cria/atualiza o schema na inicialização; use uma base de desenvolvimento, nunca produção para testes.
- Tesseract OCR e idioma português (`por`) se precisar do OCR. Sem pesos NER, o scanner opera no modo regex previsto pelo projeto.
- Chaves da Brevo e remetente verificado somente para testar envio real de e-mails. Não são necessários para rodar os testes automatizados.

## Configurar backend

1. Abra a pasta raiz do projeto no VS Code.
2. Copie `backend/.env.example` para `backend/.env` e substitua os valores localmente. Gere uma `SECRET_KEY` com:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. No terminal do VS Code, crie/ative o ambiente virtual dentro de `backend`:

   **Windows PowerShell**
   ```powershell
   cd backend
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   **macOS/Linux**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Inicie o backend, ainda em `backend`:

   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   API: `http://127.0.0.1:8000`; documentação: `http://127.0.0.1:8000/docs`.

## Servir o frontend

Abra um segundo terminal na raiz do projeto e execute:

```bash
python -m http.server 8080
```

Abra `http://localhost:8080`. Login: `http://localhost:8080/frontend/html/auth/login.html`.

O frontend usa `localhost:8000` automaticamente em localhost. A origem local é permitida pelo backend em desenvolvimento.

## Testes e lint

No terminal do backend, com o ambiente virtual ativado:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
ruff check app scanner tests
```

Os testes usam SQLite temporário por meio da configuração de testes e não enviam e-mails reais. Não aponte `DATABASE_URL` de testes para uma base de produção. Consulte o `README.md` para instalação detalhada, deploy e variáveis de ambiente.
