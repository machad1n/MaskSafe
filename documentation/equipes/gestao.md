# Gestão de equipes

Supervisores/líderes podem editar nome e descrição e gerenciar membros na própria organização, desde que tenham cargo supervisor ou superior na equipe alvo. Adição e alteração de cargo validam sempre o tenant; apenas líderes podem atribuir cargos de liderança e nenhum usuário pode atribuir cargo superior ao próprio. Membros com cargo igual/superior não podem ser removidos por hierarquia.

Exclusão de equipe é permanente apenas quando não existem documentos associados. A API retorna HTTP 409 quando qualquer documento (ativo ou não) está vinculado, preservando documentos, vínculos e histórico. A remoção individual de membro também retorna 409 se o vínculo possuir documentos. Não existe movimentação de documentos entre equipes nesta funcionalidade.
