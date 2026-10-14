"""Correção e exclusão de lançamentos pedidas pelo WhatsApp.

O lançamento precisa ser identificado com segurança antes de qualquer
alteração: quando houver mais de um candidato, a Prospere mostra as opções
e pergunta em vez de escolher sozinha.
"""

from app.texto import formatar_moeda
from app.whatsapp.consultas import (
    buscar_transacoes,
    editar_transacao,
    excluir_transacao,
)


def _listar(transacoes) -> str:
    linhas = []

    for transacao in transacoes:
        sinal = (
            "📥"
            if (transacao["tipo"] or "").lower() == "entrada"
            else "📤"
        )

        linhas.append(
            f"{sinal} #{transacao['id']} "
            f"{formatar_moeda(transacao['valor'])} — "
            f"{transacao['descricao']} ({transacao['categoria']})"
        )

    return "\n".join(linhas)


def _localizar(usuario_id: int, correcao: dict):
    """Localiza os lançamentos que o pedido pode estar citando."""

    if correcao.get("valor_antigo") is not None:
        return buscar_transacoes(
            usuario_id,
            valor_min=correcao["valor_antigo"],
            valor_max=correcao["valor_antigo"],
            limite=5,
        )

    termo = correcao.get("termo")

    if termo:
        encontradas = buscar_transacoes(
            usuario_id,
            termo=termo,
            limite=5,
        )

        if encontradas:
            return encontradas

        # Sem descrição compatível, tenta pelo valor informado.
        if correcao.get("valor") is not None:
            return buscar_transacoes(
                usuario_id,
                valor_min=correcao["valor"],
                valor_max=correcao["valor"],
                limite=5,
            )

        return []

    if correcao.get("ultima"):
        return buscar_transacoes(usuario_id, limite=1)

    return []


def tratar_correcao(usuario_id: int, correcao: dict) -> str:
    """Executa a correção ou exclusão e devolve a resposta para o usuário."""

    acao = correcao["acao"]

    if acao == "editar" and correcao.get("valor") is None:
        return (
            "Me diga o novo valor que devo usar, por favor. 😊\n"
            "Exemplo: *corrigir mercado para 45*"
        )

    candidatos = _localizar(usuario_id, correcao)

    if not candidatos:
        return (
            "Não encontrei nenhum lançamento com essas informações. "
            "Pode me dizer a descrição exata? 😊"
        )

    if len(candidatos) > 1:
        return (
            "Encontrei mais de um lançamento parecido. Qual deles é?\n\n"
            + _listar(candidatos)
            + "\n\nMe diga a descrição exata para eu acertar."
        )

    transacao = candidatos[0]

    if acao == "excluir":

        resultado = excluir_transacao(usuario_id, transacao["id"])

        if not resultado["sucesso"]:
            return "Não consegui excluir esse lançamento agora. Tente novamente. 😊"

        excluida = resultado["transacao"]

        return (
            "🗑️ Lançamento excluído!\n"
            f"{formatar_moeda(excluida['valor'])} — {excluida['descricao']}"
        )

    resultado = editar_transacao(
        usuario_id,
        transacao["id"],
        valor=correcao["valor"],
    )

    if not resultado["sucesso"]:
        return f"Não consegui corrigir: {resultado['erro']}"

    editada = resultado["transacao"]

    return (
        "✅ Lançamento corrigido!\n"
        f"{editada['descricao']}: "
        f"{formatar_moeda(transacao['valor'])} → "
        f"{formatar_moeda(editada['valor'])}"
    )
