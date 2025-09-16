from unidecode import unidecode

# Dicionário de palavras-chave por categoria
CATEGORIAS_PALAVRAS = {
    "Contas e Serviços": ["agua", "luz", "internet", "celular"],
    "Moradia": ["condominio", "aluguel"],
    "Educação": ["escola", "concurso", "curso", "faculdade"],
    "Transporte": ["carro", "ipva", "prestacao", "combustivel", "uber"],
    "Renda": ["salario", "freela", "pagamento"],
    "Família": ["mesada", "familia", "filho"],
    "Financeiro": ["cartao", "credito", "juros", "fatura"],
    "Alimentação": ["mercado", "supermercado", "padaria", "restaurante", "pizza"],
    "Saúde": ["farmacia", "remedio", "consulta", "dentista"],
    "Lazer": ["cinema", "viagem", "bar", "show"],
    "Outros": []  # Categoria padrão
}

def sugerir_categoria(descricao):
    """
    Sugere uma categoria com base na descrição textual de um lançamento.
    Normaliza o texto e verifica palavras-chave em cada grupo.
    """
    descricao = unidecode(descricao.lower())

    for categoria, palavras in CATEGORIAS_PALAVRAS.items():
        if any(palavra in descricao for palavra in palavras):
            return categoria

    return "Outros"


