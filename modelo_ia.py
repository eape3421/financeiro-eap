# modelo_ia.py

def classificar_texto(descricao: str, estabelecimento: str = "") -> str:
    """
    Classifica o texto em uma categoria financeira com base na descrição e no nome do estabelecimento.
    """
    descricao = descricao.lower()
    estabelecimento = estabelecimento.lower()

    if "mercado" in descricao or "supermercado" in estabelecimento:
        return "Alimentação"
    elif "uber" in descricao or "99" in estabelecimento:
        return "Transporte"
    elif "farmácia" in descricao or "remédio" in descricao:
        return "Saúde"
    elif "academia" in descricao:
        return "Bem-estar"
    elif "cinema" in descricao or "netflix" in estabelecimento:
        return "Lazer"
    else:
        return "Outros"

def gerar_insights(df, categorias) -> dict:
    """
    Gera insights financeiros com base nos dados e categorias.
    """
    dicas_economia = []
    dicas_investimentos = []

    if "Alimentação" in categorias and df[categorias == "Alimentação"]["valor"].sum() > 500:
        dicas_economia.append("Você pode economizar comprando em atacado ou planejando suas refeições.")

    if df["valor"].sum() > 2000:
        dicas_investimentos.append("Considere investir parte do seu dinheiro em renda fixa ou variável.")

    return {
        "dicas_economia": dicas_economia,
        "dicas_investimentos": dicas_investimentos
    }
