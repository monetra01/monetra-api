import os

import httpx

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


# =========================================================
# CONFIGURAÇÃO DO WHATSAPP
# =========================================================

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Pode ser alterada pelo Environment do Render.
# Não coloque o token aqui.
WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v23.0"
)


# =========================================================
# ENVIAR MENSAGEM PELO WHATSAPP
# =========================================================

async def enviar_mensagem_whatsapp(
    numero: str,
    mensagem: str
):
    if not WHATSAPP_ACCESS_TOKEN:
        print("❌ WHATSAPP_ACCESS_TOKEN não configurado")
        return False

    if not WHATSAPP_PHONE_NUMBER_ID:
        print("❌ WHATSAPP_PHONE_NUMBER_ID não configurado")
        return False

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {
            "body": mensagem
        }
    }

    try:

        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload
            )

        print("WhatsApp API status:", response.status_code)
        print("WhatsApp API resposta:", response.text)

        if response.is_success:
            print("✅ Mensagem enviada pelo WhatsApp")
            return True

        print("❌ Erro ao enviar mensagem pelo WhatsApp")
        return False

    except Exception as erro:

        print(
            "❌ Erro de comunicação com WhatsApp:",
            erro
        )

        return False


# =========================================================
# VERIFICAÇÃO DO WEBHOOK PELA META
# =========================================================

@router.get("/whatsapp/webhook")
def verificar_webhook(
    hub_mode: str | None = Query(
        default=None,
        alias="hub.mode"
    ),
    hub_verify_token: str | None = Query(
        default=None,
        alias="hub.verify_token"
    ),
    hub_challenge: str | None = Query(
        default=None,
        alias="hub.challenge"
    )
):

    print("=== VERIFICAÇÃO DO WEBHOOK ===")

    print("hub.mode:", hub_mode)

    print(
        "hub.verify_token recebido:",
        bool(hub_verify_token)
    )

    print(
        "hub.challenge recebido:",
        hub_challenge
    )

    token_correto = os.getenv(
        "WHATSAPP_VERIFY_TOKEN"
    )

    print(
        "WHATSAPP_VERIFY_TOKEN configurado:",
        bool(token_correto)
    )

    if (
        hub_mode == "subscribe"
        and hub_verify_token
        and token_correto
        and hub_verify_token == token_correto
        and hub_challenge
    ):

        print(
            "✅ WEBHOOK VALIDADO COM SUCESSO"
        )

        return PlainTextResponse(
            content=hub_challenge,
            status_code=200
        )

    print(
        "❌ FALHA NA VALIDAÇÃO DO WEBHOOK"
    )

    return PlainTextResponse(
        content="Token de verificação inválido",
        status_code=403
    )


# =========================================================
# RECEBIMENTO DE MENSAGENS
# =========================================================

@router.post("/whatsapp/webhook")
async def receber_mensagem(
    request: Request
):

    dados = await request.json()

    print("====================================")
    print("📩 WEBHOOK WHATSAPP RECEBIDO")
    print("====================================")

    print("Dados recebidos:")
    print(dados)

    # =====================================================
    # IDENTIFICAR SE É WEBHOOK REAL DA META
    # =====================================================

    numero_whatsapp = None
    mensagem = None
    usuario_id = dados.get("usuario_id")

    try:

        entry = dados.get("entry", [])

        if entry:

            changes = entry[0].get(
                "changes",
                []
            )

            if changes:

                value = changes[0].get(
                    "value",
                    {}
                )

                messages = value.get(
                    "messages",
                    []
                )

                # Pode ser atualização de status,
                # sem mensagem recebida.
                if not messages:

                    print(
                        "ℹ️ Webhook recebido sem mensagem."
                    )

                    return {
                        "status": "ok"
                    }

                mensagem_obj = messages[0]

                numero_whatsapp = (
                    mensagem_obj.get("from")
                )

                tipo_mensagem = (
                    mensagem_obj.get("type")
                )

                if tipo_mensagem == "text":

                    mensagem = (
                        mensagem_obj
                        .get("text", {})
                        .get("body", "")
                    )

                else:

                    print(
                        "⚠️ Tipo de mensagem não suportado:",
                        tipo_mensagem
                    )

                    if numero_whatsapp:

                        await enviar_mensagem_whatsapp(
                            numero_whatsapp,
                            "⚠️ Por enquanto, consigo "
                            "processar apenas mensagens de texto."
                        )

                    return {
                        "status": "ok"
                    }

    except Exception as erro:

        print(
            "❌ Erro ao interpretar webhook da Meta:",
            erro
        )

        return {
            "status": "erro"
        }


    # =====================================================
    # COMPATIBILIDADE COM TESTES ANTIGOS
    # =====================================================

    if not mensagem:

        mensagem = dados.get(
            "mensagem",
            ""
        )

    print(
        "📱 Número WhatsApp:",
        numero_whatsapp
    )

    print(
        "💬 Mensagem:",
        mensagem
    )

    # =====================================================
    # IDENTIFICAÇÃO DO USUÁRIO
    # =====================================================

    # Durante o primeiro teste podemos usar
    # WHATSAPP_DEFAULT_USER_ID no Render.
    #
    # Depois vamos substituir isso por uma
    # identificação real através do número WhatsApp.

    if not usuario_id:

        usuario_id = os.getenv(
            "WHATSAPP_DEFAULT_USER_ID"
        )

    print(
        "👤 Usuário:",
        usuario_id
    )

    if not usuario_id:

        resposta = (
            "❌ Usuário não identificado."
        )

        if numero_whatsapp:

            await enviar_mensagem_whatsapp(
                numero_whatsapp,
                resposta
            )

        return {
            "status": "erro",
            "resposta": resposta
        }

    usuario_id = int(usuario_id)


    # =====================================================
    # CONSULTA DE SALDO
    # =====================================================

    consulta = identificar_consulta(
        mensagem
    )

    if consulta == "saldo":

        resultado = consultar_saldo(
            usuario_id
        )

        saldo = resultado["saldo"]

        entradas = resultado[
            "total_entradas"
        ]

        saidas = resultado[
            "total_saidas"
        ]

        resposta = (
            f"💰 Seu saldo atual é "
            f"R$ {saldo:.2f}\n"
            f"📥 Total de entradas: "
            f"R$ {entradas:.2f}\n"
            f"📤 Total de saídas: "
            f"R$ {saidas:.2f}"
        )

        if numero_whatsapp:

            await enviar_mensagem_whatsapp(
                numero_whatsapp,
                resposta
            )

        return {
            "status": "ok",
            "resposta": resposta,
            "dados": resultado
        }


    # =====================================================
    # ÚLTIMAS TRANSAÇÕES
    # =====================================================

    if consulta == "ultimas_transacoes":

        transacoes = consultar_ultimas_transacoes(
            usuario_id
        )

        if not transacoes:

            resposta = (
                "📭 Você ainda não possui "
                "transações registradas."
            )

        else:

            resposta = (
                "📊 Suas últimas transações:\n\n"
            )

            for transacao in transacoes:

                sinal = (
                    "📥"
                    if transacao.tipo.lower()
                    == "entrada"
                    else "📤"
                )

                resposta += (
                    f"{sinal} R$ "
                    f"{transacao.valor:.2f} - "
                    f"{transacao.categoria}\n"
                    f"📝 {transacao.descricao}\n\n"
                )

        if numero_whatsapp:

            await enviar_mensagem_whatsapp(
                numero_whatsapp,
                resposta
            )

        return {
            "status": "ok",
            "resposta": resposta
        }


    # =====================================================
    # REGISTRAR TRANSAÇÃO
    # =====================================================

    resultado = processar_mensagem(
        mensagem
    )

    if not resultado["sucesso"]:

        resposta = resultado["resposta"]

        if numero_whatsapp:

            await enviar_mensagem_whatsapp(
                numero_whatsapp,
                resposta
            )

        return {
            "status": "erro",
            "resposta": resposta
        }


    from app.database import SessionLocal
    from app import models

    db = SessionLocal()

    try:

        nova_transacao = models.Transacao(

            usuario_id=usuario_id,

            descricao=resultado[
                "descricao"
            ],

            valor=resultado[
                "valor"
            ],

            tipo=resultado[
                "tipo"
            ],

            categoria=resultado[
                "categoria"
            ]
        )

        db.add(
            nova_transacao
        )

        db.commit()

        db.refresh(
            nova_transacao
        )

        resposta = (
            "✅ Transação registrada!\n"
            f"💰 Valor: "
            f"R$ {resultado['valor']:.2f}\n"
            f"📌 Tipo: "
            f"{resultado['tipo']}\n"
            f"📂 Categoria: "
            f"{resultado['categoria']}"
        )

        if numero_whatsapp:

            await enviar_mensagem_whatsapp(
                numero_whatsapp,
                resposta
            )

        return {
            "status": "ok",
            "resposta": resposta,
            "transacao_id":
                nova_transacao.id
        }

    finally:

        db.close()