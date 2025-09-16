import calendar
from datetime import datetime

def prever_gastos(df_lancamentos, data_atual=None):
    if data_atual is None:
        data_atual = datetime.today()

    df_mes = df_lancamentos[
        (df_lancamentos['data'].dt.month == data_atual.month) &
        (df_lancamentos['data'].dt.year == data_atual.year) &
        (df_lancamentos['tipo'] == 'Despesa')
    ]

    if df_mes.empty:
        return 0.0

    gastos_por_dia = df_mes.groupby(df_mes['data'].dt.date)['valor'].sum()
    dias_com_gasto = len(gastos_por_dia)

    # 🔒 Se só há 1 dia com gasto, não prever ainda
    if dias_com_gasto < 2:
        print("⚠️ Dados insuficientes para previsão realista.")
        return 0.0

    media_diaria_real = gastos_por_dia.mean()
    dias_totais = calendar.monthrange(data_atual.year, data_atual.month)[1]
    dias_restantes = dias_totais - data_atual.day
    previsao = media_diaria_real * dias_restantes

    print("🔍 Dias com gasto:", dias_com_gasto)
    print("🔍 Média diária real:", media_diaria_real)
    print("🔍 Dias restantes:", dias_restantes)
    print("🔍 Previsão final:", previsao)

    return round(previsao, 2)



