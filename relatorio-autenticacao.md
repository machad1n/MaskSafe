# Relatório: onde encontrar o código de autenticação

Este relatório aponta os arquivos responsáveis por cadastro, login, validação de sessão e recuperação de senha no SafeMask.

## Visão geral

A autenticação é dividida em duas partes:

- **Frontend:** páginas e scripts em `frontend/html/auth/` e `frontend/js/`.
- **Backend:** API FastAPI em `backend/app/routes/auth.py`, com apoio de módulos de segurança, modelos e esquemas.

Para executar o sistema localmente, siga [inicializacao.md](inicializacao.md). A documentação interativa da API fica em `http://127.0.0.1:8000/docs` depois de iniciar o backend.

## Arquivos principais

| Arquivo | Responsabilidade |
|---|---|
| [backend/app/routes/auth.py](backend/app/routes/auth.py) | Implementa `/auth/login`, `/auth/me`, `/auth/cadastro`, confirmação e reenvio de email, além da recuperação e redefinição de senha. É o melhor ponto de partida para acompanhar os fluxos. |
| [backend/app/core/security.py](backend/app/core/security.py) | Gera e valida hashes de senha com bcrypt; configura a chave, o algoritmo e a validade dos JWTs; separa tokens de acesso dos tokens de redefinição. |
| [backend/app/core/current_user.py](backend/app/core/current_user.py) | Valida o JWT de acesso, localiza o usuário e verifica a versão do token. É usado como dependência nas rotas que exigem autenticação. |
| [backend/app/schemas/usuario.py](backend/app/schemas/usuario.py) | Valida os dados de login e cadastro, incluindo email e limites de tamanho da senha. |
| [backend/app/schemas/auth.py](backend/app/schemas/auth.py) | Valida tokens de confirmação, recuperação e redefinição de senha, além dos emails recebidos. |
| [backend/app/models/usuario.py](backend/app/models/usuario.py) | Define os dados persistidos do usuário, incluindo `senha_hash`, `token_version` e `email_verificado`. |
| [backend/app/models/cadastro_pendente.py](backend/app/models/cadastro_pendente.py) | Mantém compatibilidade com solicitações antigas que aguardavam confirmação; o cadastro atual não usa esta tabela. |
| [backend/app/models/token_confirmacao_email.py](backend/app/models/token_confirmacao_email.py) | Persiste o hash de uso único do token de confirmação, seu usuário e a data de expiração. |
| [backend/app/main.py](backend/app/main.py) | Inicializa o FastAPI, aplica a migração de autenticação no startup e registra o router. |
| [backend/app/database.py](backend/app/database.py) | `garantir_schema_autenticacao` cria as tabelas de confirmação e adiciona `email_verificado` como verdadeiro para contas preexistentes. |
| [backend/app/core/email.py](backend/app/core/email.py) | Envia emails transacionais de recuperação de senha e confirmação de email. |
| [backend/app/core/config.py](backend/app/core/config.py) | Centraliza configurações do ambiente, incluindo validade do token de redefinição e confirmação de email. |

## Código do frontend

| Página | HTML | JavaScript | O que faz |
|---|---|---|---|
| Login | [frontend/html/auth/login.html](frontend/html/auth/login.html) | [frontend/js/login.js](frontend/js/login.js) | Envia email e senha para `POST /auth/login`; guarda o token e os dados de sessão após o sucesso. |
| Cadastro | [frontend/html/auth/cadastro.html](frontend/html/auth/cadastro.html) | [frontend/js/cadastro.js](frontend/js/cadastro.js) | Valida os campos e envia os dados para `POST /auth/cadastro`. |
| Confirmação de email | [frontend/html/auth/confirmar_email.html](frontend/html/auth/confirmar_email.html) | [frontend/js/auth/confirmar_email.js](frontend/js/auth/confirmar_email.js) | Envia o token para `POST /auth/confirmar-email` somente após clique explícito, evitando consumo automático por scanners de links. |
| Reenvio de confirmação | [frontend/html/auth/reenviar_confirmacao.html](frontend/html/auth/reenviar_confirmacao.html) | [frontend/js/auth/reenviar_confirmacao.js](frontend/js/auth/reenviar_confirmacao.js) | Solicita um novo link por `POST /auth/reenviar-confirmacao`. |
| Recuperação | [frontend/html/auth/esqueci_senha.html](frontend/html/auth/esqueci_senha.html) | [frontend/js/auth/esqueci_senha.js](frontend/js/auth/esqueci_senha.js) | Solicita o envio das instruções por `POST /auth/recuperar-senha`. |
| Redefinição | [frontend/html/auth/reset_password.html](frontend/html/auth/reset_password.html) | [frontend/js/auth/reset_password.js](frontend/js/auth/reset_password.js) | Lê o token do link enviado por email e envia a nova senha para `POST /auth/reset-senha`. |

Arquivos complementares do frontend:

- [frontend/js/session.js](frontend/js/session.js): centraliza leitura, gravação e limpeza da sessão no `localStorage`, além da verificação local de login e cargo.
- [frontend/js/config.js](frontend/js/config.js): define a URL base da API para execução local ou hospedada.
- [frontend/js/app-shell.js](frontend/js/app-shell.js): usa os dados da sessão para montar a interface e controlar a exibição de itens por cargo. Essa exibição é apenas de interface; a autorização real deve ser garantida pelo backend.

## Fluxos da API

| Método e endpoint | Uso |
|---|---|
| `POST /auth/login` | Confere credenciais, registra tentativas e retorna um token de acesso e a identidade do usuário; não exige confirmação de email. |
| `GET /auth/me` | Retorna a identidade do usuário autenticado. Exige um token de acesso Bearer. |
| `POST /auth/cadastro` | Cria usuário com senha bcrypt, email verificado e organização/equipe na mesma transação; não envia email nem exige confirmação. |
| `POST /auth/confirmar-email` | Valida token aleatório, não expirado e de uso único; cria a conta, organização e equipe, e apaga a pendência na mesma transação. |
| `POST /auth/reenviar-confirmacao` | Substitui o token anterior e envia outro para solicitação pendente. Resposta genérica e limites por email/IP evitam enumeração e abuso. |
| `POST /auth/recuperar-senha` | Solicita o email de recuperação. A resposta é genérica para não revelar se o endereço está cadastrado. |
| `POST /auth/reset-senha` | Valida o token próprio de redefinição, atualiza o hash da senha e invalida tokens de acesso emitidos antes da troca. |

## Como o token é validado

1. O cadastro atual valida email/nome/senha e cria senha bcrypt, usuário (`email_verificado=True`), organização, equipe e vínculo de liderança em uma transação. A unicidade do email é verificada pela API e reforçada pela restrição única do banco; nenhuma chamada a serviço de email condiciona o sucesso.
2. O login fica disponível imediatamente após a resposta de cadastro e emite o token de acesso habitual. Recuperação e redefinição de senha permanecem por email, com resposta genérica para evitar enumeração e tokens de reset de uso único.
3. `/auth/confirmar-email` e `/auth/reenviar-confirmacao` permanecem por compatibilidade com tokens/solicitações criados antes da alteração; novas contas não dependem desses endpoints. Tokens legados expirados, inválidos ou já usados continuam recusados.
4. O frontend armazena o token de acesso e o envia à API em chamadas autenticadas. [backend/app/core/current_user.py](backend/app/core/current_user.py) valida assinatura, expiração, tipo e versão da senha.
5. A migração mantém as tabelas de confirmação e define `email_verificado=True` para contas antigas quando a coluna ainda não existe. Contas já existentes com valor falso também podem fazer login, pois a confirmação não é mais requisito.
6. Tokens de redefinição permanecem separados dos tokens de acesso e da confirmação de email.

## Testes relacionados

- [backend/tests/test_sessao_token_e_limite.py](backend/tests/test_sessao_token_e_limite.py): sessão, validade de token e limite de tentativas de login.
- [backend/tests/test_confirmacao_email.py](backend/tests/test_confirmacao_email.py): cadastro pendente, email, confirmação, expiração, reuso, reenvio, limite e migração de contas antigas.
- [backend/tests/test_sessao_e_cargo.py](backend/tests/test_sessao_e_cargo.py): identidade, sessão e cargo retornados ao usuário.
- [backend/tests/test_autorizacao.py](backend/tests/test_autorizacao.py): regras de autorização por cargo.

## Caminho recomendado para manutenção

- **Investigar login:** comece em [frontend/js/login.js](frontend/js/login.js), siga para [backend/app/routes/auth.py](backend/app/routes/auth.py) e depois para [backend/app/core/security.py](backend/app/core/security.py).
- **Investigar páginas protegidas:** veja [frontend/js/session.js](frontend/js/session.js) e [backend/app/core/current_user.py](backend/app/core/current_user.py); confira também as dependências usadas pelas rotas protegidas.
- **Investigar recuperação de senha:** percorra [frontend/js/auth/esqueci_senha.js](frontend/js/auth/esqueci_senha.js), [backend/app/routes/auth.py](backend/app/routes/auth.py), [backend/app/core/email.py](backend/app/core/email.py) e [frontend/js/auth/reset_password.js](frontend/js/auth/reset_password.js).
- **Investigar confirmação de email:** percorra [frontend/js/auth/confirmar_email.js](frontend/js/auth/confirmar_email.js), [frontend/js/auth/reenviar_confirmacao.js](frontend/js/auth/reenviar_confirmacao.js), [backend/app/routes/auth.py](backend/app/routes/auth.py), [backend/app/models/token_confirmacao_email.py](backend/app/models/token_confirmacao_email.py) e [backend/app/core/email.py](backend/app/core/email.py).
- **Alterar campos ou regras de senha:** confira `backend/app/schemas/usuario.py`, `backend/app/schemas/auth.py` e os testes correspondentes.

## Alteração: cadastro e login sem confirmação de email

A rota `POST /auth/cadastro` agora cria a conta e a estrutura inicial de organização/equipe de forma atômica e marca `email_verificado=True`; não envia mensagem de confirmação. A senha continua sendo validada no schema e armazenada com bcrypt. O login imediato é coberto por teste. As rotas e tabelas de confirmação não foram removidas, permitindo consumir pendências e tokens já emitidos. Recuperação de senha por email, resposta anti-enumeração e uso único do token de redefinição permanecem inalterados. Não há migração de banco necessária: as colunas/tabelas já existentes são mantidas.

## Revisão de segurança do fluxo

### Escopo e resumo

Foram analisados o cadastro e login, a emissão e validação de tokens, o estado de sessão no navegador, a recuperação e redefinição de senha, os controles de tentativas, a autorização por cargo e organização e os testes relacionados. A revisão encontrou dois pontos, ambos corrigidos nas alterações descritas abaixo. Os demais controles observados incluem hash de senha com bcrypt, expiração e tipos distintos para JWTs, invalidação de tokens de acesso após troca de senha, limite de tentativas de login e verificação de autorização no backend.

### Achados

| # | Severidade | Arquivo | Linhas | Vulnerabilidade | Confiança | Status |
|---|---|---|---|---|---|---|
| 1 | 🟡 MEDIUM | [backend/app/routes/auth.py](backend/app/routes/auth.py) | 349-381 | O token de redefinição não era invalidado nem marcado como usado após a troca de senha, permitindo outra redefinição enquanto válido. | 9/10 | Corrigido |
| 2 | ⚪ LOW | [backend/app/routes/auth.py](backend/app/routes/auth.py) | 304-319 | `POST /auth/recuperar-senha` retornava erro 500 se o endereço existisse e o envio falhasse, revelando a existência da conta. | 9/10 | Corrigido |

#### 1. Token de redefinição reutilizável

Antes da correção, o token era emitido sem versão vinculada ao usuário. Agora `POST /auth/recuperar-senha` inclui a `token_version` atual no token de redefinição. `POST /auth/reset-senha` valida essa versão e atualiza senha e versão com uma operação condicional no banco. Após o primeiro uso bem-sucedido, tokens emitidos com a versão antiga deixam de ser aceitos; a atualização condicional também impede que duas requisições simultâneas consumam a mesma versão.

Tokens antigos sem a claim `tv` são tratados como versão `0` por compatibilidade; eles também ficam inutilizados após uma redefinição bem-sucedida ou quando o token expirar. O teste de regressão reutiliza o mesmo token e verifica que a segunda tentativa falha e não altera a senha definida no primeiro uso.

#### 2. Enumeração de contas durante falha de email

Antes da correção, o endpoint usava uma resposta genérica quando o endereço não estava cadastrado, mas retornava erro 500 se a conta existisse e a geração/envio do email falhasse. Agora erros no processamento da solicitação são registrados no log do backend e o endpoint mantém a mesma resposta genérica e status público. O teste de regressão simula uma falha do provedor e compara as respostas para email existente e inexistente.

Como consequência intencional da proteção contra enumeração, a pessoa solicitante não recebe confirmação de falha de entrega; a falha continua visível para a equipe nos logs. A mensagem agora informa que a pessoa receberá instruções caso o email esteja cadastrado, sem afirmar que o envio já ocorreu. O envio assíncrono permanece uma possível evolução operacional, mas não foi necessário para corrigir o vazamento.

## Alterações realizadas nesta correção

- [backend/app/routes/auth.py](backend/app/routes/auth.py): adicionada a claim `tv` ao token de recuperação; a redefinição rejeita versões inválidas ou obsoletas e grava hash da nova senha junto com o incremento condicional de `token_version`; falhas de auditoria, geração ou envio do email são registradas com `logger.exception`, mantendo status e resposta pública genéricos para não enumerar contas. A mensagem de recuperação também foi ajustada para não afirmar que o email já foi enviado.
- [backend/tests/test_sessao_token_e_limite.py](backend/tests/test_sessao_token_e_limite.py): adicionados testes para confirmar que o mesmo token de redefinição não pode trocar a senha duas vezes e que a recuperação mantém status e corpo idênticos quando o envio falha para uma conta existente.
- Nenhuma coluna ou migração de banco foi necessária: a correção usa `token_version`, que já existe e já é incrementada na troca de senha.
- Os links internos deste relatório foram ajustados para a localização atual do arquivo na raiz do repositório.
- **Validação executada:** `backend\.venv\Scripts\python.exe -m pytest tests\test_sessao_token_e_limite.py -q` (executado a partir da pasta `backend`): **26 testes passaram**.

### Recomendações preventivas

- **Reduzir exposição do token no navegador:** a sessão atual guarda o token em `localStorage` por meio de [frontend/js/session.js](frontend/js/session.js), o que permite que JavaScript executado na origem leia o token. A revisão não identificou, no escopo examinado, um caminho de XSS explorável que confirme roubo de token. Como defesa em profundidade, avaliar cookie `HttpOnly`, `Secure` e `SameSite` para a sessão. Essa mudança exige configurar proteção contra CSRF e rever CORS, login, logout e chamadas da API; não é uma troca isolada de armazenamento.
- **Proteger o link de redefinição:** evitar incluir o endereço de email na URL se a página não precisar dele; fragmentos e parâmetros de URL podem aparecer em histórico, logs e telemetria. Configurar a página para não carregar recursos de terceiros desnecessários, definir uma política `Referrer-Policy` restritiva e remover token e email da barra de endereço após a leitura, sem comprometer o envio inicial do token.
- **Manter configuração segura em produção:** configurar `SECRET_KEY` forte e estável e as variáveis do provedor de email no ambiente de produção, nunca em código versionado. Verificar os valores e a descrição de configuração em [backend/app/core/config.py](backend/app/core/config.py) e [backend/app/core/security.py](backend/app/core/security.py).
- **Cobrir cenários de segurança como contratos:** [backend/tests/test_sessao_token_e_limite.py](backend/tests/test_sessao_token_e_limite.py) agora verifica o uso único do token de redefinição e respostas indistinguíveis na recuperação mesmo quando o envio falha. Os demais testes do arquivo cobrem também expiração/tipo de tokens, limite de tentativas e invalidação de sessões após troca de senha.
- **Tratar o cargo no cliente apenas como apresentação:** [frontend/js/app-shell.js](frontend/js/app-shell.js) esconde itens por cargo, mas isso não substitui autorização. As decisões de acesso devem continuar sendo aplicadas em cada endpoint protegido no backend; evite considerar o cargo salvo no navegador como prova de permissão.

### Controles observados sem achado confirmado nesta revisão

- A senha é transformada em hash com bcrypt no backend; o frontend envia a senha em texto no corpo da requisição, portanto o ambiente publicado deve usar HTTPS.
- Os tokens de acesso e de redefinição têm tipos distintos, e o dependente de usuário atual rejeita tokens que não sejam de acesso.
- Os tokens de acesso têm expiração e carregam uma versão de senha; a troca de senha incrementa essa versão.
- O login registra falhas e aplica limite de tentativas por email e IP.
- O backend resolve usuário e cargo a partir do token e aplica verificações de autorização e escopo organizacional; o estado/cargo no navegador não deve ser a fonte de autorização.
- Embora o token seja guardado no `localStorage`, isso por si só não comprova uma falha explorável sem um caminho de execução de JavaScript não confiável. A recomendação de armazenamento em cookie é preventiva e requer mudanças coordenadas contra CSRF.

## Compatibilidade legada: implementação anterior da confirmação de email

Esta seção descreve o fluxo de confirmação que existia antes da alteração atual; não representa o comportamento do cadastro novo. As rotas continuam ativas apenas para terminar pendências/tokens previamente emitidos:

1. No fluxo antigo, uma solicitação ainda pendente em `cadastro_pendente` guardava nome, email, hash da senha e hash/validade do token, sem criar `Usuario`, `Organizacao` ou `Equipe`. O cadastro atual não cria novas pendências.
2. `POST /auth/confirmar-email` continua disponível para tokens legados: valida hash e validade, cria usuário com email verificado, organização e equipe, e remove a pendência na mesma transação. Após o uso, o link não pode ser reaproveitado.
3. `POST /auth/reenviar-confirmacao` substitui o token anterior somente para solicitações pendentes legadas. Responde genericamente para emails inexistentes, já confirmados, limitados ou com falha de envio; registra auditoria e limita os reenvios a 3 por pendência e 10 por IP em uma janela de uma hora.
4. O cadastro atual cria a conta imediatamente, e o login fica disponível sem clicar em link de confirmação. Uma pendência legada não cria conta até que seu token antigo seja confirmado.
5. A validade do link é configurável por `EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS` (padrão: 24 horas). Tokens são gerados com `secrets.token_urlsafe(32)`; somente SHA-256 é armazenado no banco.
6. A página do link não confirma automaticamente ao abrir: scanners de email podem visitar o endereço sem consumir o token. O navegador remove o token da barra de endereço e só envia a confirmação após clique.

### Arquivos alterados para essa implementação

- [backend/app/models/usuario.py](backend/app/models/usuario.py): mantém `email_verificado` verdadeiro por padrão para compatibilidade; o cadastro atual define a flag como verdadeira sem exigir confirmação.
- [backend/app/models/cadastro_pendente.py](backend/app/models/cadastro_pendente.py): nova tabela temporária para dados do cadastro, hash do token, validade e limite de reenvio.
- [backend/app/models/token_confirmacao_email.py](backend/app/models/token_confirmacao_email.py): tabela de tokens com hash único, usuário, criação e expiração; há no máximo um token vigente por usuário.
- [backend/app/models/__init__.py](backend/app/models/__init__.py): registra o novo modelo para criação da tabela.
- [backend/app/database.py](backend/app/database.py) e [backend/app/main.py](backend/app/main.py): migração idempotente no startup para criar a tabela de pendências; contas que já estavam no banco recebem `email_verificado=True`.
- [backend/app/core/email.py](backend/app/core/email.py): adiciona o email/link de confirmação e reutiliza o envio transacional do provedor também para recuperação de senha.
- [backend/app/core/config.py](backend/app/core/config.py): adiciona configuração da validade do token de confirmação.
- [backend/app/core/audit.py](backend/app/core/audit.py): registra um tipo de evento de auditoria para reenvios.
- [backend/app/schemas/auth.py](backend/app/schemas/auth.py): valida o token recebido na confirmação.
- [backend/app/routes/auth.py](backend/app/routes/auth.py): o cadastro atual cria usuário/organização/equipe diretamente; rotas de token descartável e reenvio limitado atendem compatibilidade legada.
- [frontend/html/auth/confirmar_email.html](frontend/html/auth/confirmar_email.html) e [frontend/js/auth/confirmar_email.js](frontend/js/auth/confirmar_email.js): confirmação iniciada por clique, não por carregamento automático do link.
- [frontend/html/auth/reenviar_confirmacao.html](frontend/html/auth/reenviar_confirmacao.html) e [frontend/js/auth/reenviar_confirmacao.js](frontend/js/auth/reenviar_confirmacao.js): formulário de reenvio com mensagem neutra.
- [frontend/js/cadastro.js](frontend/js/cadastro.js): apresenta o sucesso do cadastro direto e o link para login; não imprime senha e dados pessoais no console.
- [backend/tests/test_confirmacao_email.py](backend/tests/test_confirmacao_email.py): cobre cadastro direto/login imediato e, em separado, confirmação/reenvio de pendências antigas.
- O cadastro direto não inicia sessão automaticamente; o usuário pode abrir login imediatamente.

### Validação

- Suíte completa do backend: `python -m pytest -q` — **171 testes passaram**.
- Ruff nos módulos e testes alterados: aprovado.
- `node --check` nos scripts JavaScript alterados: aprovado.
- `git diff --check`: aprovado.

### Ajuste de feedback no reenvio

- [frontend/html/auth/reenviar_confirmacao.html](frontend/html/auth/reenviar_confirmacao.html): a área de retorno tem anúncio acessível (`aria-live`) e o botão recebeu um identificador para controlar o estado do envio.
- [frontend/js/auth/reenviar_confirmacao.js](frontend/js/auth/reenviar_confirmacao.js): ao enviar, desabilita o botão e mostra “Enviando solicitação...” junto de uma mensagem de progresso; ao concluir, exibe orientação para verificar entrada/spam, ou um erro de comunicação, e reabilita o botão.
- [backend/app/routes/auth.py](backend/app/routes/auth.py): a resposta neutra agora explica que o pedido foi recebido e que o email só será enviado se houver uma conta pendente; também orienta a verificar spam ou entrar caso já esteja confirmado. Continua sem revelar se o endereço existe.

### Diagnóstico de email não recebido

- O envio de recuperação de senha e de links de confirmação legados depende de `BREVO_API_KEY` e `SMTP_FROM`; a função de envio falha se qualquer uma estiver ausente. `SMTP_FROM` precisa ser um remetente validado na conta Brevo.
- Verificação do ambiente local nesta sessão: não existe `backend/.env` e `BREVO_API_KEY`, `SMTP_FROM` e `SMTP_FROM_NAME` não estão definidos no shell. Isso explica falhas em execução local. A configuração privada do serviço Render não é visível neste ambiente e precisa ser verificada no painel/logs do serviço.
- [render.yaml](render.yaml): declara `BREVO_API_KEY` e `SMTP_FROM` como variáveis privadas (`sync: false`) para o Blueprint solicitar seus valores; `SMTP_FROM_NAME` recebe o nome padrão SafeMask.
- [README.md](README.md): documenta as configurações necessárias para envio local e no Render.
- A entrega de confirmação deixou de fazer parte do cadastro atual. A rota de reenvio e a resposta neutra permanecem apenas para solicitações pendentes legadas.
- [backend/app/core/email.py](backend/app/core/email.py): o log de sucesso foi ajustado para dizer que a Brevo aceitou a solicitação, sem sugerir que houve entrega na caixa postal.
- [backend/app/core/config.py](backend/app/core/config.py): a API falha explicitamente no startup se `EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS` for zero ou negativo.
- Os testes de confirmação legada continuam usando envio simulado; não provam entrega real de email.
- Registro histórico: uma verificação feita em 2026-10-27 observou a página de confirmação retornando 404 e a rota ausente do OpenAPI publicado naquele momento. Essa observação não foi revalidada após as alterações atuais; a confirmação é hoje apenas compatibilidade para pendências antigas, e a nova inscrição não depende dela.
- Depois de configurar os valores válidos, sincronize o Blueprint no Render, preencha os segredos e faça deploy. Nos logs, procure a aceitação pela Brevo ou exceções de configuração/API e confira o estado de entrega no painel da Brevo. Não compartilhe nem registre a chave da API.
