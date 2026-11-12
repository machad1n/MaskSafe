import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core import tenancy
from app.core.audit import (
    ACAO_CADASTRO,
    ACAO_LOGIN,
    ACAO_LOGIN_BLOQUEADO,
    ACAO_LOGIN_FALHO,
    ACAO_REENVIO_CONFIRMAR_EMAIL,
    ACAO_RESET_SENHA,
    ACAO_RESET_SENHA_SOLICITACAO,
    ip_do_cliente,
    registrar,
)
from app.core.config import (
    EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS,
    RESET_TOKEN_EXPIRE_MINUTES,
)
from app.core.current_user import get_current_user
from app.core.email import enviar_email_confirmacao, enviar_email_recuperacao
from app.core.security import (
    TIPO_RESET,
    criar_token_jwt,
    criar_token_jwt_com_expiry,
    hash_senha,
    verificar_senha,
)
from app.database import get_db
from app.models.cadastro_pendente import CadastroPendente
from app.models.cargo import Cargo
from app.models.equipe import Equipe
from app.models.log_auditoria import LogAuditoria
from app.models.token_confirmacao_email import TokenConfirmacaoEmail
from app.models.usuario import Usuario
from app.models.usuario_equipe import UsuarioEquipe
from app.schemas.auth import ConfirmarEmailRequest, RecuperarSenhaRequest, ResetSenhaRequest
from app.schemas.usuario import UsuarioCreate, UsuarioLogin

router = APIRouter(prefix="/auth", tags=["Autenticação"])
logger = logging.getLogger(__name__)

# Limite de tentativas de login. Sem isso, `/auth/login` unlimited + senha
# fraca = credential stuffing. Contagem por e-mail E por IP: uma delas cobre
# o ataque distribuido, a outra o alvo concentrado.
# E-mail da conta que absorve tentativas de login sem cadastro,
# porque `log_auditoria.user_id` nao aceita nulo.
_EMAIL_SENTINEL = "__login_desconhecido__@safemask.invalid"

MAX_TENTATIVAS_LOGIN = 5
JANELA_TENTATIVAS_MINUTOS = 15
JANELA_REENVIO_CONFIRMAR_EMAIL_MINUTOS = 60
MAX_REENVIOS_CONFIRMAR_EMAIL_USUARIO = 3
MAX_REENVIOS_CONFIRMAR_EMAIL_IP = 10
MENSAGEM_REENVIO_CONFIRMAR_EMAIL = (
    "Solicitação recebida. Se este endereço estiver cadastrado e pendente de "
    "confirmação, enviaremos um novo link. Verifique sua caixa de entrada e "
    "a pasta de spam; se já confirmou o email, faça login."
)
MENSAGEM_CADASTRO_PENDENTE = (
    "Solicitação de cadastro recebida. Verifique sua caixa de entrada e confirme "
    "o email para criar sua conta. Se a mensagem não chegar, solicite um novo link."
)

# Hash descartavel de senha cualquiera. Faz o bcrypt rodar no caminho de
# "usuario nao encontrado" para que o tempo de resposta nao diferencie os dois.
_HASH_SENHA_QUALQUER = hash_senha("senha-que-nao-existe")


def _registrar_login_falho(
    db: Session, request: Request, user_id: int | None
) -> None:
    """Grava a tentativa falhada, inclusive para e-mail inexistente.

    `log_auditoria.user_id` tem FK NOT NULL, então o e-mail desconhecido não
    tem linha onde se apoiar. Para continuar contando tentativas por e-mail,
    a tentativa orfa é gravada na conta sentinel `-1`, criada uma vez.
    """
    alvo = user_id
    try:
        if alvo is None:
            sentinel = db.query(Usuario).filter(Usuario.email == _EMAIL_SENTINEL).first()
            if sentinel is None:
                sentinel = Usuario(
                    nome="__tentativa_desconhecida__",
                    email=_EMAIL_SENTINEL,
                    senha_hash=_HASH_SENHA_QUALQUER,
                    is_system=True,
                )
                db.add(sentinel)
                db.flush()
            alvo = sentinel.user_id

        db.add(LogAuditoria(
            user_id=alvo,
            acao=ACAO_LOGIN_FALHO,
            ip_origem=ip_do_cliente(request),
            data_hora=datetime.utcnow(),
        ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Falha ao registrar tentativa de login.")


def _excedeu_tentativas(
    db: Session, request: Request, user_id: int | None
) -> bool:
    """True se o par (e-mail, IP) estourou o limite dentro da janela.

    Falhas anteriores a um login bem-sucedido nao contam. Sem isso, quem
    digita a senha errada duas vezes, acerta na terceira e digita errado de
    novo cinco vezes na mesma hora fica trancado fora da propria conta. O
    `log_auditoria` continua append-only: o corte e por janela de tempo, nao
    apagando registro.
    """
    desde = datetime.utcnow() - timedelta(minutes=JANELA_TENTATIVAS_MINUTOS)
    ip = ip_do_cliente(request)

    filtros = [
        LogAuditoria.acao == ACAO_LOGIN_FALHO,
        LogAuditoria.data_hora >= desde,
    ]
    if user_id is not None:
        ultimo_sucesso = (
            select(func.max(LogAuditoria.data_hora))
            .where(
                LogAuditoria.acao == ACAO_LOGIN,
                LogAuditoria.user_id == user_id,
            )
            .scalar_subquery()
        )
        desde = case((ultimo_sucesso > desde, ultimo_sucesso), else_=desde)
        filtros[1] = LogAuditoria.data_hora >= desde
        filtros.append(or_(LogAuditoria.user_id == user_id, LogAuditoria.ip_origem == ip))
    else:
        filtros.append(LogAuditoria.ip_origem == ip)

    falhas = db.query(func.count(LogAuditoria.log_id)).filter(*filtros).scalar() or 0
    return falhas > MAX_TENTATIVAS_LOGIN


def cargo_efetivo(db: Session, user_id: int, organizacao_id: int | None = None) -> dict | None:
    """Cargo de maior nivel do usuario entre as equipes da organizacao.

    O papel viaja na resposta do login para o frontend montar o menu. Como um
    usuario pode estar em varias equipes com cargos diferentes, vale o maior
    nivel: esconder itens do menu e cosmético, a autorizacao real acontece em
    cada endpoint.

    Quando `organizacao_id` vem informado, os vinculos de outras organizacoes
    sao ignorados: o papel de um tenant nao pode conceder acesso em outro.
    """
    consulta = (
        db.query(Cargo.nome, Cargo.nivel)
        .join(UsuarioEquipe, UsuarioEquipe.cargo_id == Cargo.cargo_id)
        .filter(UsuarioEquipe.user_id == user_id)
    )
    if organizacao_id is not None:
        consulta = consulta.join(
            Equipe, Equipe.team_id == UsuarioEquipe.team_id
        ).filter(Equipe.organizacao_id == organizacao_id)

    linha = consulta.order_by(Cargo.nivel.desc()).first()
    if not linha:
        return None
    return {"nome": linha.nome, "nivel": linha.nivel}


def identidade(db: Session, usuario: Usuario) -> dict:
    cargo = cargo_efetivo(db, usuario.user_id, usuario.organizacao_id)
    return {
        "user_id": usuario.user_id,
        "nome": usuario.nome,
        "email": usuario.email,
        "organizacao_id": usuario.organizacao_id,
        "organizacao_nome": usuario.organizacao.nome if usuario.organizacao else None,
        # Sem equipe o usuario ainda autenticou, mas nao ha papel para o menu.
        "cargo": cargo["nome"] if cargo else None,
        "nivel": cargo["nivel"] if cargo else 0,
    }


def _criar_token_confirmacao(db: Session, usuario: Usuario) -> str:
    token = secrets.token_urlsafe(32)
    registro = TokenConfirmacaoEmail(
        user_id=usuario.user_id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        expira_em=datetime.utcnow() + timedelta(hours=EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS),
    )
    db.query(TokenConfirmacaoEmail).filter(
        TokenConfirmacaoEmail.user_id == usuario.user_id
    ).delete(synchronize_session=False)
    db.add(registro)
    db.commit()
    return token


def _criar_token_cadastro_pendente(db: Session, cadastro: CadastroPendente) -> str:
    token = secrets.token_urlsafe(32)
    cadastro.token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cadastro.expira_em = datetime.utcnow() + timedelta(
        hours=EMAIL_CONFIRMATION_TOKEN_EXPIRE_HOURS
    )
    db.add(cadastro)
    db.commit()
    return token


def _cadastro_pendente_reenvio_limitado(
    cadastro: CadastroPendente, agora: datetime
) -> bool:
    inicio_janela = cadastro.reenvios_janela_inicio or cadastro.criado_em
    if inicio_janela <= agora - timedelta(
        minutes=JANELA_REENVIO_CONFIRMAR_EMAIL_MINUTOS
    ):
        cadastro.reenvios_janela_inicio = agora
        cadastro.reenvios_na_janela = 0
    return cadastro.reenvios_na_janela >= MAX_REENVIOS_CONFIRMAR_EMAIL_USUARIO


def _usuario_sentinela(db: Session) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.email == _EMAIL_SENTINEL).first()
    if usuario:
        return usuario

    usuario = Usuario(
        nome="__tentativa_desconhecida__",
        email=_EMAIL_SENTINEL,
        senha_hash=_HASH_SENHA_QUALQUER,
        is_system=True,
    )
    db.add(usuario)
    try:
        db.commit()
    except Exception:
        db.rollback()
        usuario = db.query(Usuario).filter(Usuario.email == _EMAIL_SENTINEL).first()
        if not usuario:
            raise
    return usuario


def _reenvio_confirmacao_limitado(
    db: Session, request: Request, usuario: Usuario | None
) -> bool:
    desde = datetime.utcnow() - timedelta(
        minutes=JANELA_REENVIO_CONFIRMAR_EMAIL_MINUTOS
    )
    ip = ip_do_cliente(request)
    tentativas_ip = (
        db.query(func.count(LogAuditoria.log_id))
        .filter(
            LogAuditoria.acao == ACAO_REENVIO_CONFIRMAR_EMAIL,
            LogAuditoria.ip_origem == ip,
            LogAuditoria.data_hora >= desde,
        )
        .scalar()
        or 0
    )
    if tentativas_ip >= MAX_REENVIOS_CONFIRMAR_EMAIL_IP:
        return True

    if usuario and usuario.email != _EMAIL_SENTINEL:
        tentativas_email = (
            db.query(func.count(LogAuditoria.log_id))
            .filter(
                LogAuditoria.acao == ACAO_REENVIO_CONFIRMAR_EMAIL,
                LogAuditoria.user_id == usuario.user_id,
                LogAuditoria.data_hora >= desde,
            )
            .scalar()
            or 0
        )
        if tentativas_email >= MAX_REENVIOS_CONFIRMAR_EMAIL_USUARIO:
            return True

    return False


# Autenticação compartilhada pelos formatos JSON e form-encoded.
def _autenticar(request: Request, credenciais: UsuarioLogin, db: Session) -> dict:
    usuario = (
        db.query(Usuario)
        .options(joinedload(Usuario.organizacao))
        .filter(Usuario.email == credenciais.email)
        .first()
    )
    if _excedeu_tentativas(db, request, usuario.user_id if usuario else None):
        # Mesmo sob bloqueio, mantenha custo semelhante para emails existentes
        # e inexistentes: o limite por IP tambem pode atingir contas desconhecidas.
        hash_alvo = usuario.senha_hash if usuario else _HASH_SENHA_QUALQUER
        verificar_senha(credenciais.senha_hash, hash_alvo)
        if usuario:
            registrar(db, request, usuario.user_id, ACAO_LOGIN_BLOQUEADO)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Aguarde alguns minutos.",
        )

    # O bcrypt também roda para contas inexistentes, evitando enumeração por tempo.
    if usuario is None or usuario.is_system:
        verificar_senha(credenciais.senha_hash, _HASH_SENHA_QUALQUER)
        _registrar_login_falho(db, request, usuario.user_id if usuario else None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verificar_senha(credenciais.senha_hash, usuario.senha_hash):
        _registrar_login_falho(db, request, usuario.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    identidade_usuario = identidade(db, usuario)
    token = criar_token_jwt(
        {"sub": usuario.email, "nome": usuario.nome, "tv": usuario.token_version or 0}
    )
    registrar(db, request, usuario.user_id, ACAO_LOGIN, data_hora=datetime.utcnow())
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": identidade_usuario,
    }


# A rota JSON é mantida para compatibilidade com clientes existentes.
@router.post("/login", response_model=dict)
def login(
    request: Request,
    credenciais: UsuarioLogin,
    db: Session = Depends(get_db),
):
    return _autenticar(request, credenciais, db)


@router.get("/me", response_model=dict)
async def me(
    usuario_atual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Identidade e cargo do portador do token.

    Permite reidratar a sessao (por exemplo apos um deploy) sem refazer login.
    """
    return identidade(db, usuario_atual)

def _cadastrar(request: Request, usuario: UsuarioCreate, db: Session) -> dict:
    """Cria conta, organização, equipe e auditoria em uma única transação."""
    if db.query(Usuario).filter(Usuario.email == usuario.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado.",
        )

    cargo_lider = db.query(Cargo).filter(Cargo.nome == "lider").first()
    if not cargo_lider:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cargo 'lider' não encontrado.",
        )

    cargo_lider_id = cargo_lider.cargo_id
    # Fecha a transação somente de leitura antes do bcrypt: o custo de hash não
    # deve manter conexão/transação SQL ocupada por centenas de milissegundos.
    db.rollback()
    senha_hash = hash_senha(usuario.senha_hash)

    try:
        organizacao = tenancy.criar(db, f"Organização de {usuario.nome}")
        novo_usuario = Usuario(
            nome=usuario.nome,
            email=usuario.email,
            senha_hash=senha_hash,
            organizacao_id=organizacao.organizacao_id,
            email_verificado=True,
            criado_em=datetime.utcnow(),
        )
        equipe = Equipe(
            nome="Minha equipe",
            organizacao_id=organizacao.organizacao_id,
            criado_em=datetime.utcnow(),
        )
        db.add_all([novo_usuario, equipe])
        db.flush()
        novo_user_id = novo_usuario.user_id
        db.add(
            UsuarioEquipe(
                user_id=novo_user_id,
                team_id=equipe.team_id,
                cargo_id=cargo_lider_id,
                criado_em=datetime.utcnow(),
            )
        )
        # Se havia uma solicitação antiga não confirmada para o mesmo email,
        # ela não pode permanecer reservando o endereço após o cadastro direto.
        db.query(CadastroPendente).filter(
            CadastroPendente.email == usuario.email
        ).delete(synchronize_session=False)
        # Registro de auditoria persiste atomicamente com a conta, sem um
        # segundo commit/rede após criar os dados de negócio.
        db.add(LogAuditoria(
            user_id=novo_user_id,
            acao=ACAO_CADASTRO,
            ip_origem=ip_do_cliente(request),
        ))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        # Restrição UNIQUE do email também protege a corrida entre cadastros.
        if db.query(Usuario).filter(Usuario.email == usuario.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado.",
            ) from exc
        logger.exception("Falha transacional ao criar conta.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível concluir o cadastro.",
        ) from None

    return {
        "mensagem": "Conta criada com sucesso. Você já pode entrar.",
        "user_id": novo_user_id,
    }


# Rota JSON preservada para clientes já integrados.
@router.post("/cadastro", status_code=status.HTTP_201_CREATED)
def cadastrar(
    request: Request,
    usuario: UsuarioCreate,
    db: Session = Depends(get_db),
):
    return _cadastrar(request, usuario, db)


@router.post("/confirmar-email")
async def confirmar_email(
    request: Request,
    payload: ConfirmarEmailRequest,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    cadastro = (
        db.query(CadastroPendente)
        .filter(
            CadastroPendente.token_hash == token_hash,
            CadastroPendente.expira_em > datetime.utcnow(),
        )
        .with_for_update()
        .first()
    )
    if cadastro:
        if db.query(Usuario).filter(Usuario.email == cadastro.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Link de confirmação inválido ou expirado.",
            )

        cargo_lider = db.query(Cargo).filter(Cargo.nome == "lider").first()
        if not cargo_lider:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cargo 'lider' não encontrado.",
            )

        nome = cadastro.nome
        email = cadastro.email
        organizacao = tenancy.criar(db, f"Organização de {nome}")
        db.flush()
        usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=cadastro.senha_hash,
            organizacao_id=organizacao.organizacao_id,
            email_verificado=True,
            criado_em=datetime.utcnow(),
        )
        db.add(usuario)
        db.flush()

        equipe = Equipe(
            nome="Minha equipe",
            organizacao_id=organizacao.organizacao_id,
            criado_em=datetime.utcnow(),
        )
        db.add(equipe)
        db.flush()
        db.add(
            UsuarioEquipe(
                user_id=usuario.user_id,
                team_id=equipe.team_id,
                cargo_id=cargo_lider.cargo_id,
                criado_em=datetime.utcnow(),
            )
        )
        db.delete(cadastro)
        db.commit()

        registrar(db, request, usuario.user_id, ACAO_CADASTRO)
        return {"mensagem": "Email confirmado e conta criada. Você já pode entrar."}

    registro = (
        db.query(TokenConfirmacaoEmail)
        .filter(
            TokenConfirmacaoEmail.token_hash == token_hash,
            TokenConfirmacaoEmail.expira_em > datetime.utcnow(),
        )
        .with_for_update()
        .first()
    )
    if not registro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de confirmação inválido ou expirado.",
        )

    usuario = db.query(Usuario).filter(Usuario.user_id == registro.user_id).first()
    if not usuario:
        db.delete(registro)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de confirmação inválido ou expirado.",
        )

    usuario.email_verificado = True
    db.delete(registro)
    db.commit()
    return {"mensagem": "Email confirmado. Você já pode entrar na sua conta."}


@router.post("/reenviar-confirmacao")
async def reenviar_confirmacao(
    request: Request,
    dados: RecuperarSenhaRequest,
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    cadastro = db.query(CadastroPendente).filter(
        CadastroPendente.email == dados.email
    ).first()
    usuario_auditoria = usuario or _usuario_sentinela(db)

    agora = datetime.utcnow()
    limite_pendente = (
        cadastro is not None
        and _cadastro_pendente_reenvio_limitado(cadastro, agora)
    )
    if _reenvio_confirmacao_limitado(
        db, request, usuario if usuario and not usuario.email_verificado else None
    ) or limite_pendente:
        return {"mensagem": MENSAGEM_REENVIO_CONFIRMAR_EMAIL}

    if cadastro and not usuario:
        cadastro.reenvios_na_janela += 1
        token = _criar_token_cadastro_pendente(db, cadastro)
        usuario_auditoria = _usuario_sentinela(db)
        registrar(db, request, usuario_auditoria.user_id, ACAO_REENVIO_CONFIRMAR_EMAIL)
        try:
            enviar_email_confirmacao(cadastro.email, cadastro.nome, token)
        except Exception:
            logger.exception("Falha ao reenviar confirmação de email.")
        return {"mensagem": MENSAGEM_REENVIO_CONFIRMAR_EMAIL}

    registrar(db, request, usuario_auditoria.user_id, ACAO_REENVIO_CONFIRMAR_EMAIL)

    if not usuario or usuario.email_verificado:
        return {"mensagem": MENSAGEM_REENVIO_CONFIRMAR_EMAIL}

    token = _criar_token_confirmacao(db, usuario)
    try:
        enviar_email_confirmacao(usuario.email, usuario.nome, token)
    except Exception:
        logger.exception("Falha ao reenviar confirmação de email.")

    return {"mensagem": MENSAGEM_REENVIO_CONFIRMAR_EMAIL}


@router.post("/recuperar-senha")
async def recuperar_senha(
    request: Request,
    dados: RecuperarSenhaRequest,
    db: Session = Depends(get_db),
):
    """Envia as instrucoes de recuperacao.

    A resposta e sempre a mesma, exista o email ou nao: responder 404 para um
    cadastro desconhecido permitiria enumerar quem usa o sistema.
    """
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario:
        return {
            "mensagem": "Se o email estiver cadastrado, você receberá instruções de recuperação."
        }

    try:
        registrar(db, request, usuario.user_id, ACAO_RESET_SENHA_SOLICITACAO)
        token = criar_token_jwt_com_expiry(
            {"sub": usuario.email, "tv": usuario.token_version or 0},
            minutes=RESET_TOKEN_EXPIRE_MINUTES,
        )
        enviar_email_recuperacao(usuario.email, usuario.nome, token)
    except Exception:
        logger.exception("Falha ao processar solicitação de recuperação de senha.")

    return {"mensagem": "Se o email estiver cadastrado, você receberá instruções de recuperação."}


@router.post('/reset-senha')
async def reset_senha(request: Request, payload: ResetSenhaRequest, db: Session = Depends(get_db)):
    token = payload.token
    nova_senha = payload.senha

    try:
        # Decodifica o token para obter o email
        from jose import jwt
        from jose.exceptions import ExpiredSignatureError

        from app.core.security import ALGORITHM, SECRET_KEY

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Um access token decodifica aqui igual. Sem o `typ`, o token de sessao
        # da vitima — que anda no localStorage e vaza em qualquer XSS — viraria
        # senha permanente.
        if decoded.get("typ") != TIPO_RESET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido.",
            )

        email = decoded.get('sub')
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Token inválido.')

        versao_token = decoded.get("tv", 0)
        if type(versao_token) is not int:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Token inválido.')

        usuario = db.query(Usuario).filter(Usuario.email == email).first()
        if not usuario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuário não encontrado.')

        # A atualização condicional consome o token uma única vez, mesmo se
        # duas requisições tentarem usar a mesma versão simultaneamente.
        atualizados = (
            db.query(Usuario)
            .filter(
                Usuario.user_id == usuario.user_id,
                Usuario.token_version == versao_token,
            )
            .update(
                {
                    Usuario.senha_hash: hash_senha(nova_senha),
                    Usuario.token_version: versao_token + 1,
                },
                synchronize_session=False,
            )
        )
        if atualizados != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido ou já utilizado.",
            )

        db.commit()

        registrar(db, request, usuario.user_id, ACAO_RESET_SENHA)

        return {'mensagem': 'Senha atualizada com sucesso.'}
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado."
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Token inválido ou erro ao redefinir a senha.') from exc
