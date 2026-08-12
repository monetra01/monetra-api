from datetime import datetime

from app.database import SessionLocal
from app import models


def consultar_saldo(usuario_id: int):
    db = SessionLocal()

    try:
        transacoes = db.query(models.Transacao).filter(
            models.Transacao.usuario_id == usuario_id
        ).all()

        entradas = sum(
            t.valor
            for t in transacoes
            if t.tipo.lower() == "entrada"
        )

        saidas = sum(
            t.valor
            for t in transacoes
            if t.tipo.lower() == "saida"
        )

        saldo = entradas - saidas

        return {
            "saldo": saldo,
            "total_entradas": entradas,
            "total_saidas": saidas
        }

    finally:
        db.close()


def consultar_ultimas_transacoes(usuario_id: int, limite: int = 5):
    db = SessionLocal()

    try:
        transacoes = (
            db.query(models.Transacao)
            .filter(models.Transacao.usuario_id == usuario_id)
            .order_by(models.Transacao.id.desc())
            .limit(limite)
            .all()
        )

        return transacoes

    finally:
        db.close()


def consultar_gastos_mes(usuario_id: int):
    db = SessionLocal()

    try:
        agora = datetime.now()

        inicio_mes = datetime(
            agora.year,
            agora.month,
            1
        )

        if agora.month == 12:
            inicio_proximo_mes = datetime(
                agora.year + 1,
                1,
                1
            )
        else:
            inicio_proximo_mes = datetime(
                agora.year,
                agora.month + 1,
                1
            )

        gastos = (
            db.query(models.Transacao)
            .filter(
                models.Transacao.usuario_id == usuario_id,
                models.Transacao.tipo.ilike("saida"),
                models.Transacao.data >= inicio_mes,
                models.Transacao.data < inicio_proximo_mes
            )
            .all()
        )

        total = sum(t.valor for t in gastos)

        return total

    finally:
        db.close()        