from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    senha = Column(String, nullable=False)


class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    descricao = Column(String, nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String, nullable=False)
    categoria = Column(String, nullable=True)

    data = Column(DateTime, server_default=func.now())