from sqlalchemy import TIMESTAMP, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class TokenConfirmacaoEmail(Base):
    __tablename__ = "token_confirmacao_email"
    __table_args__ = (UniqueConstraint("user_id", name="uq_token_confirmacao_email_user"),)

    token_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("usuario.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    criado_em = Column(TIMESTAMP, nullable=False, server_default=func.now())
    expira_em = Column(TIMESTAMP, nullable=False)
