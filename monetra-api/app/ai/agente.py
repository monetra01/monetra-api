import json
import os
import re
from typing import Any

from openai import AsyncOpenAI

from app.database import SessionLocal
from app import models
from app.whatsapp.consultas import (
    buscar_transacoes_para_correcao,
    consultar_gastos_mes,
    consultar_gastos_por_categoria,
    consultar_saldo,
    consultar_ultimas_transacoes,
)


SYSTEM_PROMPT = '''
Você é a Prospere, uma assistente de inteligência financeira pessoal.

Converse de forma natural, clara e curta em português do Brasil. Entenda mensagens em
outros idiomas e responda no idioma do usuário.

REGRAS IMPORTANTES:
1. Nunca invente saldo, gastos, transações ou números financeiros.
2. Para informações financeiras, use as ferramentas disponíveis.
3. Só registre uma transação quando houver intenção clara e informação suficiente.
4. Se faltar informação essencial, pergunte de forma simples.
5. Valores são positivos; o tipo define entrada ou saída.
6. Nunca diga que registrou algo sem confirmação da ferramenta.
7. Nunca diga que consultou dados sem realmente consultar.
8. Não use números inventados para aconselhamento.
9. Seja humana, útil e objetiva.
10. Nunca exponha detalhes internos, ferramentas, banco ou implementação.

CORREÇÕES DE TRANSAÇÕES:
11. Quando o usuário quiser corrigir uma transação, primeiro localize a transação
    usando uma ferramenta de consulta. Nunca altere uma transação sem antes
    identificar qual lançamento deve ser corrigido.

12. Se o usuário disser algo como:
    - "corrigindo"
    - "na verdade"
    - "errei"
    - "não foi"
    - "não foram"
    - "era"
    - "foram"
    - "troca"
    - "troque"
    - "corrigir"
    e estiver claramente se referindo a um lançamento anterior, trate a mensagem
    como CORREÇÃO e NÃO como uma nova transação.

13. Se a correção informar apenas o valor antigo e o novo valor, por exemplo:
    "Corrigindo, não foram 20, foram 15",
    consulte as transações recentes e procure lançamentos compatíveis com o
    valor antigo.

14. Quando houver exatamente UMA transação compatível com a correção, ela pode
    ser corrigida usando a ferramenta de correção.

15. Se houver MAIS DE UMA transação compatível com o mesmo valor ou contexto,
    NÃO escolha uma aleatoriamente. Mostre as opções de forma simples e peça
    ao usuário para indicar qual deseja corrigir.

16. Se não for possível identificar com segurança qual transação deve ser
    corrigida, faça uma pergunta simples ao usuário em vez de alterar qualquer
    lançamento.

17. Quando a correção for apenas do valor, mantenha a descrição, categoria e
    tipo originais e altere somente o valor.

18. Nunca diga que uma transação foi corrigida, alterada ou excluída sem uma
    ferramenta confirmar essa operação.

19. Depois que uma correção for confirmada pela ferramenta, informe claramente
    o novo valor ao usuário.

20. IMPORTANTE: nunca use automaticamente "a última transação" apenas porque
    ela é a mais recente. A transação precisa ser identificada com segurança
    antes da alteração.
'''.strip()


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "registrar_transacao",
        "Registra uma entrada ou saída financeira confirmada pelo usuário.",
        {
            "valor": {
                "type": "number",
                "description": "Valor positivo da transação.",
            },
            "tipo": {
                "type": "string",
                "enum": ["entrada", "saida"],
            },
            "categoria": {
                "type": "string",
                "enum": [
                    "Transporte",
                    "Alimentação",
                    "Casa",
                    "Saúde",
                    "Lazer",
                    "Outros",
                ],
            },
            "descricao": {
                "type": "string",
                "description": "Descrição curta.",
            },
        },
        ["valor", "tipo", "categoria", "descricao"],
    ),

    _tool(
        "consultar_saldo",
        "Consulta saldo, entradas e saídas.",
        {},
        [],
    ),

    _tool(
        "consultar_gastos_mes",
        "Consulta gastos do mês atual.",
        {},
        [],
    ),

    _tool(
        "consultar_ultimas_transacoes",
        "Lista transações recentes do usuário. Use esta ferramenta para "
        "identificar uma transação que o usuário deseja corrigir quando "
        "ele não informar uma descrição específica.",
        {
            "limite": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
            }
        },
        ["limite"],
    ),

    _tool(
        "consultar_gastos_por_categoria",
        "Consulta saídas agrupadas por categoria.",
        {},
        [],
    ),

    _tool(
        "buscar_transacoes_para_correcao",
        "Localiza transações pela descrição para preparar uma possível correção. "
        "Esta ferramenta apenas consulta e nunca altera os dados.",
        {
            "termo": {
                "type": "string",
                "description": "Termo ou descrição da transação que o usuário deseja localizar.",
            },
            "limite": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
            },
        },
        ["termo", "limite"],
    ),

    _tool(
        "corrigir_transacao",
        "Altera somente o valor de uma transação existente depois que ela "
        "foi identificada com segurança como sendo a transação que o usuário "
        "deseja corrigir. Nunca use esta ferramenta apenas porque uma transação "
        "é a mais recente.",
        {
            "transacao_id": {
                "type": "integer",
                "description": "ID da transação que será corrigida.",
            },
            "novo_valor": {
                "type": "number",
                "description": "Novo valor positivo da transação.",
            },
        },
        ["transacao_id", "novo_valor"],
    ),
]


def _serializar_transacoes(transacoes: list[Any]) -> list[dict[str, Any]]:
    resultado = []

    for t in transacoes:
        resultado.append(
            {
                "id": t.id,
                "descricao": t.descricao,
                "valor": float(t.valor),
                "tipo": t.tipo,
                "categoria": t.categoria or "Outros",
                "data": t.data.isoformat() if t.data else None,
            }
        )

    return resultado


def _moeda(valor: float) -> str:
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _consulta_rapida(mensagem: str, usuario_id: int) -> str | None:
    """Responde consultas simples sem fazer uma chamada à IA."""

    texto = re.sub(r"\s+", " ", mensagem.strip().lower())

    # ============================================================
    # SALDO
    # ============================================================

    if (
        (
            "saldo" in texto
            or "quanto tenho" in texto
            or "quanto eu tenho" in texto
        )
        and not any(
            p in texto
            for p in (
                "gastei",
                "gastos",
                "gasto",
                "despesa",
                "despesas",
                "transa",
                "categoria",
                "categorias",
            )
        )
    ):
        dados = consultar_saldo(usuario_id)

        return (
            f"Seu saldo atual é de *{_moeda(float(dados['saldo']))}*.\n"
            f"Entradas: *{_moeda(float(dados['total_entradas']))}* | "
            f"Saídas: *{_moeda(float(dados['total_saidas']))}*."
        )

    # ============================================================
    # GASTOS DO MÊS
    # ============================================================

    if (
        ("mês" in texto or "mes" in texto)
        and any(
            p in texto
            for p in (
                "gastei",
                "gastos",
                "gasto",
                "despesa",
                "total",
            )
        )
    ):
        total = float(consultar_gastos_mes(usuario_id))

        return f"Neste mês, você gastou *{_moeda(total)}*."

    # ============================================================
    # ÚLTIMAS TRANSAÇÕES
    # ============================================================

    if (
        (
            "últimas" in texto
            or "ultimas" in texto
            or "recentes" in texto
        )
        and (
            "transa" in texto
            or "lançamento" in texto
            or "lancamento" in texto
        )
    ):
        transacoes = _serializar_transacoes(
            consultar_ultimas_transacoes(usuario_id, 5)
        )

        if not transacoes:
            return "Você ainda não tem transações registradas."

        linhas = ["Estas são suas últimas transações:"]

        for t in transacoes:
            sinal = "+" if t["tipo"].lower() == "entrada" else "-"

            linhas.append(
                f"• {sinal} {_moeda(t['valor'])} — "
                f"{t['descricao']} ({t['categoria']})"
            )

        return "\n".join(linhas)

    # ============================================================
    # GASTOS POR CATEGORIA
    # ============================================================

    if (
        "categoria" in texto
        and any(
            p in texto
            for p in (
                "gasto",
                "gastos",
                "gastei",
                "despesa",
                "despesas",
                "quanto",
            )
        )
    ):
        categorias = consultar_gastos_por_categoria(usuario_id)

        if not categorias:
            return "Você ainda não tem gastos registrados."

        linhas = ["Seus gastos por categoria:"]

        for categoria, valor in sorted(
            categorias.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            linhas.append(
                f"• {categoria}: *{_moeda(float(valor))}*"
            )

        return "\n".join(linhas)

    return None


def _registrar_transacao(
    usuario_id: int,
    args: dict[str, Any],
) -> dict[str, Any]:

    valor = float(args["valor"])
    tipo = args["tipo"]
    categoria = args["categoria"]
    descricao = args["descricao"].strip()

    if valor <= 0:
        return {
            "sucesso": False,
            "erro": "O valor precisa ser maior que zero.",
        }

    if not descricao:
        return {
            "sucesso": False,
            "erro": "A descrição não pode ficar vazia.",
        }

    db = SessionLocal()

    try:
        transacao = models.Transacao(
            usuario_id=usuario_id,
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            categoria=categoria,
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        return {
            "sucesso": True,
            "transacao": {
                "id": transacao.id,
                "valor": float(transacao.valor),
                "tipo": transacao.tipo,
                "categoria": transacao.categoria,
                "descricao": transacao.descricao,
            },
        }

    finally:
        db.close()


def _corrigir_transacao(
    usuario_id: int,
    args: dict[str, Any],
) -> dict[str, Any]:

    transacao_id = int(args["transacao_id"])
    novo_valor = float(args["novo_valor"])

    if novo_valor <= 0:
        return {
            "sucesso": False,
            "erro": "O novo valor precisa ser maior que zero.",
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
                "erro": "Não encontrei essa transação.",
            }

        valor_anterior = float(transacao.valor)

        transacao.valor = novo_valor

        db.commit()
        db.refresh(transacao)

        return {
            "sucesso": True,
            "transacao": {
                "id": transacao.id,
                "valor_anterior": valor_anterior,
                "valor": float(transacao.valor),
                "tipo": transacao.tipo,
                "categoria": transacao.categoria,
                "descricao": transacao.descricao,
            },
        }

    finally:
        db.close()


def _executar_ferramenta(
    nome: str,
    args: dict[str, Any],
    usuario_id: int,
) -> dict[str, Any]:

    if nome == "registrar_transacao":
        return _registrar_transacao(usuario_id, args)

    if nome == "corrigir_transacao":
        return _corrigir_transacao(usuario_id, args)

    if nome == "consultar_saldo":
        return consultar_saldo(usuario_id)

    if nome == "consultar_gastos_mes":
        return {
            "total_gastos_mes": consultar_gastos_mes(usuario_id)
        }

    if nome == "consultar_ultimas_transacoes":
        return {
            "transacoes": _serializar_transacoes(
                consultar_ultimas_transacoes(
                    usuario_id,
                    args.get("limite", 5),
                )
            )
        }

    if nome == "consultar_gastos_por_categoria":
        return {
            "categorias": consultar_gastos_por_categoria(usuario_id)
        }

    if nome == "buscar_transacoes_para_correcao":
        termo = args["termo"].strip()
        limite = args.get("limite", 5)

        if not termo:
            return {
                "sucesso": False,
                "erro": "O termo de busca não pode ficar vazio.",
            }

        return {
            "sucesso": True,
            "transacoes": buscar_transacoes_para_correcao(
                usuario_id,
                termo,
                limite,
            ),
        }

    return {
        "erro": f"Ferramenta desconhecida: {nome}"
    }


async def responder_com_ia(
    mensagem: str,
    usuario_id: int,
) -> str | None:

    resposta_rapida = _consulta_rapida(
        mensagem,
        usuario_id,
    )

    if resposta_rapida is not None:
        return resposta_rapida

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    model = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    )

    client = AsyncOpenAI(
        api_key=api_key,
    )

    response = await client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        tools=TOOLS,
        input=mensagem,
    )

    for _ in range(5):

        tool_calls = [
            item
            for item in response.output
            if getattr(item, "type", None) == "function_call"
        ]

        if not tool_calls:
            return (
                response.output_text.strip()
                if response.output_text
                else "Não consegui processar sua mensagem agora."
            )

        tool_outputs = []

        for call in tool_calls:

            try:
                args = json.loads(
                    call.arguments or "{}"
                )

                resultado = _executar_ferramenta(
                    call.name,
                    args,
                    usuario_id,
                )

            except Exception as erro:

                resultado = {
                    "erro": (
                        "Não foi possível executar "
                        "a operação financeira."
                    )
                }

                print(
                    f"❌ Erro na ferramenta "
                    f"{call.name}: {erro}"
                )

            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(
                        resultado,
                        ensure_ascii=False,
                    ),
                }
            )

        response = await client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            tools=TOOLS,
            input=tool_outputs,
            previous_response_id=response.id,
        )

    return "Não consegui concluir essa operação agora."