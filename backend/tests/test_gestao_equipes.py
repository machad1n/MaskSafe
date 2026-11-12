from app.core.security import criar_token_jwt
from app.models.documentos import Documento
from app.models.equipe import Equipe
from app.models.usuario import Usuario
from app.models.usuario_equipe import UsuarioEquipe


def auth(user):
    return {"Authorization": f"Bearer {criar_token_jwt({'sub': user.email, 'nome': user.nome})}"}


def test_editar_equipe_e_adicionar_remover_membro(client, seed):
    db = seed["db"]
    # Ana já é líder da equipe A; cria outro usuário no mesmo tenant.
    user = Usuario(
        nome="Caio",
        email="caio@acme.test",
        senha_hash="x",
        organizacao_id=seed["organizacao"].organizacao_id,
    )
    db.add(user)
    db.commit()
    headers = auth(seed["usuario"])
    tid = seed["equipe_a"].team_id

    response = client.patch(
        f"/equipes/{tid}",
        json={"nome": "Equipe Renomeada", "descricao": "Atualizada"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["equipe"]["nome"] == "Equipe Renomeada"

    response = client.post(
        f"/equipes/{tid}/membros",
        json={"user_id": user.user_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    link_id = response.json()["user_team_id"]
    assert client.delete(f"/equipes/{tid}/membros/{link_id}", headers=headers).status_code == 200


def test_busca_candidatos_equipa_exclui_apenas_membros_da_equipe(client, seed):
    db = seed["db"]
    org_id = seed["organizacao"].organizacao_id
    user_atual = Usuario(
        nome="Ja na equipe",
        email="ja-na-equipe@acme.test",
        senha_hash="x",
        organizacao_id=org_id,
    )
    user_outra_equipe = Usuario(
        nome="Outra equipe",
        email="outra-equipe@acme.test",
        senha_hash="x",
        organizacao_id=org_id,
    )
    user_disponivel = Usuario(
        nome="Disponivel",
        email="disponivel@acme.test",
        senha_hash="x",
        organizacao_id=org_id,
    )
    db.add_all([user_atual, user_outra_equipe, user_disponivel])
    db.flush()
    db.add_all([
        UsuarioEquipe(
            user_id=user_atual.user_id,
            team_id=seed["equipe_a"].team_id,
            cargo_id=seed["cargo_membro"].cargo_id,
        ),
        UsuarioEquipe(
            user_id=user_outra_equipe.user_id,
            team_id=seed["equipe_b"].team_id,
            cargo_id=seed["cargo_membro"].cargo_id,
        ),
    ])
    db.commit()

    response = client.get(
        f"/equipes/form-data?team_id={seed['equipe_a'].team_id}",
        headers=auth(seed["usuario"]),
    )

    assert response.status_code == 200, response.text
    candidate_ids = {user["user_id"] for user in response.json()["usuarios_disponiveis"]}
    assert user_atual.user_id not in candidate_ids
    assert user_outra_equipe.user_id in candidate_ids
    assert user_disponivel.user_id in candidate_ids


def test_form_data_expoe_cargos_para_edicao_no_modal(client, seed):
    response = client.get(
        f"/equipes/form-data?team_id={seed['equipe_a'].team_id}",
        headers=auth(seed["usuario"]),
    )

    assert response.status_code == 200, response.text
    cargos = response.json()["cargos_disponiveis"]
    cargo_ids = {cargo["cargo_id"] for cargo in cargos}
    assert seed["cargo_membro"].cargo_id in cargo_ids
    assert seed["cargo_lider"].cargo_id in cargo_ids


def test_operacoes_equipes_negam_membro_comum_e_isolam_tenant(client, seed):
    db = seed["db"]
    member = Usuario(
        nome="Membro",
        email="membro@acme.test",
        senha_hash="x",
        organizacao_id=seed["organizacao"].organizacao_id,
    )
    db.add(member)
    db.flush()
    db.add(
        UsuarioEquipe(
            user_id=member.user_id,
            team_id=seed["equipe_a"].team_id,
            cargo_id=seed["cargo_membro"].cargo_id,
        )
    )
    db.commit()
    headers = auth(member)
    assert client.patch(
        f"/equipes/{seed['equipe_a'].team_id}",
        json={"nome": "X"},
        headers=headers,
    ).status_code == 403
    assert client.patch(
        f"/equipes/{seed['equipe_globex'].team_id}",
        json={"nome": "X"},
        headers=auth(seed["usuario"]),
    ).status_code == 404


def test_exclusao_e_remocao_bloqueiam_documento_vinculado(client, seed, documento):
    db = seed["db"]
    doc = documento(seed["user_team_a"])
    db.add(doc)
    db.commit()
    headers = auth(seed["usuario"])
    assert client.delete(
        f"/equipes/{seed['equipe_a'].team_id}", headers=headers
    ).status_code == 409
    assert client.delete(
        f"/equipes/{seed['equipe_a'].team_id}/membros/{seed['user_team_a']}",
        headers=headers,
    ).status_code == 409
    assert db.query(Documento).filter_by(doc_id=doc.doc_id).count() == 1
    assert db.query(UsuarioEquipe).filter_by(user_team_id=seed["user_team_a"]).count() == 1


def test_exclusao_sem_documentos_tem_sucesso(client, seed):
    headers = auth(seed["usuario"])
    # Eleva o cargo de Ana apenas para validar exclusão autorizada sem documentos.
    link = seed["db"].query(UsuarioEquipe).filter_by(user_team_id=seed["user_team_b"]).one()
    link.cargo_id = seed["cargo_lider"].cargo_id
    seed["db"].commit()
    team_id = seed["equipe_b"].team_id
    assert client.delete(f"/equipes/{team_id}", headers=headers).status_code == 200
    assert seed["db"].query(Equipe).filter_by(team_id=team_id).count() == 0
