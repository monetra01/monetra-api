from datetime import datetime, timedelta

from app.categorias import normalizar_categoria
from app.database import SessionLocal
from app import models
from app.texto import normalizar_texto


# =========================================================
# SERIALIZAÇÃO
# =========================================================

def serializar_transacao(transacao) -> dict:
    """Formato único de lançamento usado pela IA, pelo WhatsApp e pela API."""

    return {
        "id": transacao.id,
        "descricao": transacao.descricao,
        "valor": float(transacao.valor),
        "tipo": transacao.tipo,
        "categoria": normalizar_categoria(transacao.categoria),
        "data": (
            transacao.data.isoformat()
            if transacao.data
            else None
        ),
    }


def serializar_transacoes(transacoes) -> list[dict]:
    return [
        serializar_transacao(transacao)
        for transacao in transacoes
    ]


# =========================================================
# PERÍODOS
# =========================================================

PERIODOS = ("dia", "semana", "mes", "ano")


def limites_periodo(periodo: str):
    """Início (inclusivo) e fim (exclusivo) do período atual."""

    agora = datetime.now()

    inicio_hoje = datetime(
        agora.year,
        agora.month,
        agora.day,
    )

    if periodo == "dia":
        return inicio_hoje, inicio_hoje + timedelta(days=1)

    if periodo == "semana":
        inicio_semana = inicio_hoje - timedelta(
            days=inicio_hoje.weekday()
        )
        return inicio_semana, inicio_semana + timedelta(days=7)

    if periodo == "ano":
        return (
            datetime(agora.year, 1, 1),
            datetime(agora.year + 1, 1, 1),
        )

    inicio_proximo_mes = (
        datetime(agora.year + 1, 1, 1)
        if agora.month == 12
        else datetime(agora.year, agora.month + 1, 1)
    )

    return (
        datetime(agora.year, agora.month, 1),
        inicio_proximo_mes,
    )


# =========================================================
# CONSULTAS
# =========================================================

def consultar_saldo(usuario_id: int):
    db = SessionLocal()
    try:
        transacoes = (
            db.query(models.Transacao)
            .filter(models.Transacao.usuario_id == usuario_id)
            .all()
        )

        entradas = sum(
            float(t.valor)
            for t in transacoes
            if t.tipo.lower() == "entrada"
        )

        saidas = sum(
            float(t.valor)
            for t in transacoes
            if t.tipo.lower() == "saida"
        )

        return {
            "saldo": entradas - saidas,
            "total_entradas": entradas,
            "total_saidas": saidas,
        }

    finally:
        db.close()


def consultar_periodo(usuario_id: int, periodo: str = "mes"):
    """Entradas, saídas e saldo do período atual (dia, semana, mês ou ano)."""

    inicio, fim = limites_periodo(periodo)

    db = SessionLocal()
    try:
        transacoes = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.usuario_id == usuario_id,
                models.Transacao.data >= inicio,
                models.Transacao.data < fim,
            )
            .all()
        )

    finally:
        db.close()

    entradas = 0.0
    saidas = 0.0

    for transacao in transacoes:

        valor = float(transacao.valor)

        if (transacao.tipo or "").lower() == "entrada":
            entradas += valor
        else:
            saidas += valor

    return {
        "periodo": periodo,
        "inicio": inicio.date().isoformat(),
        "fim": fim.date().isoformat(),
        "total_entradas": entradas,
        "total_saidas": saidas,
        "saldo": entradas - saidas,
    }


def consultar_ultimas_transacoes(usuario_id: int, limite: int = 5):
    db = SessionLocal()
    try:
        return (
            db.query(models.Transacao)
            .filter(models.Transacao.usuario_id == usuario_id)
            .order_by(models.Transacao.id.desc())
            .limit(limite)
            .all()
        )

    finally:
        db.close()


def consultar_gastos_mes(usuario_id: int):
    db = SessionLocal()
    try:
        agora = datetime.now()

        inicio_mes = datetime(
            agora.year,
            agora.month,
            1,
        )

        inicio_proximo_mes = (
            datetime(agora.year + 1, 1, 1)
            if agora.month == 12
            else datetime(
                agora.year,
                agora.month + 1,
                1,
            )
        )

        gastos = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.usuario_id == usuario_id,
                models.Transacao.tipo.ilike("saida"),
                models.Transacao.data >= inicio_mes,
                models.Transacao.data < inicio_proximo_mes,
            )
            .all()
        )

        return float(
            sum(t.valor for t in gastos)
        )

    finally:
        db.close()


def consultar_gastos_por_categoria(usuario_id: int):
    db = SessionLocal()
    try:
        transacoes = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.usuario_id == usuario_id,
                models.Transacao.tipo.ilike("saida"),
            )
            .all()
        )

        categorias = {}

        for t in transacoes:
            categoria = normalizar_categoria(t.categoria)

            categorias[categoria] = (
                categorias.get(categoria, 0)
                + float(t.valor)
            )

        return categorias

    finally:
        db.close()


def consultar_gasto_categoria(
    usuario_id: int,
    categoria: str,
    periodo: str | None = None,
    dias: int | None = None,
):
    """Total gasto numa categoria, com filtro opcional de período ou dias."""

    categoria_buscada = normalizar_categoria(categoria)

    db = SessionLocal()
    try:
        consulta = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.usuario_id == usuario_id,
                models.Transacao.tipo.ilike("saida"),
            )
        )

        if periodo:
            inicio, fim = limites_periodo(periodo)

            consulta = consulta.filter(
                models.Transacao.data >= inicio,
                models.Transacao.data < fim,
            )

        elif dias:
            consulta = consulta.filter(
                models.Transacao.data
                >= datetime.now() - timedelta(days=dias)
            )

        transacoes = consulta.all()

    finally:
        db.close()

    total = 0.0
    quantidade = 0

    for transacao in transacoes:

        if normalizar_categoria(transacao.categoria) == categoria_buscada:
            total += float(transacao.valor)
            quantidade += 1

    return {
        "categoria": categoria_buscada,
        "periodo": periodo,
        "dias": dias,
        "total": total,
        "quantidade": quantidade,
    }


def buscar_transacoes(
    usuario_id: int,
    termo: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    periodo: str | None = None,
    dias: int | None = None,
    valor_min: float | None = None,
    valor_max: float | None = None,
    limite: int = 20,
):
    """Histórico do usuário com busca e filtros.

    Filtra por descrição, categoria, tipo, período, últimos N dias e faixa
    de valor. Somente leitura.
    """

    limite = max(1, int(limite or 20))

    db = SessionLocal()

    try:
        consulta = (
            db.query(models.Transacao)
            .filter(models.Transacao.usuario_id == usuario_id)
        )

        if tipo:
            consulta = consulta.filter(
                models.Transacao.tipo.ilike(tipo)
            )

        if periodo:
            inicio, fim = limites_periodo(periodo)

            consulta = consulta.filter(
                models.Transacao.data >= inicio,
                models.Transacao.data < fim,
            )

        elif dias:
            consulta = consulta.filter(
                models.Transacao.data
                >= datetime.now() - timedelta(days=dias)
            )

        transacoes = (
            consulta
            .order_by(models.Transacao.id.desc())
            .all()
        )

    finally:
        db.close()

    termo_normalizado = normalizar_texto(termo) if termo else None

    categoria_normalizada = (
        normalizar_categoria(categoria)
        if categoria
        else None
    )

    encontradas = []

    for transacao in transacoes:

        valor = float(transacao.valor)

        if (
            termo_normalizado
            and termo_normalizado not in normalizar_texto(transacao.descricao)
        ):
            continue

        if (
            categoria_normalizada
            and normalizar_categoria(transacao.categoria) != categoria_normalizada
        ):
            continue

        if valor_min is not None and valor < float(valor_min):
            continue

        if valor_max is not None and valor > float(valor_max):
            continue

        encontradas.append(transacao)

        if len(encontradas) >= limite:
            break

    return serializar_transacoes(encontradas)


# =========================================================
# EDIÇÃO E EXCLUSÃO
# =========================================================

def editar_transacao(
    usuario_id: int,
    transacao_id: int,
    valor: float | None = None,
    descricao: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    data: datetime | None = None,
):
    """Edita um lançamento do próprio usuário, alterando só o que foi informado."""

    if valor is not None and float(valor) <= 0:
        return {
            "sucesso": False,
            "erro": "O valor precisa ser maior que zero.",
        }

    if descricao is not None and not str(descricao).strip():
        return {
            "sucesso": False,
            "erro": "A descrição não pode ficar vazia.",
        }

    if (
        tipo is not None
        and normalizar_texto(str(tipo)) not in ("entrada", "saida")
    ):
        return {
            "sucesso": False,
            "erro": "O tipo precisa ser entrada ou saída.",
        }

    db = SessionLocal()

    try:
        transacao = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.id == transacao_id,
                models.Transacao.usuario_id == usuario_id,
            )
            .first()
        )

        if not transacao:
            return {
                "sucesso": False,
                "erro": "Não encontrei esse lançamento.",
                "nao_encontrado": True,
            }

        if valor is not None:
            transacao.valor = float(valor)

        if descricao is not None:
            transacao.descricao = str(descricao).strip()

        if categoria is not None:
            transacao.categoria = normalizar_categoria(categoria)

        if tipo is not None:
            transacao.tipo = (
                "entrada"
                if normalizar_texto(str(tipo)) == "entrada"
                else "saida"
            )

        if data is not None:
            transacao.data = data

        db.commit()
        db.refresh(transacao)

        return {
            "sucesso": True,
            "transacao": serializar_transacao(transacao),
        }

    finally:
        db.close()


def excluir_transacao(usuario_id: int, transacao_id: int):
    """Exclui um lançamento do próprio usuário."""

    db = SessionLocal()

    try:
        transacao = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.id == transacao_id,
                models.Transacao.usuario_id == usuario_id,
            )
            .first()
        )

        if not transacao:
            return {
                "sucesso": False,
                "erro": "Não encontrei esse lançamento.",
                "nao_encontrado": True,
            }

        dados = serializar_transacao(transacao)

        db.delete(transacao)
        db.commit()

        return {
            "sucesso": True,
            "transacao": dados,
        }

    finally:
        db.close()
