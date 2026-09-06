import re
import unicodedata


def normalizar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def extrair_valor(mensagem: str):
    texto = mensagem.lower().replace("r$", "")
    encontrados = re.findall(r"\d+(?:[.,]\d{1,2})?", texto)
    if not encontrados:
        return None

    bruto = encontrados[0]
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    return float(bruto)


def processar_mensagem(mensagem: str):
    texto = mensagem.strip()
    normalizado = normalizar_texto(texto)
    valor = extrair_valor(texto)

    if valor is None or valor <= 0:
        return {
            "sucesso": False,
            "resposta": "Não consegui identificar o valor. Exemplo: Gastei R$ 50 com combustível."
        }

    palavras_entrada = [
        "recebi", "ganhei", "entrou", "entrada", "salario", "pix recebido",
        "caiu na conta", "depositaram"
    ]
    tipo = "entrada" if any(palavra in normalizado for palavra in palavras_entrada) else "saida"

    if any(p in normalizado for p in [
        "combustivel", "gasolina", "etanol", "alcool", "abasteci", "abastecer", "abastecimento",
        "uber", "99", "taxi", "onibus", "transporte"
    ]):
        categoria = "Transporte"
    elif any(p in normalizado for p in [
        "mercado", "supermercado", "comida", "almoco", "jantar", "lanche", "restaurante", "padaria"
    ]):
        categoria = "Alimentação"
    elif any(p in normalizado for p in [
        "aluguel", "casa", "energia", "luz", "agua", "internet"
    ]):
        categoria = "Casa"
    elif any(p in normalizado for p in [
        "farmacia", "remedio", "medicamento"
    ]):
        categoria = "Saúde"
    elif any(p in normalizado for p in [
        "cinema", "viagem", "bar", "jogo", "lazer"
    ]):
        categoria = "Lazer"
    else:
        categoria = "Outros"

    return {
        "sucesso": True,
        "valor": valor,
        "tipo": tipo,
        "categoria": categoria,
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
