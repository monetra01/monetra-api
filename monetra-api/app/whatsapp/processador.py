import re

from app.categorias import CATEGORIA_PADRAO
from app.texto import normalizar_texto


def extrair_valores(mensagem: str) -> list[float]:
    """Todos os valores numéricos encontrados na mensagem, na ordem."""

    texto = mensagem.lower().replace("r$", "")

    valores = []

    for bruto in re.findall(r"\d+(?:[.,]\d{1,2})?", texto):

        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")

        valores.append(float(bruto))

    return valores


def extrair_valor(mensagem: str):
    valores = extrair_valores(mensagem)

    return valores[0] if valores else None


# Palavras que indicam dinheiro entrando.
PALAVRAS_ENTRADA = (
    "recebi",
    "ganhei",
    "entrou",
    "entrada",
    "entradas",
    "recebimento",
    "recebimentos",
    "salario",
    "salário",
    "renda",
    "faturei",
    "comissao",
    "comissões",
    "bonus",
    "bônus",
    "bonificacao",
    "bonificação",
    "freela",
    "freelance",
    "pix recebido",
    "caiu na conta",
    "depositaram",
)


# Categorias por palavra-chave. A primeira que casar é usada.
PALAVRAS_CATEGORIA = (
    (
        "Transporte",
        (
            "combustivel",
            "combustível",
            "gasolina",
            "etanol",
            "alcool",
            "álcool",
            "abasteci",
            "abastecer",
            "abastecimento",
            "uber",
            "taxi",
            "táxi",
            "onibus",
            "ônibus",
            "transporte",
            "estacionamento",
            "pedagio",
            "pedágio",
            "metro",
            "metrô",
        ),
    ),
    (
        "Alimentação",
        (
            "mercado",
            "supermercado",
            "comida",
            "almoco",
            "almoço",
            "jantar",
            "lanche",
            "restaurante",
            "padaria",
            "ifood",
            "cafe",
            "café",
        ),
    ),
    (
        "Moradia",
        (
            "aluguel",
            "casa",
            "energia",
            "luz",
            "agua",
            "água",
            "internet",
            "condominio",
            "condomínio",
            "faxina",
        ),
    ),
    (
        "Saúde",
        (
            "farmacia",
            "farmácia",
            "remedio",
            "remédio",
            "medicamento",
            "medico",
            "médico",
            "dentista",
            "exame",
            "academia",
        ),
    ),
    (
        "Lazer",
        (
            "cinema",
            "viagem",
            "bar",
            "lazer",
            "show",
            "ingresso",
            "festa",
            "jogo",
        ),
    ),
    (
        "Compras e assinaturas",
        (
            "compra",
            "compras",
            "roupa",
            "shopping",
            "assinatura",
            "assinaturas",
            "netflix",
            "spotify",
            "streaming",
            "amazon",
        ),
    ),
    (
        "Educação",
        (
            "curso",
            "faculdade",
            "escola",
            "livro",
            "mensalidade",
            "educacao",
            "educação",
        ),
    ),
    (
        "Investimentos",
        (
            "investimento",
            "investi",
            "aporte",
            "poupanca",
            "poupança",
            "reserva",
            "tesouro",
            "cdb",
            "acoes",
            "ações",
            "cripto",
            "bitcoin",
        ),
    ),
)


def classificar_categoria(normalizado: str, tipo: str) -> str:
    """Categoria provável da mensagem.

    Recebimentos entram sempre como Renda, conforme o padrão da Prospere.
    """

    if tipo == "entrada":
        return "Renda"

    for categoria, palavras in PALAVRAS_CATEGORIA:

        if any(palavra in normalizado for palavra in palavras):
            return categoria

    return CATEGORIA_PADRAO


def processar_mensagem(mensagem: str):
    texto = mensagem.strip()
    normalizado = normalizar_texto(texto)
    valor = extrair_valor(texto)

    if valor is None or valor <= 0:
        return {
            "sucesso": False,
            "resposta": "Não consegui identificar o valor. Exemplo: Gastei R$ 50 com combustível."
        }

    tipo = "entrada" if any(
        palavra in normalizado for palavra in PALAVRAS_ENTRADA
    ) else "saida"

    return {
        "sucesso": True,
        "valor": valor,
        "tipo": tipo,
        "categoria": classificar_categoria(normalizado, tipo),
        "descricao": texto
    }


def identificar_consulta(mensagem: str):
    texto = normalizar_texto(mensagem)

    palavras_saldo = [
        "quanto eu tenho", "qual meu saldo", "meu saldo", "quanto tenho",
        "quanto dinheiro tenho", "saldo", "dinheiro disponivel", "quanto sobrou"
    ]
    if any(frase in texto for frase in palavras_saldo):
        return "saldo"

    palavras_gastos_mes = [
        "quanto gastei esse mes", "quanto gastei este mes",
        "quanto eu gastei esse mes", "quanto eu gastei este mes",
        "gastos do mes", "gastos desse mes", "total de gastos do mes",
        "total que gastei esse mes", "quanto gastei no mes"
    ]
    if any(frase in texto for frase in palavras_gastos_mes):
        return "gastos_mes"

    palavras_ultimas_transacoes = [
        "ultimas transacoes", "ultimos gastos", "meus ultimos gastos",
        "meus gastos", "o que eu gastei", "mostrar gastos", "mostra meus gastos",
        "mostrar transacoes", "minhas transacoes", "historico de gastos"
    ]
    if any(frase in texto for frase in palavras_ultimas_transacoes):
        return "ultimas_transacoes"

    return None


# =========================================================
# CORREÇÃO E EXCLUSÃO DE LANÇAMENTOS
# =========================================================

VERBOS_EXCLUSAO = (
    "excluir", "exclui", "exclua",
    "deletar", "deleta", "delete",
    "apagar", "apaga", "apague",
    "remover", "remove", "remova",
)

VERBOS_EDICAO = (
    "editar", "edita", "edite",
    "alterar", "altera", "altere",
    "corrigir", "corrige", "corrija", "corrigindo",
    "ajustar", "ajusta", "ajuste",
    "trocar", "troca", "troque",
    "mudar", "muda", "mude",
)

PADRAO_VERBO = re.compile(
    r"\b(" + "|".join(VERBOS_EXCLUSAO + VERBOS_EDICAO) + r")\b"
)

MARCADORES_CORRECAO = (
    "na verdade",
    "errei",
    "errado",
    "nao foram",
    "nao foi",
)

# Palavras que apenas ligam a frase ao lançamento e não ajudam a identificá-lo.
PALAVRAS_IGNORADAS = {
    "a", "o", "as", "os", "um", "uma",
    "meu", "minha", "meus", "minhas",
    "do", "da", "dos", "das", "de",
    "no", "na", "nos", "nas",
    "que", "para", "por", "pra",
    "transacao", "transacoes", "lançamento", "lancamento", "lançamentos",
    "lancamentos", "gasto", "gastos", "despesa", "despesas",
    "entrada", "entradas", "registro", "registros", "conta", "valor",
}

PALAVRAS_ULTIMA = {"ultima", "ultimo", "ultimas", "ultimos"}


def identificar_correcao(mensagem: str):
    """Reconhece um pedido de correção ou exclusão de lançamento.

    Devolve None quando a mensagem não é um pedido de correção/exclusão.
    """

    texto = (mensagem or "").strip().lower()
    normalizado = normalizar_texto(mensagem)

    if not texto:
        return None

    valores = extrair_valores(mensagem)

    # "Corrigindo, não foram 20, foram 15" — correção apenas do valor.
    if any(marcador in normalizado for marcador in MARCADORES_CORRECAO) and len(valores) >= 2:
        return {
            "acao": "editar",
            "termo": None,
            "valor": valores[-1],
            "valor_antigo": valores[0],
            "ultima": False,
        }

    encontrado = PADRAO_VERBO.search(texto)

    if not encontrado:
        return None

    verbo = encontrado.group(1)
    acao = "excluir" if verbo in VERBOS_EXCLUSAO else "editar"

    resto = texto[encontrado.end():].strip(" .,:;!?")

    termo = resto
    valor = None

    if acao == "editar":

        separador = re.search(r"\b(para|por|pra)\b", resto)

        if separador:

            novos = extrair_valores(resto[separador.end():])

            if novos:
                valor = novos[0]
                termo = resto[:separador.start()]

        else:

            numeros = extrair_valores(resto)

            if len(numeros) == 1:
                valor = numeros[0]
                termo = re.sub(r"\d+(?:[.,]\d{1,2})?", "", resto)

    ultima = False
    palavras = [p for p in re.split(r"[\s,]+", termo) if p]

    while palavras:

        chave = normalizar_texto(palavras[0])

        if chave in PALAVRAS_ULTIMA:
            ultima = True
            palavras.pop(0)
            continue

        if chave in PALAVRAS_IGNORADAS:
            palavras.pop(0)
            continue

        break

    termo_final = " ".join(palavras).strip(" .,:;!?")

    return {
        "acao": acao,
        "termo": termo_final or None,
        "valor": valor,
        "valor_antigo": None,
        "ultima": ultima,
    }
