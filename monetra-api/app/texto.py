"""Ajudantes de texto compartilhados pela Prospere.

Concentra a normalização usada para comparar categorias, descrições e
intenções (sem acento, minúsculo) e a formatação de valores em reais.
"""

import unicodedata


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sem acentos e sem espaços nas pontas."""

    texto = (texto or "").lower().strip()

    texto = unicodedata.normalize("NFD", texto)

    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def formatar_moeda(valor) -> str:
    """Formata um número no padrão brasileiro: R$ 1.234,56."""

    return (
        f"R$ {float(valor):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
