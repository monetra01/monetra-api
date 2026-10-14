import json
import os
import re
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI

from app import models
from app.categorias import ALIASES, CATEGORIA_PADRAO, normalizar_categoria
from app.database import SessionLocal
from app.texto import formatar_moeda, normalizar_texto
from app.whatsapp.consultas import (
    PERIODOS,
    buscar_transacoes,
    consultar_gasto_categoria,
    consultar_gastos_mes,
    consultar_gastos_por_categoria,
    consultar_periodo,
    consultar_saldo,
    consultar_ultimas_transacoes,
    editar_transacao,
    excluir_transacao,
    serializar_transacoes,
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

CORREÇÕES E EXCLUSÕES DE TRANSAÇÕES:
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
    ser corrigida usando a ferramenta de edição.

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

CATEGORIAS:
21. As categorias padrão da Prospere são: Alimentação, Moradia, Transporte, Saúde,
    Lazer, Compras e assinaturas, Educação, Renda, Investimentos e Outros.
22. Entradas de dinheiro (salário, renda extra, comissões, bonificações e outros
    recebimentos) usam a categoria Renda.
23. Se o usuário pedir uma categoria personalizada, use exatamente o nome que ele
    informou.

PERÍODOS, ANÁLISES E HISTÓRICO:
24. Quando o usuário falar de hoje, desta semana, deste mês ou deste ano, consulte
    o período em vez de somar tudo.
25. Para perguntas sobre uma categoria específica, consulte aquela categoria.
26. Para procurar lançamentos antigos, use a busca do histórico e informe id,
    descrição, valor, categoria e data do que encontrar.
27. Ao comparar valores, use apenas números vindos das ferramentas.

EDIÇÃO E EXCLUSÃO:
28. Para editar, primeiro localize o lançamento com a busca do histórico. A
    ferramenta de edição altera apenas os campos informados; mantenha os demais.
29. Só exclua um lançamento quando o usuário pedir a exclusão claramente e o
    lançamento estiver identificado. Se a identificação não for segura, mostre as
    opções e pergunte.
30. Depois de excluir, informe exatamente o que foi excluído.
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
        "Registra uma entrada ou saída financeira confirmada pelo usuário. "
        "Use o campo data quando o usuário informar quando o lançamento "
        "aconteceu.",
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
                "description": (
                    "Categoria do lançamento, como Alimentação, Moradia, "
                    "Transporte, Saúde, Lazer, Compras e assinaturas, Educação, "
                    "Renda, Investimentos, Outros ou uma categoria "
                    "personalizada do usuário. Use Renda para entradas."
                ),
            },
            "descricao": {
                "type": "string",
                "description": "Descrição curta.",
            },
            "data": {
                "type": ["string", "null"],
                "description": (
                    "Data do lançamento no formato AAAA-MM-DD. "
                    "Use null para hoje."
                ),
            },
        },
        ["valor", "tipo", "categoria", "descricao", "data"],
    ),

    _tool(
        "consultar_saldo",
        "Consulta saldo, entradas e saídas.",
        {},
        [],
    ),

    _tool(
        "consultar_periodo",
        "Consulta entradas, saídas e saldo de um período atual "
        "(dia, semana, mês ou ano).",
        {
            "periodo": {
                "type": "string",
                "enum": list(PERIODOS),
            },
        },
        ["periodo"],
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
        "consultar_gasto_categoria",
        "Consulta quanto o usuário gastou em uma categoria, no total, num "
        "período atual ou nos últimos N dias.",
        {
            "categoria": {
                "type": "string",
                "description": "Categoria consultada.",
            },
            "periodo": {
                "type": ["string", "null"],
                "description": (
                    "dia, semana, mes ou ano. Use null quando o usuário não "
                    "informar período."
                ),
            },
            "dias": {
                "type": ["integer", "null"],
                "description": (
                    "Últimos N dias. Use null quando o usuário não informar."
                ),
            },
        },
        ["categoria", "periodo", "dias"],
    ),

    _tool(
        "buscar_transacoes",
        "Busca lançamentos no histórico do usuário por descrição, categoria, "
        "tipo, período, últimos N dias ou faixa de valor. Use antes de editar "
        "ou excluir, para localizar o lançamento correto. Esta ferramenta "
        "apenas consulta e nunca altera os dados.",
        {
            "termo": {
                "type": ["string", "null"],
                "description": "Trecho da descrição procurada.",
            },
            "categoria": {
                "type": ["string", "null"],
                "description": "Categoria procurada.",
            },
            "tipo": {
                "type": ["string", "null"],
                "description": "entrada ou saida.",
            },
            "periodo": {
                "type": ["string", "null"],
                "description": "dia, semana, mes ou ano.",
            },
            "dias": {
                "type": ["integer", "null"],
                "description": "Últimos N dias.",
            },
            "valor_min": {
                "type": ["number", "null"],
                "description": "Valor mínimo.",
            },
            "valor_max": {
                "type": ["number", "null"],
                "description": "Valor máximo.",
            },
            "limite": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
            },
        },
        [
            "termo",
            "categoria",
            "tipo",
            "periodo",
            "dias",
            "valor_min",
            "valor_max",
            "limite",
        ],
    ),

    _tool(
        "editar_transacao",
        "Altera um lançamento já identificado com segurança. Informe apenas os "
        "campos que devem mudar. Nunca use esta ferramenta apenas porque uma "
        "transação é a mais recente.",
        {
            "transacao_id": {
                "type": "integer",
                "description": "ID do lançamento que será alterado.",
            },
            "valor": {
                "type": ["number", "null"],
                "description": "Novo valor positivo.",
            },
            "descricao": {
                "type": ["string", "null"],
                "description": "Nova descrição.",
            },
            "categoria": {
                "type": ["string", "null"],
                "description": "Nova categoria.",
            },
            "tipo": {
                "type": ["string", "null"],
                "description": "entrada ou saida.",
            },
            "data": {
                "type": ["string", "null"],
                "description": "Nova data no formato AAAA-MM-DD.",
            },
        },
        [
            "transacao_id",
            "valor",
            "descricao",
            "categoria",
            "tipo",
            "data",
        ],
    ),

    _tool(
        "excluir_transacao",
        "Exclui um lançamento já identificado com segurança e cuja exclusão o "
        "usuário pediu claramente.",
        {
            "transacao_id": {
                "type": "integer",
                "description": "ID do lançamento que será excluído.",
            },
        },
        ["transacao_id"],
    ),
]


def _moeda(valor: float) -> str:
    return formatar_moeda(valor)


def _periodo_valido(valor: Any) -> str | None:
    if not valor:
        return None

    texto = normalizar_texto(str(valor))

    return texto if texto in PERIODOS else None


def _nome_periodo(periodo: str | None) -> str:
    return {
        "dia": "hoje",
        "semana": "nesta semana",
        "mes": "neste mês",
        "ano": "neste ano",
    }.get(periodo or "mes", "neste mês")


def _sinal(tipo: Any) -> str:
    return "📥" if normalizar_texto(str(tipo)) == "entrada" else "📤"


def _categoria_citada(texto: str) -> str | None:
    procurado = normalizar_texto(texto)

    for chave, categoria in ALIASES.items():
        if f" {chave} " in f" {procurado} ":
            return categoria

    return None


def _periodo_citado(texto: str) -> str | None:
    if "hoje" in texto:
        return "dia"

    if "esta semana" in texto or "essa semana" in texto:
        return "semana"

    if (
        "este mes" in texto
        or "esse mes" in texto
        or "no mes" in texto
        or "do mes" in texto
    ):
        return "mes"

    if "este ano" in texto or "esse ano" in texto:
        return "ano"

    return None


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
    # GASTOS EM UMA CATEGORIA
    # ============================================================

    if any(
        p in texto
        for p in (
            "quanto gastei",
            "quanto eu gastei",
            "quanto foi",
            "gastos com",
            "total de gastos com",
        )
    ):
        categoria = _categoria_citada(texto)

        if categoria:

            periodo = _periodo_citado(texto)

            dados = consultar_gasto_categoria(
                usuario_id,
                categoria,
                periodo=periodo,
            )

            if periodo:
                return (
                    f"Você gastou *{_moeda(float(dados['total']))}* com "
                    f"*{dados['categoria']}* {_nome_periodo(periodo)}."
                )

            geral = float(
                consultar_gasto_categoria(
                    usuario_id,
                    categoria,
                )["total"]
            )

            return (
                f"Você gastou *{_moeda(float(dados['total']))}* com "
                f"*{dados['categoria']}* neste mês. "
                f"No total: *{_moeda(geral)}*."
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
    # PERÍODO (HOJE, SEMANA, ANO)
    # ============================================================

    periodo = _periodo_citado(texto)

    if periodo in ("dia", "semana", "ano") and any(
        p in texto
        for p in (
            "gastei",
            "gastos",
            "gasto",
            "despesa",
            "despesas",
            "entrou",
            "recebi",
            "entrada",
            "entradas",
        )
    ):
        dados = consultar_periodo(usuario_id, periodo)

        return (
            f"{_nome_periodo(periodo).capitalize()} você recebeu "
            f"*{_moeda(float(dados['total_entradas']))}* e gastou "
            f"*{_moeda(float(dados['total_saidas']))}*. "
            f"Saldo do período: *{_moeda(float(dados['saldo']))}*."
        )

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
        transacoes = serializar_transacoes(
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
    # BUSCA NO HISTÓRICO
    # ============================================================

    busca = re.match(
        r"^(buscar|busca|pesquisar|pesquisa|procurar|procura|encontrar|encontra)\s+(.+)$",
        texto,
    )

    if busca:

        termo = busca.group(2).strip()

        transacoes = buscar_transacoes(
            usuario_id,
            termo=termo,
            limite=5,
        )

        if not transacoes:
            return f"Não encontrei lançamentos com *{termo}*."

        linhas = [
            f"Encontrei {len(transacoes)} lançamento(s) com *{termo}*:"
        ]

        for t in transacoes:
            linhas.append(
                f"• #{t['id']} {_sinal(t['tipo'])} "
                f"{_moeda(t['valor'])} — {t['descricao']} "
                f"({t['categoria']})"
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


def _converter_data(valor: Any):
    """Converte "AAAA-MM-DD" em datetime. Devolve None quando não for possível."""

    if not valor:
        return None

    if isinstance(valor, datetime):
        return valor

    try:
        return datetime.strptime(
            str(valor).strip()[:10],
            "%Y-%m-%d",
        )

    except ValueError:
        return None


def _registrar_transacao(
    usuario_id: int,
    args: dict[str, Any],
) -> dict[str, Any]:

    valor = float(args["valor"])
    tipo = args["tipo"]
    categoria = normalizar_categoria(args.get("categoria"))
    descricao = (args.get("descricao") or "").strip()
    data = _converter_data(args.get("data"))

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

        if data:
            transacao.data = data

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        return {
            "sucesso": True,
            "transacao": {
                "id": transacao.id,
                "valor": float(transacao.valor),
                "tipo": transacao.tipo,
                "categoria": normalizar_categoria(transacao.categoria),
                "descricao": transacao.descricao,
                "data": (
                    transacao.data.isoformat()
                    if transacao.data
                    else None
                ),
            },
        }

    finally:
        db.close()


def _editar_transacao(
    usuario_id: int,
    args: dict[str, Any],
) -> dict[str, Any]:

    alteracoes = {}

    if args.get("valor") is not None:
        alteracoes["valor"] = float(args["valor"])

    if args.get("descricao"):
        alteracoes["descricao"] = str(args["descricao"])

    if args.get("categoria"):
        alteracoes["categoria"] = normalizar_categoria(
            args["categoria"]
        )

    if args.get("tipo"):
        alteracoes["tipo"] = str(args["tipo"])

    data = _converter_data(args.get("data"))

    if data:
        alteracoes["data"] = data

    if not alteracoes:
        return {
            "sucesso": False,
            "erro": "Nenhum campo para alterar foi informado.",
        }

    return editar_transacao(
        usuario_id,
        int(args["transacao_id"]),
        **alteracoes,
    )


def _executar_ferramenta(
    nome: str,
    args: dict[str, Any],
    usuario_id: int,
) -> dict[str, Any]:

    if nome == "registrar_transacao":
        return _registrar_transacao(usuario_id, args)

    if nome == "editar_transacao":
        return _editar_transacao(usuario_id, args)

    if nome == "excluir_transacao":
        return excluir_transacao(
            usuario_id,
            int(args["transacao_id"]),
        )

    if nome == "consultar_saldo":
        return consultar_saldo(usuario_id)

    if nome == "consultar_periodo":
        return consultar_periodo(
            usuario_id,
            _periodo_valido(args.get("periodo")) or "mes",
        )

    if nome == "consultar_gastos_mes":
        return {
            "total_gastos_mes": consultar_gastos_mes(usuario_id)
        }

    if nome == "consultar_ultimas_transacoes":
        return {
            "transacoes": serializar_transacoes(
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

    if nome == "consultar_gasto_categoria":
        return consultar_gasto_categoria(
            usuario_id,
            args["categoria"],
            periodo=_periodo_valido(args.get("periodo")),
            dias=args.get("dias"),
        )

    if nome == "buscar_transacoes":
        return {
            "transacoes": buscar_transacoes(
                usuario_id,
                termo=args.get("termo"),
                categoria=args.get("categoria"),
                tipo=args.get("tipo"),
                periodo=_periodo_valido(args.get("periodo")),
                dias=args.get("dias"),
                valor_min=args.get("valor_min"),
                valor_max=args.get("valor_max"),
                limite=args.get("limite", 10),
            )
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
