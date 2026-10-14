"""Categorias financeiras da Prospere.

Fonte única das categorias usadas pela assistente, pelo processador
determinístico e pela API. Os sinônimos existem para reconhecer variações
digitadas pelo usuário e nomes antigos já gravados no banco (por exemplo
"Casa", que hoje é "Moradia").
"""

from app.texto import normalizar_texto

CATEGORIAS_PADRAO = (
    "Alimentação",
    "Moradia",
    "Transporte",
    "Saúde",
    "Lazer",
    "Compras e assinaturas",
    "Educação",
    "Renda",
    "Investimentos",
    "Outros",
)

CATEGORIA_PADRAO = "Outros"

# Chave: texto normalizado (sem acento, minúsculo). Valor: categoria padrão.
ALIASES = {
    "alimentacao": "Alimentação",
    "supermercado": "Alimentação",
    "mercado": "Alimentação",
    "comida": "Alimentação",
    "restaurante": "Alimentação",
    "padaria": "Alimentação",
    "moradia": "Moradia",
    "casa": "Moradia",
    "aluguel": "Moradia",
    "contas": "Moradia",
    "transporte": "Transporte",
    "combustivel": "Transporte",
    "gasolina": "Transporte",
    "saude": "Saúde",
    "farmacia": "Saúde",
    "lazer": "Lazer",
    "entretenimento": "Lazer",
    "compras": "Compras e assinaturas",
    "assinaturas": "Compras e assinaturas",
    "educacao": "Educação",
    "cursos": "Educação",
    "renda": "Renda",
    "salario": "Renda",
    "recebimento": "Renda",
    "investimentos": "Investimentos",
    "economias": "Investimentos",
    "outros": "Outros",
    "outras": "Outros",
}


def normalizar_categoria(valor: str | None) -> str:
    """Devolve a categoria padrão correspondente ao texto informado.

    Categorias personalizadas (que não estão na lista padrão) são
    preservadas como o usuário escreveu.
    """

    if not valor or not str(valor).strip():
        return CATEGORIA_PADRAO

    texto = str(valor).strip()

    return ALIASES.get(normalizar_texto(texto), texto)


def categoria_citada(texto: str) -> str | None:
    """Categoria mencionada numa mensagem, se houver alguma conhecida."""

    procurado = normalizar_texto(texto)

    for chave, categoria in ALIASES.items():
        if f" {chave} " in f" {procurado} ":
            return categoria

    return None
