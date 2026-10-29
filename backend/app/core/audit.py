"""Registro de trilha de auditoria.

O SRS (RN-010) exige que acesso e operacoes criticas fiquem registrados em
`log_auditoria`. A tabela existia, mas nenhuma rota gravava nela.
"""

import ipaddress
import logging
import os

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.log_auditoria import LogAuditoria

logger = logging.getLogger(__name__)

# Acoes usadas nas rotas. Mantidas curtas porque `acao` tem String(100).
ACAO_LOGIN = "login"
ACAO_LOGIN_FALHO = "login_falha"
ACAO_LOGIN_BLOQUEADO = "login_bloqueado"
ACAO_LOGOUT = "logout"
ACAO_CADASTRO = "cadastro"
ACAO_RESET_SENHA_SOLICITACAO = "reset_senha_solicitacao"
ACAO_RESET_SENHA = "reset_senha"
ACAO_REENVIO_CONFIRMAR_EMAIL = "reenviar_confirmacao_email"
ACAO_UPLOAD = "upload_documento"
ACAO_UPLOAD_CENSURADO = "upload_documento_censurado"
ACAO_LISTAR_DOCUMENTOS = "listar_documentos"
ACAO_VER_ORIGINAL = "ver_original"
ACAO_VER_PARCIAL = "ver_parcial"
ACAO_VER_CENSURADO = "ver_censurado"
ACAO_CRIAR_EQUIPE = "criar_equipe"
ACAO_ATUALIZAR_EQUIPE = "atualizar_equipe"
ACAO_ADICIONAR_MEMBRO = "adicionar_membro"
ACAO_REMOVER_MEMBRO = "remover_membro"


def ip_do_cliente(request: Request | None) -> str:
    """Retorna IP cliente; só confia no X-Forwarded-For de proxy configurado.

    Configure TRUSTED_PROXY_IPS com IPs/CIDRs separados por vírgula. Sem
    configuração, usa-se o peer TCP, nunca um header controlado pelo cliente.
    """
    if request is None:
        return "desconhecido"

    peer = request.client.host if request.client else "desconhecido"
    trusted_items = [item.strip() for item in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if item.strip()]
    # Permite peer names fornecidos por alguns ASGI transports; em produção
    # prefira endereços/CIDRs explícitos.
    if peer in trusted_items:
        peer_ip = None
    else:
        try:
            peer_ip = ipaddress.ip_address(peer)
        except ValueError:
            return peer[:45]
    proxy_ranges = []
    for item in trusted_items:
        try:
            proxy_ranges.append(ipaddress.ip_network(item.strip(), strict=False))
        except ValueError:
            continue
    peer_trusted = peer in trusted_items or (
        peer_ip is not None and any(peer_ip in network for network in proxy_ranges)
    )
    if not peer_trusted:
        return peer[:45]

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # A cadeia padrão é cliente, proxies...; caminhe da direita e descarte
        # apenas proxies confiáveis para não aceitar um valor injetado à esquerda.
        chain = [item.strip() for item in forwarded.split(",") if item.strip()]
        for candidate in reversed(chain):
            try:
                candidate_ip = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if any(candidate == item for item in trusted_items) or any(
                candidate_ip in network for network in proxy_ranges
            ):
                continue
            return str(candidate_ip)[:45]
    return peer[:45]


def registrar(
    db: Session,
    request: Request | None,
    user_id: int,
    acao: str,
    *,
    commit: bool = True,
) -> LogAuditoria:
    """Grava uma linha de auditoria.

    Nunca levanta excecao: perder um log nao pode derrubar a requisição que o
    originou. Falhas sao logadas para investigacao.
    """
    entrada = LogAuditoria(
        user_id=user_id,
        acao=acao[:100],
        ip_origem=ip_do_cliente(request),
    )
    try:
        db.add(entrada)
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        logger.exception("Falha ao registrar auditoria: acao=%s user=%s", acao, user_id)
        db.rollback()
    return entrada


def registrar_falha_login(db: Session, request: Request | None, user_id: int | None) -> None:
    """Tentativa de login sem usuario autenticavel usa user_id nulo ou -1.

    `log_auditoria.user_id` tem FK NOT NULL, entao tentativas anônimas entram
    com o menor id conhecido apenas para preservar o registro.
    """
    if user_id is None:
        return
    registrar(db, request, user_id, ACAO_LOGIN_FALHO)
