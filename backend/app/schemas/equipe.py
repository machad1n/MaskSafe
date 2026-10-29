from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EquipeBase(BaseModel):
    nome: str
    descricao: str | None = None


class EquipeCreate(EquipeBase):
    membros_ids: list[int] = Field(default_factory=list)


class EquipeUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None


class EquipeMemberAdd(BaseModel):
    user_id: int
    cargo_id: int | None = None


class EquipeMemberUpdate(BaseModel):
    cargo_id: int


class EquipeMemberResponse(BaseModel):
    user_team_id: int
    user_id: int
    nome: str
    email: str
    cargo_nome: str
    cargo_nivel: int
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class EquipeDetailResponse(BaseModel):
    team_id: int
    nome: str
    descricao: str | None = None
    criado_em: datetime
    membros: int
    documentos: int
    membros_lista: list[EquipeMemberResponse]

    model_config = ConfigDict(from_attributes=True)
