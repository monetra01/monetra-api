from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr

    class Config:
        from_attributes = True


class TransacaoCreate(BaseModel):
    descricao: str
    valor: float = Field(gt=0)
    tipo: str
    categoria: str | None = None


class TransacaoUpdate(BaseModel):
    descricao: str | None = None
    valor: float | None = Field(default=None, gt=0)
    tipo: str | None = None
    categoria: str | None = None
    data: datetime | None = None


class TransacaoResponse(BaseModel):
    id: int
    usuario_id: int
    descricao: str
    valor: float
    tipo: str
    categoria: str | None
    data: datetime | None = None

    class Config:
        from_attributes = True


class TransacaoDetalhe(BaseModel):
    """Lançamento no formato do histórico da Prospere."""

    id: int
    descricao: str
    valor: float
    tipo: str
    categoria: str | None
    data: datetime | None = None
