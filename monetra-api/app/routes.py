from app.categorias import CATEGORIAS_PADRAO
from app.security import gerar_hash, verificar_senha, criar_token, verificar_token
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.whatsapp.consultas import (
    buscar_transacoes,
    editar_transacao,
    excluir_transacao,
)


router = APIRouter()


@router.post("/usuarios", response_model=schemas.UsuarioResponse)
def criar_usuario(
    usuario: schemas.UsuarioCreate,
    db: Session = Depends(get_db)
):
    novo_usuario = models.Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha=gerar_hash(usuario.senha)
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


@router.post("/login")
def login(
    email: str,
    senha: str,
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == email
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Email ou senha inválidos"
        )

    if not verificar_senha(senha, usuario.senha):
        raise HTTPException(
            status_code=401,
            detail="Email ou senha inválidos"
        )

    token = criar_token({"sub": str(usuario.id)})

    return {
        "message": "Login realizado com sucesso",
        "usuario_id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/categorias")
def listar_categorias():
    """Categorias padrão da Prospere."""

    return {
        "categorias": list(CATEGORIAS_PADRAO)
    }


@router.post("/transacoes", response_model=schemas.TransacaoResponse)
def criar_transacao(
    transacao: schemas.TransacaoCreate,
    db: Session = Depends(get_db),
    usuario_id: int = Depends(verificar_token)
):
    nova_transacao = models.Transacao(
        usuario_id=usuario_id,
        descricao=transacao.descricao,
        valor=transacao.valor,
        tipo=transacao.tipo,
        categoria=transacao.categoria
    )

    db.add(nova_transacao)
    db.commit()
    db.refresh(nova_transacao)

    return nova_transacao


@router.get(
    "/transacoes",
    response_model=list[schemas.TransacaoDetalhe]
)
def historico_transacoes(
    termo: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    periodo: str | None = None,
    dias: int | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    limite: int = 50,
    usuario_id: int = Depends(verificar_token)
):
    """Histórico do usuário autenticado, com busca e filtros."""

    return buscar_transacoes(
        usuario_id,
        termo=termo,
        categoria=categoria,
        tipo=tipo,
        periodo=periodo,
        dias=dias,
        valor_min=valor_min,
        valor_max=valor_max,
        limite=max(1, min(int(limite), 200))
    )


@router.patch(
    "/transacoes/{transacao_id}",
    response_model=schemas.TransacaoDetalhe
)
def atualizar_transacao(
    transacao_id: int,
    alteracoes: schemas.TransacaoUpdate,
    usuario_id: int = Depends(verificar_token)
):
    """Altera um lançamento do próprio usuário."""

    dados = alteracoes.model_dump(
        exclude_unset=True,
        exclude_none=True
    )

    if not dados:
        raise HTTPException(
            status_code=400,
            detail="Nenhum campo para alterar foi informado."
        )

    resultado = editar_transacao(
        usuario_id,
        transacao_id,
        **dados
    )

    if not resultado["sucesso"]:

        raise HTTPException(
            status_code=(
                404
                if resultado.get("nao_encontrado")
                else 400
            ),
            detail=resultado["erro"]
        )

    return resultado["transacao"]


@router.delete("/transacoes/{transacao_id}")
def remover_transacao(
    transacao_id: int,
    usuario_id: int = Depends(verificar_token)
):
    """Exclui um lançamento do próprio usuário."""

    resultado = excluir_transacao(
        usuario_id,
        transacao_id
    )

    if not resultado["sucesso"]:

        raise HTTPException(
            status_code=(
                404
                if resultado.get("nao_encontrado")
                else 400
            ),
            detail=resultado["erro"]
        )

    return {
        "message": "Lançamento excluído.",
        "transacao": resultado["transacao"]
    }


@router.get(
    "/transacoes/{usuario_id}",
    response_model=list[schemas.TransacaoResponse]
)
def listar_transacoes(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_autenticado: int = Depends(verificar_token)
):
    if usuario_autenticado != usuario_id:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado aos dados de outro usuário."
        )

    transacoes = db.query(models.Transacao).filter(
        models.Transacao.usuario_id == usuario_id
    ).all()

    return transacoes


@router.get(
    "/minhas-transacoes",
    response_model=list[schemas.TransacaoResponse]
)
def minhas_transacoes(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(verificar_token)
):
    transacoes = db.query(models.Transacao).filter(
        models.Transacao.usuario_id == usuario_id
    ).all()

    return transacoes


@router.get("/saldo")
def consultar_saldo(
    db: Session = Depends(get_db),
    usuario_id: int = Depends(verificar_token)
):
    transacoes = db.query(models.Transacao).filter(
        models.Transacao.usuario_id == usuario_id
    ).all()

    entradas = sum(
        transacao.valor
        for transacao in transacoes
        if transacao.tipo.lower() == "entrada"
    )

    saidas = sum(
        transacao.valor
        for transacao in transacoes
        if transacao.tipo.lower() == "saida"
    )

    saldo = entradas - saidas

    return {
        "usuario_id": usuario_id,
        "total_entradas": entradas,
        "total_saidas": saidas,
        "saldo": saldo
    }


@router.get("/resumo/{usuario_id}")
def resumo_financeiro(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_autenticado: int = Depends(verificar_token)
):
    if usuario_autenticado != usuario_id:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado aos dados de outro usuário."
        )

    transacoes = db.query(models.Transacao).filter(
        models.Transacao.usuario_id == usuario_id
    ).all()

    entradas = sum(
        transacao.valor
        for transacao in transacoes
        if transacao.tipo.lower() == "entrada"
    )

    saidas = sum(
        transacao.valor
        for transacao in transacoes
        if transacao.tipo.lower() == "saida"
    )

    saldo = entradas - saidas

    categorias = {}

    for transacao in transacoes:
        if transacao.tipo.lower() == "saida":
            categoria = transacao.categoria or "Sem categoria"

            if categoria not in categorias:
                categorias[categoria] = 0

            categorias[categoria] += transacao.valor

    return {
        "usuario_id": usuario_id,
        "total_entradas": entradas,
        "total_saidas": saidas,
        "saldo": saldo,
        "despesas_por_categoria": categorias
    }
