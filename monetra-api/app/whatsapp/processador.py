import re
from app.whatsapp.consultas import consultar_gastos_mes

def processar_mensagem(mensagem: str):
    texto = mensagem.lower().strip()

    # Procura um valor em reais
    padrao_valor = r"(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)"
    encontrado = re.search(padrao_valor, texto)

    if not encontrado:
        return {
            "sucesso": False,
            "resposta": "Não consegui identificar o valor. Exemplo: Gastei 50 reais com combustível."
        }

    valor = encontrado.group(1).replace(",", ".")
    valor = float(valor)

    # Identifica se é entrada ou saída
    palavras_entrada = [
        "recebi",
        "ganhei",
        "entrou",
        "entrada",
        "salário",
        "salario",
        "pix recebido"
    ]

    tipo = "entrada" if any(
        palavra in texto for palavra in palavras_entrada
    ) else "saida"

    # Identifica categoria
    if any(palavra in texto for palavra in [
        "combustível",
        "combustivel",
        "gasolina",
        "etanol",
        "álcool",
        "alcool",
        "abasteci",
        "abastecer",
        "abastecimento",
    ]):
        categoria = "Transporte"

    elif any(palavra in texto for palavra in [
        "uber",
        "99",
        "taxi",
        "táxi",
        "ônibus",
        "onibus"
    ]):
        categoria = "Transporte"

    elif any(palavra in texto for palavra in [
        "mercado",
        "supermercado",
        "comida",
        "almoço",
        "almoco",
        "jantar",
        "lanche",
        "restaurante"
    ]):
        categoria = "Alimentação"

    elif any(palavra in texto for palavra in [
        "aluguel",
        "casa",
        "energia",
        "luz",
        "água",
        "agua",
        "internet"
    ]):
        categoria = "Casa"

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
    texto = mensagem.lower().strip()

    palavras_saldo = [
        "quanto eu tenho",
        "qual meu saldo",
        "meu saldo",
        "quanto tenho",
        "quanto dinheiro tenho",
        "saldo",
        "dinheiro disponível",
        "dinheiro disponivel"
    ]

    if any(frase in texto for frase in palavras_saldo):
        return "saldo"

    palavras_ultimas_transacoes = [
        "últimas transações",
        "ultimas transacoes",
        "últimos gastos",
        "ultimos gastos",
        "meus últimos gastos",
        "meus ultimos gastos",
        "meus gastos",
        "o que eu gastei",
        "mostrar gastos",
        "mostra meus gastos",
        "mostrar transações",
        "mostrar transacoes"
    ]

    if any(frase in texto for frase in palavras_ultimas_transacoes):
        return "ultimas_transacoes"

    palavras_gastos_mes= [
        "quanto gastei esse mês",
        "quanto gastei este mês",
        "quanto eu gastei esse mês",
        "quanto eu gastei este mês",
        "gastos do mês",
        "gastos desse mês",
        "total de gastos do mês",
        "total que gastei esse mês",
    ]

    