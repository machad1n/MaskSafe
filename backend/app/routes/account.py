import io
import logging
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import ip_do_cliente, registrar
from app.core.current_user import get_current_user
from app.core.security import criar_token_jwt, hash_senha, verificar_senha
from app.database import get_db
from app.models.cadastro_pendente import CadastroPendente
from app.models.cargo import Cargo
from app.models.documentos import Documento
from app.models.log_auditoria import LogAuditoria
from app.models.token_confirmacao_email import TokenConfirmacaoEmail
from app.models.usuario import Usuario
from app.models.usuario_equipe import UsuarioEquipe
from app.schemas.account import AlteracaoSenha, ExclusaoConta, PerfilAtualizacao

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conta", tags=["Conta"])
MAX_FOTO_BYTES = 5 * 1024 * 1024
MAX_FOTO_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_FOTO_PIXELS


def _token_atualizado(usuario: Usuario) -> str:
    return criar_token_jwt({
        "sub": usuario.email,
        "nome": usuario.nome,
        "tv": usuario.token_version or 0,
    })


def _perfil(usuario: Usuario) -> dict:
    return {
        "user_id": usuario.user_id,
        "nome": usuario.nome,
        "email": usuario.email,
        "foto_url": f"/conta/foto/{usuario.user_id}" if usuario.foto_perfil else None,
    }


async def _normalizar_foto(arquivo: UploadFile) -> tuple[bytes, str]:
    if arquivo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Selecione uma imagem JPEG, PNG ou WebP.")
    conteudo = await arquivo.read(MAX_FOTO_BYTES + 1)
    if len(conteudo) > MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="A imagem deve ter no máximo 5 MB.")
    if not conteudo:
        raise HTTPException(status_code=400, detail="O arquivo de imagem está vazio.")
    try:
        imagem = Image.open(io.BytesIO(conteudo))
        if imagem.format not in {"JPEG", "PNG", "WEBP"}:
            raise HTTPException(status_code=400, detail="Formato de imagem não permitido.")
        imagem.verify()
        imagem = ImageOps.exif_transpose(Image.open(io.BytesIO(conteudo)))
        imagem.thumbnail((512, 512), Image.Resampling.LANCZOS)
        if imagem.mode not in {"RGB", "L"}:
            imagem = imagem.convert("RGB")
        elif imagem.mode == "L":
            imagem = imagem.convert("RGB")
        saida = io.BytesIO()
        imagem.save(saida, format="JPEG", quality=86, optimize=True)
        return saida.getvalue(), "image/jpeg"
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="O arquivo enviado não é uma imagem válida.") from exc


@router.get("/perfil", response_model=dict)
def obter_perfil(usuario: Usuario = Depends(get_current_user)):
    return _perfil(usuario)


@router.put("/perfil", response_model=dict)
async def atualizar_perfil(
    request: Request,
    nome: str = Form(..., min_length=1, max_length=120),
    email: str = Form(..., min_length=3, max_length=129),
    foto: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    try:
        payload = PerfilAtualizacao(nome=nome, email=email)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Informe um nome e um endereço de email válidos.") from exc

    email_normalizado = str(payload.email)
    duplicado = (
        db.query(Usuario.user_id)
        .filter(func.lower(Usuario.email) == email_normalizado.lower(), Usuario.user_id != usuario.user_id)
        .first()
    )
    if duplicado:
        raise HTTPException(status_code=409, detail="Este email já está sendo usado por outra conta.")

    nova_foto = None
    tipo_foto = None
    if foto and foto.filename:
        nova_foto, tipo_foto = await _normalizar_foto(foto)

    try:
        email_anterior = usuario.email
        usuario.nome = payload.nome
        usuario.email = email_normalizado
        if email_anterior != email_normalizado:
            db.query(TokenConfirmacaoEmail).filter(
                TokenConfirmacaoEmail.user_id == usuario.user_id
            ).delete(synchronize_session=False)
        if nova_foto is not None:
            usuario.foto_perfil = nova_foto
            usuario.foto_perfil_tipo = tipo_foto
        db.commit()
        db.refresh(usuario)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este email já está sendo usado por outra conta.") from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Falha ao atualizar perfil do usuário %s", usuario.user_id)
        raise HTTPException(status_code=500, detail="Não foi possível salvar o perfil.") from exc

    return {"perfil": _perfil(usuario), "access_token": _token_atualizado(usuario), "token_type": "bearer"}


@router.get("/foto/{user_id}")
def obter_foto(
    user_id: int,
    usuario_atual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id != usuario_atual.user_id:
        raise HTTPException(status_code=404, detail="Foto de perfil não encontrada.")
    alvo = db.query(Usuario).filter(Usuario.user_id == user_id, Usuario.is_system.is_(False)).first()
    if not alvo or not alvo.foto_perfil:
        raise HTTPException(status_code=404, detail="Foto de perfil não encontrada.")
    return Response(
        content=alvo.foto_perfil,
        media_type=alvo.foto_perfil_tipo or "image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.put("/senha", response_model=dict)
def alterar_senha(
    payload: AlteracaoSenha,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not verificar_senha(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    if payload.nova_senha != payload.confirmar_senha:
        raise HTTPException(status_code=400, detail="A confirmação da nova senha não corresponde.")
    if verificar_senha(payload.nova_senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Escolha uma senha diferente da atual.")

    usuario.senha_hash = hash_senha(payload.nova_senha)
    usuario.token_version = (usuario.token_version or 0) + 1
    db.commit()
    registrar(db, request, usuario.user_id, "alterar_senha")
    return {"mensagem": "Senha alterada com sucesso.", "access_token": _token_atualizado(usuario), "token_type": "bearer"}


@router.delete("", response_model=dict)
def excluir_conta(
    payload: ExclusaoConta,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    if not payload.confirmar:
        raise HTTPException(status_code=400, detail="Confirme a exclusão antes de continuar.")
    if not verificar_senha(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")

    if usuario.is_system:
        raise HTTPException(status_code=403, detail="Esta conta técnica não pode ser excluída por esta operação.")

    organizacao_id = usuario.organizacao_id
    email_arquivo = f"__conta_arquivada_{secrets.token_hex(12)}@safemask.invalid"
    arquivo = db.query(Usuario).filter(Usuario.email == email_arquivo).first()
    if arquivo is None:
        arquivo = Usuario(
            nome="Conta arquivada",
            email=email_arquivo,
            senha_hash=hash_senha(secrets.token_urlsafe(48)),
            organizacao_id=organizacao_id,
            is_system=True,
            email_verificado=True,
        )
        db.add(arquivo)
        try:
            db.flush()
        except Exception as exc:
            db.rollback()
            logger.exception("Falha ao criar identidade técnica para arquivamento.")
            raise HTTPException(status_code=500, detail="Não foi possível preservar o histórico da conta.") from exc

    cargo_arquivo = db.query(Cargo).filter(Cargo.nome == "membro").order_by(Cargo.nivel.asc()).first()
    if cargo_arquivo is None:
        db.rollback()
        raise HTTPException(status_code=500, detail="Não foi possível preservar os vínculos dos documentos.")

    vinculos = db.query(UsuarioEquipe).filter(UsuarioEquipe.user_id == usuario.user_id).all()
    try:
        for vinculo in vinculos:
            vinculo_arquivo = (
                db.query(UsuarioEquipe)
                .filter(
                    UsuarioEquipe.user_id == arquivo.user_id,
                    UsuarioEquipe.team_id == vinculo.team_id,
                )
                .first()
            )
            if vinculo_arquivo is None:
                vinculo_arquivo = UsuarioEquipe(
                    user_id=arquivo.user_id,
                    team_id=vinculo.team_id,
                    cargo_id=cargo_arquivo.cargo_id,
                )
                db.add(vinculo_arquivo)
                db.flush()
            db.query(Documento).filter(Documento.user_team_id == vinculo.user_team_id).update(
                {Documento.user_team_id: vinculo_arquivo.user_team_id}, synchronize_session=False
            )

        db.query(LogAuditoria).filter(LogAuditoria.user_id == usuario.user_id).update(
            {LogAuditoria.user_id: arquivo.user_id}, synchronize_session=False
        )
        db.query(TokenConfirmacaoEmail).filter(
            TokenConfirmacaoEmail.user_id == usuario.user_id
        ).delete(synchronize_session=False)
        db.query(CadastroPendente).filter(CadastroPendente.email == usuario.email).delete(
            synchronize_session=False
        )
        db.add(LogAuditoria(
            user_id=arquivo.user_id,
            acao="excluir_conta",
            ip_origem=ip_do_cliente(request),
        ))
        db.query(UsuarioEquipe).filter(UsuarioEquipe.user_id == usuario.user_id).delete(
            synchronize_session=False
        )
        db.query(Usuario).filter(Usuario.user_id == usuario.user_id).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Falha transacional ao excluir conta %s", usuario.user_id)
        raise HTTPException(status_code=500, detail="Não foi possível excluir a conta sem afetar os dados associados.") from exc

    return {"mensagem": "Sua conta foi excluída. Equipes, documentos e registros históricos foram preservados."}
