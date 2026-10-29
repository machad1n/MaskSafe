from sqlalchemy import TIMESTAMP, Column, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class CadastroPendente(Base):
    __tablename__ = "cadastro_pendente"

    cadastro_id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(129), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    criado_em = Column(TIMESTAMP, nullable=False, server_default=func.now())
    expira_em = Column(TIMESTAMP, nullable=False)
    reenvios_janela_inicio = Column(TIMESTAMP, nullable=False, server_default=func.now())
    reenvios_na_janela = Column(Integer, nullable=False, default=0, server_default="0")
