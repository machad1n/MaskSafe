# Auditoria dos requisitos da imagem

**Data:** 29/10/2026  
**Escopo:** revisão do código local e dos testes do MaskSafe. Os títulos na imagem não especificam critérios de aceite detalhados; os status abaixo refletem somente o comportamento verificável no projeto, não uma confirmação de implantação em produção.

## Resultado por requisito

| ID | Requisito | Situação | Evidência e observações |
|---|---|---|---|
| #16 | Corrigir vazamento entre equipes em original/descensura parcial | **Corrigido no código; validado por testes** | Acesso a documento, original, preview e parcial é autorizado pela equipe e organização. Listagens e seleções de equipes filtram tenant. Arquivos fora do diretório permitido e symlinks externos são recusados; respostas de arquivo não ficam em cache. Testes incluem isolamento e symlink. |
| #19 | Melhorias na autenticação e recuperação de senha | **Corrigido no código; validado por testes** | O cadastro cria conta ativa, hash de senha e organização/equipe em transação, sem exigir ou enviar confirmação de email; login fica disponível imediatamente. A senha continua validada e armazenada em bcrypt. Fluxos de recuperação/reset, resposta anti-enumeração, token de uso único, limite de tentativas e invalidação de sessões foram preservados. Rotas/tabelas de confirmação ficam apenas para pendências legadas. |
| #23 | Expansão das funcionalidades de usuários e equipes | **Operações adicionadas; testes de autorização/isolamento aprovados** | Usuários com papel de gestão podem editar equipe, adicionar/remover membros e alterar cargos conforme hierarquia. Equipes de outra organização não são reveladas. Exclusão e remoção são bloqueadas com HTTP 409 quando existem documentos associados, preservando documentos e vínculos. A interface permite essas operações; a seleção de usuários/cargos usa entrada de IDs e pode receber melhoria de usabilidade posterior. |
| #10 | Melhoria no Front-end | **Parcialmente verificado** | Foram melhorados o feedback do cadastro sem confirmação, os controles de gestão de equipe e a acessibilidade/descrição do gráfico do dashboard. A imagem não traz critérios detalhados para as demais páginas e não foi feita validação visual completa em navegador real. |
| #21 | Melhorias na segurança e no armazenamento de arquivos | **Proteções implementadas; criptografia/retention pendentes** | Foram reforçados o isolamento por organização, a validação do caminho persistido, o bloqueio de symlink/path externo e os cabeçalhos privados sem cache. **Os arquivos continuam sem criptografia em repouso**, conforme já informado no README. Política de retenção/expurgo de originais, derivados e backups não foi definida nem implementada; isso requer decisão operacional e gestão segura de chaves/backup, e não foi inventado nesta correção. |
| #22 | Correção das métricas e estados no dashboard | **Corrigido no código; testes de regressão aprovados** | A API conta documentos ativos e estados reais; nível de segurança alto é indicador independente. O gráfico circular usa fatias complementares e não soma a métrica sobreposta de nível alto, evitando percentual acima de 100%. O caso total zero e documento ainda em processamento tem cobertura de teste. |

## Alterações principais

- Cadastro sem confirmação de email, com conta ativa e login imediato; mantida compatibilidade de confirmação apenas para solicitações antigas.
- Filtros de tenant e equipe no acesso/listagem de documentos, com proteção contra caminhos fora do storage e symlinks externos.
- Gestão de equipes e membros, com autorização por cargo e bloqueio de exclusão que poderia deixar documentos órfãos.
- Ajuste do gráfico do dashboard e descrição acessível.
- README e instruções de autenticação atualizados; nenhum segredo ou arquivo `.env` real foi adicionado.

## Testes executados

- Suíte completa do backend com SQLite de teste: **184 passaram** (`python -m pytest -q`).
- Ruff em `app`, `scanner` e `tests`: **aprovado**.
- Compilação/sintaxe Python (`compileall`) e análise sintática de todos os scripts JavaScript (`node --check`): **aprovadas**.

Uma primeira execução integrada encontrou 12 falhas: expectativas antigas que ainda exigiam cadastro pendente e fixtures que gravavam arquivos fora do storage autorizado, além de um fallback que podia contornar um caminho armazenado inválido. Os testes/fixtures foram atualizados para o contrato novo e o fallback inseguro foi removido; a suíte final completa passou.

## Limites desta validação

Não foram feitas operações na conta real da Brevo, Neon, Render ou Vercel; não foi comprovado envio de email, conexão ao banco de produção nem deploy. Também não foi executado um teste ponta a ponta em navegador real. A aprovação dos testes demonstra o comportamento coberto no ambiente local, não a disponibilidade do serviço hospedado. Antes de publicar, configure os segredos nos painéis e teste cadastro/login, recuperação de senha, equipes e arquivos em ambiente controlado.
