from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def gerar_hash(senha: str):
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str):
    return pwd_context.verify(senha, senha_hash)
SECRET_KEY = "monetra-chave-secreta-trocar-depois"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def criar_token(data: dict):
    dados = data.copy()
    expiracao = datetime.utcnow() + timedelta(
    minutes=ACCESS_TOKEN_EXPIRE_MINUTES
)
    dados.update({"exp": expiracao})

    return jwt.encode(
    dados,
    SECRET_KEY,
    algorithm=ALGORITHM
)

security = HTTPBearer()


def verificar_token(
    credenciais: HTTPAuthorizationCredentials = Depends(security)
):
    token = credenciais.credentials

    try:
        dados = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        usuario_id = dados.get("sub")

        if usuario_id is None:
            raise HTTPException(
                status_code=401,
                detail="Token inválido"
            )

        return int(usuario_id)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Token inválido ou expirado"
        )
    expiracao = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    dados.update({"exp": expiracao})

    return jwt.encode(
        dados,
        SECRET_KEY,
        algorithm=ALGORITHM
    )