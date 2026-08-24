import os

from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse

from app.whatsapp.processador import (
    processar_mensagem,
    identificar_consulta
)

from app.whatsapp.consultas import (
    consultar_saldo,
    consultar_ultimas_transacoes
)


router = APIRouter()


@router.get("/whatsapp/webhook")
def verificar_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Endpoint usado pela Meta para verificar o webhook.
    """

    token_correto = os.getenv("WHATSAPP_VERIFY_TOKEN")

    if (
        hub_mode == "subscribe"
        and hub_verify_token
        and hub_verify_token == token_correto
    ):
        return PlainTextResponse(content=hub_challenge)

    return PlainTextResponse(
        content="Token de verificação inválido",
        status_code=403
    )


@router.post("/whatsapp/webhook")
async def receber_mensagem(request: Request):

    dados = await request.json()

    mensagem = dados.get("mensagem", "")
    usuario_id = dados.get("usuario_id")

    print("Mensagem recebida:", mensagem)
    print("Usuário:", usuario_id)

    if not usuario_id:
        return {
            "status": "erro",
            "resposta": "Usuário não identificado."
        }

    # Verifica se é uma consulta
    consulta = identificar_consulta(mensagem)

    if consulta == "saldo":

        resultado = consultar_saldo(int(usuario_id))

        saldo = resultado["saldo"]
        entradas = resultado["total_entradas"]
        saidas = resultado["total_saidas"]

        return {
            "status": "ok",
            "resposta": (
                f"💰 Seu saldo atual é R$ {saldo:.2f}\n"
                f"📥 Total de entradas: R$ {entradas:.2f}\n"
                f"📤 Total de saídas: R$ {saidas:.2f}"
            ),
            "dados": resultado
        }

    if consulta == "ultimas_transacoes":

        transacoes = consultar_ultimas_transacoes(
            int(usuario_id)
        )

        if not transacoes:
            return {
                "status": "ok",
                "resposta": "📭 Você ainda não possui transações registradas."
            }

        resposta = "📊 Suas últimas transações:\n\n"

        for transacao in transacoes:
            sinal = "📥" if transacao.tipo.lower() == "entrada" else "📤"

            resposta += (
                f"{sinal} R$ {transacao.valor:.2f} - "
                f"{transacao.categoria}\n"
                f"📝 {transacao.descricao}\n\n"
            )

        return {
            "status": "ok",
            "resposta": resposta
        }

    # Se não for consulta, tenta registrar uma transação
    resultado = processar_mensagem(mensagem)

    if not resultado["sucesso"]:
        return {
            "status": "erro",
            "resposta": resultado["resposta"]
        }

    from app.database import SessionLocal
    from app import models

    db = SessionLocal()

    try:

        nova_transacao = models.Transacao(
            usuario_id=int(usuario_id),
            descricao=resultado["descricao"],
            valor=resultado["valor"],
            tipo=resultado["tipo"],
            categoria=resultado["categoria"]
        )

        db.add(nova_transacao)
        db.commit()
        db.refresh(nova_transacao)

        return {
            "status": "ok",
            "resposta": (
                f"✅ Transação registrada!\n"
                f"💰 Valor: R$ {resultado['valor']:.2f}\n"
                f"📌 Tipo: {resultado['tipo']}\n"
                f"📂 Categoria: {resultado['categoria']}"
            ),
            "transacao_id": nova_transacao.id
        }

    finally:
        db.close()