from pydantic import BaseModel, EmailStr


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
    valor: float
    tipo: str
    categoria: str | None = None


class TransacaoResponse(BaseModel):
    id: int
    usuario_id: int
    descricao: str
    valor: float
    tipo: str
    categoria: str | None