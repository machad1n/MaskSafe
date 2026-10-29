import hashlib
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

from app.core import email as email_service
from app.database import garantir_schema_autenticacao
from app.models.cadastro_pendente import CadastroPendente
from app.models.equipe import Equipe
from app.models.organizacao import Organizacao
from app.models.token_confirmacao_email import TokenConfirmacaoEmail
from app.models.usuario import Usuario

SENHA = "SenhaForte123!"


def _cadastro(client, email="nova@safemask.example.com"):
    return client.post(
        "/auth/cadastro",
        json={"nome": "Nova Pessoa", "email": email, "senha_hash": SENHA},
    )


def test_cadastro_cria_conta_sem_confirmacao_e_login_imediato(client, seed):
    resposta = _cadastro(client)

    assert resposta.status_code == 201, resposta.text
    assert "access_token" not in resposta.json()
    usuario = seed["db"].query(Usuario).filter_by(
        email="nova@safemask.example.com"
    ).one()
    assert usuario.email_verificado is True
    assert usuario.senha_hash != SENHA
    assert seed["db"].query(CadastroPendente).filter_by(
        email=usuario.email
    ).count() == 0
    assert seed["db"].query(Organizacao).count() == 3
    assert seed["db"].query(Equipe).count() == 4
    assert seed["db"].query(TokenConfirmacaoEmail).count() == 0

    login = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha_hash": SENHA},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    assert login.json()["user"]["organizacao_id"] == usuario.organizacao_id
    assert login.json()["user"]["cargo"] == "lider"


def test_cadastro_email_unico_e_senha_forte(client, seed):
    resposta = _cadastro(client, email="ana@safemask.example.com")
    assert resposta.status_code == 400

    invalido = client.post(
        "/auth/cadastro",
        json={"nome": "Nova Pessoa", "email": "nova@safemask.example.com", "senha_hash": "fraca"},
    )
    assert invalido.status_code == 422


def _cadastro_legado(client, seed, email="nova@safemask.example.com"):
    """Simula uma solicitação pendente anterior à desativação da confirmação."""
    import secrets

    from app.core.security import hash_senha

    token = secrets.token_urlsafe(32)
    cadastro = CadastroPendente(
        nome="Nova Pessoa", email=email, senha_hash=hash_senha(SENHA),
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expira_em=datetime.utcnow() + timedelta(hours=24),
    )
    seed["db"].add(cadastro)
    seed["db"].commit()
    return token


def test_cadastro_nao_depende_do_provedor_de_email(client, seed, monkeypatch):
    def falha_envio(*args, **kwargs):
        raise AssertionError("cadastro direto não deve enviar email")

    monkeypatch.setattr("app.routes.auth.enviar_email_confirmacao", falha_envio)
    resposta = _cadastro(client)
    assert resposta.status_code == 201, resposta.text


def test_confirmacao_valida_consumida_uma_vez_e_libera_login(
    client, seed, monkeypatch
):
    emails = []
    monkeypatch.setattr(
        "app.routes.auth.enviar_email_confirmacao",
        lambda destinatario, nome, token: emails.append(token),
    )
    token = _cadastro_legado(client, seed)

    confirmar = client.post("/auth/confirmar-email", json={"token": token})
    reutilizar = client.post("/auth/confirmar-email", json={"token": token})

    assert confirmar.status_code == 200, confirmar.text
    assert reutilizar.status_code == 400
    usuario = seed["db"].query(Usuario).filter_by(
        email="nova@safemask.example.com"
    ).one()
    assert usuario.email_verificado is True
    assert seed["db"].query(CadastroPendente).filter_by(
        email="nova@safemask.example.com"
    ).count() == 0
    assert usuario.organizacao_id != seed["organizacao"].organizacao_id
    assert seed["db"].query(Organizacao).count() == 3
    assert seed["db"].query(Equipe).count() == 4
    assert seed["db"].query(Usuario).filter_by(
        email="nova@safemask.example.com"
    ).count() == 1
    assert seed["db"].query(TokenConfirmacaoEmail).filter_by(
        user_id=usuario.user_id
    ).count() == 0

    login = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha_hash": SENHA},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_token_de_cadastro_pendente_expirado_nao_cria_usuario(
    client, seed, monkeypatch
):
    emails = []
    monkeypatch.setattr(
        "app.routes.auth.enviar_email_confirmacao",
        lambda destinatario, nome, token: emails.append(token),
    )
    token_legado = _cadastro_legado(client, seed)
    cadastro = seed["db"].query(CadastroPendente).filter_by(
        email="nova@safemask.example.com"
    ).one()
    cadastro.expira_em = datetime.utcnow() - timedelta(seconds=1)
    seed["db"].commit()

    resposta = client.post(
        "/auth/confirmar-email", json={"token": token_legado}
    )

    assert resposta.status_code == 400
    assert seed["db"].query(Usuario).filter_by(
        email="nova@safemask.example.com"
    ).count() == 0
    assert seed["db"].query(CadastroPendente).filter_by(
        email="nova@safemask.example.com"
    ).count() == 1


def test_token_expirado_nao_confirma_email(client, seed):
    usuario = seed["usuario"]
    token = "token-expirado"
    seed["db"].add(
        TokenConfirmacaoEmail(
            user_id=usuario.user_id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expira_em=datetime.utcnow() - timedelta(seconds=1),
        )
    )
    seed["db"].commit()

    resposta = client.post("/auth/confirmar-email", json={"token": token})

    assert resposta.status_code == 400
    assert usuario.email_verificado is True


def test_reenvio_substitui_token_antigo_e_respostas_sao_genericas(
    client, seed, monkeypatch
):
    emails = []
    monkeypatch.setattr(
        "app.routes.auth.enviar_email_confirmacao",
        lambda destinatario, nome, token: emails.append(token),
    )
    token_antigo = _cadastro_legado(client, seed)

    reenvio = client.post(
        "/auth/reenviar-confirmacao",
        json={"email": "nova@safemask.example.com"},
    )
    resposta_desconhecida = client.post(
        "/auth/reenviar-confirmacao",
        json={"email": "inexistente@safemask.example.com"},
    )

    assert reenvio.status_code == resposta_desconhecida.status_code == 200
    assert reenvio.json() == resposta_desconhecida.json()
    assert len(emails) == 1
    token_novo = emails[0]
    assert token_novo != token_antigo
    assert seed["db"].query(Usuario).filter_by(
        email="nova@safemask.example.com"
    ).count() == 0
    assert client.post(
        "/auth/confirmar-email", json={"token": token_antigo}
    ).status_code == 400
    assert client.post(
        "/auth/confirmar-email", json={"token": token_novo}
    ).status_code == 200


def test_reenvio_aplica_limite_por_usuario(client, seed, monkeypatch):
    emails = []
    monkeypatch.setattr(
        "app.routes.auth.enviar_email_confirmacao",
        lambda destinatario, nome, token: emails.append(token),
    )
    token_antigo = _cadastro_legado(client, seed)

    respostas = [
        client.post(
            "/auth/reenviar-confirmacao",
            json={"email": "nova@safemask.example.com"},
        )
        for _ in range(4)
    ]

    assert all(resposta.status_code == 200 for resposta in respostas)
    assert len(emails) == 3  # três reenvios por janela para uma pendência legada
    assert client.post(
        "/auth/confirmar-email", json={"token": token_antigo}
    ).status_code == 400


def test_reenvio_aplica_limite_por_ip(client, seed, monkeypatch):
    emails = []
    monkeypatch.setattr(
        "app.routes.auth.enviar_email_confirmacao",
        lambda destinatario, nome, token: emails.append(token),
    )
    usuarios = [
        Usuario(
            nome=f"Pessoa {indice}",
            email=f"pessoa{indice}@safemask.example.com",
            senha_hash=seed["usuario"].senha_hash,
            organizacao_id=seed["organizacao"].organizacao_id,
            email_verificado=False,
        )
        for indice in range(4)
    ]
    seed["db"].add_all(usuarios)
    seed["db"].commit()

    respostas = [
        client.post(
            "/auth/reenviar-confirmacao",
            json={"email": usuario.email},
        )
        for usuario in usuarios
        for _ in range(3)
    ]

    assert all(resposta.status_code == 200 for resposta in respostas)
    assert len(emails) == 10


def test_migracao_preserva_contas_existentes_com_email_verificado():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE usuario (user_id INTEGER PRIMARY KEY, "
                    "email VARCHAR(129) NOT NULL)"
                )
            )
            conn.execute(
                text("INSERT INTO usuario (user_id, email) VALUES (1, 'legado@example.com')")
            )

        garantir_schema_autenticacao(bind=engine)

        with engine.connect() as conn:
            verificado = conn.execute(
                text("SELECT email_verificado FROM usuario WHERE user_id = 1")
            ).scalar_one()
            tabela_tokens = conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'token_confirmacao_email'"
                )
            ).scalar_one_or_none()
            tabela_pendentes = conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'cadastro_pendente'"
                )
            ).scalar_one_or_none()

        assert verificado == 1
        assert tabela_tokens == "token_confirmacao_email"
        assert tabela_pendentes == "cadastro_pendente"
    finally:
        engine.dispose()


def test_link_de_confirmacao_mantem_token_no_fragment(monkeypatch):
    emails = []
    monkeypatch.setattr(
        email_service,
        "FRONTEND_URL",
        "https://frontend.example.test",
    )
    monkeypatch.setattr(
        email_service,
        "_enviar_email_transacional",
        lambda destinatario, assunto, conteudo: emails.append(conteudo),
    )

    email_service.enviar_email_confirmacao(
        "pessoa@example.com",
        "Pessoa",
        "token-secreto",
    )

    assert "#token=token-secreto" in emails[0]
    assert "?token=token-secreto" not in emails[0]
    assert (
        "https://frontend.example.test/frontend/html/auth/confirmar_email.html"
        "#token=token-secreto"
    ) in emails[0]
    assert (
        f"Este link expira em "
        f"{email_service.EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS} horas"
    ) in emails[0]
