from app.database import SessionLocal
from app import models


def buscar_cadastro_pendente(numero_whatsapp):
    db = SessionLocal()

    try:
        return (
            db.query(models.CadastroPendente)
            .filter(
                models.CadastroPendente.whatsapp_numero
                == numero_whatsapp
            )
            .first()
        )

    finally:
        db.close()


def criar_cadastro_pendente(numero_whatsapp):
    db = SessionLocal()

    try:
        cadastro = models.CadastroPendente(
            whatsapp_numero=numero_whatsapp,
            etapa="aguardando_nome"
        )

        db.add(cadastro)
        db.commit()
        db.refresh(cadastro)

        return cadastro

    finally:
        db.close()


def atualizar_cadastro_pendente(
    numero_whatsapp,
    etapa=None,
    nome=None
):
    db = SessionLocal()

    try:
        cadastro = (
            db.query(models.CadastroPendente)
            .filter(
                models.CadastroPendente.whatsapp_numero
                == numero_whatsapp
            )
            .first()
        )

        if not cadastro:
            return None

        if etapa is not None:
            cadastro.etapa = etapa

        if nome is not None:
            cadastro.nome = nome

        db.commit()
        db.refresh(cadastro)

        return cadastro

    finally:
        db.close()


def concluir_cadastro(numero_whatsapp):
    db = SessionLocal()

    try:
        cadastro = (
            db.query(models.CadastroPendente)
            .filter(
                models.CadastroPendente.whatsapp_numero
                == numero_whatsapp
            )
            .first()
        )

        if not cadastro or not cadastro.nome:
            return None

        usuario = models.Usuario(
            nome=cadastro.nome,
            whatsapp_numero=numero_whatsapp,
            email=None,
            senha=""
        )

        db.add(usuario)
        db.flush()

        db.delete(cadastro)
        db.commit()
        db.refresh(usuario)

        return usuario

    finally:
        db.close()