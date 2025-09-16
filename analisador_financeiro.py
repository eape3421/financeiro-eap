import pandas as pd


METAS = {
    'cartao_credito': 1500.00,
    'alimentacao': 800.00,
    'transporte': 300.00
}

def verificar_meta_cartao(df_lancamentos):
    """Verifica se os gastos no cartão ultrapassaram a meta"""
    gastos_cartao = df_lancamentos[df_lancamentos['forma_pagamento'] == 'Cartão']['valor'].sum()
    if gastos_cartao > METAS['cartao_credito']:
        excesso = gastos_cartao - METAS['cartao_credito']
        return f"⚠️ Você ultrapassou sua meta no cartão em R$ {excesso:.2f}."
    return "✅ Gastos no cartão estão dentro da meta."


def analisar_gastos_por_categoria(df_lancamentos):
    """Compara gastos por categoria com metas"""
    alertas = []
    categorias = df_lancamentos['tipo'].unique()
    for categoria in categorias:
        total = df_lancamentos[df_lancamentos['tipo'] == categoria]['valor'].sum()
        meta = METAS.get(categoria.lower())
        if meta and total > meta:
            excesso = total - meta
            alertas.append(f"📉 Categoria '{categoria}' ultrapassou a meta em R$ {excesso:.2f}.")
    return alertas


def sugestao_investimento(saldo_disponivel):
    """Sugere investimentos com base no saldo"""
    if saldo_disponivel >= 1000:
        return "💼 Considere aplicar em CDBs ou Tesouro Direto com liquidez diária."
    elif saldo_disponivel >= 500:
        return "📈 Que tal começar com um fundo de renda fixa conservador?"
    else:
        return "🔒 Priorize montar uma reserva de emergência antes de investir."


def gerar_alertas(df_lancamentos, saldo_disponivel):
    """Função principal que reúne todos os alertas"""
    alertas = []
    alertas.append(verificar_meta_cartao(df_lancamentos))
    alertas.extend(analisar_gastos_por_categoria(df_lancamentos))
    alertas.append(sugestao_investimento(saldo_disponivel))
    return alertas

