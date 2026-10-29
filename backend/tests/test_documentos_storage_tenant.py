"""Regressoes de isolamento e confinamento de arquivos de documentos."""
from app.core.security import criar_token_jwt
from app.models.documentos import Documento
from app.models.usuario_equipe import UsuarioEquipe
from tests.conftest import CONTEUDO_PDF


def _auth(usuario):
    return {"Authorization": f"Bearer {criar_token_jwt({'sub': usuario.email})}"}


def test_vinculo_cross_tenant_nao_lista_documento(client, seed, scanner_registrado):
    scanner_registrado([(3, 0)])
    upload = client.post(
        "/documentos/upload",
        headers=_auth(seed["usuario"]),
        files={"file": ("contrato.pdf", CONTEUDO_PDF, "application/pdf")},
        data={"titulo": "Contrato", "nivel_seguranca": "1",
              "teams": f"[{seed['equipe_a'].team_id}]"},
    )
    assert upload.status_code == 201, upload.text
    # Simula vínculo inconsistente gravado no banco: equipe da Acme para Bia/Globex.
    seed["db"].add(UsuarioEquipe(
        user_id=seed["usuario_globex"].user_id,
        team_id=seed["equipe_a"].team_id,
        cargo_id=seed["cargo_membro"].cargo_id,
    ))
    seed["db"].commit()
    resposta = client.get(
        f"/documentos/listar/{seed['equipe_a'].team_id}",
        headers=_auth(seed["usuario_globex"]),
    )
    assert resposta.status_code == 403


def test_preview_rejeita_symlink_para_fora_do_storage(client, seed, scanner_registrado, tmp_path):
    scanner_registrado([(3, 0)])
    upload = client.post(
        "/documentos/upload",
        headers=_auth(seed["usuario"]),
        files={"file": ("contrato.pdf", CONTEUDO_PDF, "application/pdf")},
        data={"titulo": "Contrato", "nivel_seguranca": "1",
              "teams": f"[{seed['equipe_a'].team_id}]"},
    )
    assert upload.status_code == 201, upload.text
    doc = seed["db"].query(Documento).filter_by(doc_id=upload.json()["doc_id"]).one()
    fora = tmp_path / "fora.pdf"
    fora.write_bytes(b"conteudo fora do storage")
    link = tmp_path / "censurados" / "escape.pdf"
    link.symlink_to(fora)
    doc.caminho_storage = str(link)
    seed["db"].commit()
    resposta = client.get(
        f"/documentos/censurados/{doc.doc_id}/arquivo",
        headers=_auth(seed["usuario"]),
    )
    assert resposta.status_code == 404
