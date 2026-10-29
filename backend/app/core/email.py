import logging
import os

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app.core.config import (
    EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS,
    FRONTEND_URL,
    RESET_TOKEN_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)


def _enviar_email_transacional(destinatario: str, assunto: str, conteudo: str) -> None:
    api_key = os.getenv("BREVO_API_KEY")
    smtp_from = os.getenv("SMTP_FROM")
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "SafeMask")
    support_email = os.getenv("SUPPORT_EMAIL") or smtp_from

    if not api_key:
        raise ValueError("BREVO_API_KEY não configurado.")
    if not smtp_from:
        raise ValueError("SMTP_FROM não configurado.")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": destinatario}],
        sender={"email": smtp_from, "name": smtp_from_name},
        reply_to={"email": support_email},
        subject=assunto,
        text_content=conteudo,
    )

    try:
        api_instance.send_transac_email(email)
        logger.info("Brevo aceitou a solicitação de envio transacional para %s", destinatario)
    except ApiException:
        logger.exception("Falha ao enviar email via Brevo para %s", destinatario)
        raise


def enviar_email_recuperacao(destinatario: str, nome: str, token: str) -> None:
    support_email = os.getenv("SUPPORT_EMAIL") or os.getenv("SMTP_FROM")
    linhas = [
        f"Olá, {nome}.",
        "",
        "Recebemos uma solicitação de recuperação de senha para a sua conta SafeMask.",
        f"Clique no link abaixo para redefinir sua senha. Este link expira em {RESET_TOKEN_EXPIRE_MINUTES} minutos.",
        "",
    ]

    if FRONTEND_URL:
        reset_path = "/frontend/html/auth/reset_password.html"
        link = f"{FRONTEND_URL}{reset_path}#token={token}"
        linhas.extend([f"Redefinir senha: {link}", ""])
    else:
        linhas.extend(["(Frontend não configurado. Contate o suporte.)", ""])

    if support_email:
        linhas.extend([f"Suporte: {support_email}"])

    _enviar_email_transacional(
        destinatario,
        "SafeMask - Recuperação de senha",
        "\n".join(linhas),
    )


def enviar_email_confirmacao(destinatario: str, nome: str, token: str) -> None:
    linhas = [
        f"Olá, {nome}.",
        "",
        "Confirme seu endereço de email para ativar sua conta SafeMask.",
        f"Este link expira em {EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS} horas e só pode ser usado uma vez.",
        "",
    ]

    if FRONTEND_URL:
        confirm_path = "/frontend/html/auth/confirmar_email.html"
        link = f"{FRONTEND_URL}{confirm_path}#token={token}"
        linhas.extend([f"Confirmar email: {link}", ""])
    else:
        linhas.extend(["(Frontend não configurado. Contate o suporte.)", ""])

    _enviar_email_transacional(
        destinatario,
        "SafeMask - Confirme seu email",
        "\n".join(linhas),
    )
