from datetime import datetime

from app.database import SessionLocal
from app import models


def consultar_saldo(usuario_id: int):
    db = SessionLocal()
    try:
        transacoes = db.query(models.Transacao).filter(models.Transacao.usuario_id == usuario_id).all()
        entradas = sum(float(t.valor) for t in transacoes if t.tipo.lower() == "entrada")
        saidas = sum(float(t.valor) for t in transacoes if t.tipo.lower() == "saida")
        return {"saldo": entradas - saidas, "total_entradas": entradas, "total_saidas": saidas}
    finally:
        db.close()


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
        inicio_mes = datetime(agora.year, agora.month, 1)
        inicio_proximo_mes = (
            datetime(agora.year + 1, 1, 1)
            if agora.month == 12
            else datetime(agora.year, agora.month + 1, 1)
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
        return float(sum(t.valor for t in gastos))
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
            categoria = t.categoria or "Outros"
            categorias[categoria] = categorias.get(categoria, 0) + float(t.valor)
        return categorias
    finally:
        db.close()
