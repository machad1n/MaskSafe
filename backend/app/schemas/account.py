import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class PerfilAtualizacao(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr

    @field_validator("nome")
    @classmethod
    def nome_nao_vazio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O nome é obrigatório.")
        return value


class AlteracaoSenha(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=72)
    confirmar_senha: str = Field(min_length=8, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def validar_forca(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("A nova senha deve ter no máximo 72 bytes.")
        if not re.search(r"[a-z]", value):
            raise ValueError("A nova senha deve conter ao menos uma letra minúscula.")
        if not re.search(r"[A-Z]", value):
            raise ValueError("A nova senha deve conter ao menos uma letra maiúscula.")
        if not re.search(r"\d", value):
            raise ValueError("A nova senha deve conter ao menos um número.")
        return value


class ExclusaoConta(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    confirmar: bool
