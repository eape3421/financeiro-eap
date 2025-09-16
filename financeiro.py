import os
import secrets
import traceback
import time
import threading
import webbrowser
from decimal import Decimal
from datetime import datetime, date, timedelta

# 📦 Bibliotecas externas
import pandas as pd
from dotenv import load_dotenv

# 🌐 Flask e extensões
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 🧠 SQLAlchemy
from sqlalchemy import func, extract
from sqlalchemy.orm import joinedload, aliased

# 🧩 Módulos personalizados
from insights import Insights
from modelo_ia import classificar_texto, gerar_insights
from analisador_financeiro import gerar_alertas
from previsao import prever_gastos
from models import CompraCartao, ParcelaCartao, Lancamento, Categoria, gerar_parcelas, db
# from modulos.rotas import lancar


# 🔹 Carrega variáveis do .env
load_dotenv()

# 🔹 Inicializa o app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

# 🔧 Inicializa extensões
db.init_app(app)
migrate = Migrate(app, db)

@app.route("/lancar", methods=["GET", "POST"])
def lancar():
    try:
        if request.method == "POST":
            campos = ["competencia", "data", "descricao", "estabelecimento", "valor", "tipo", "forma_pagamento"]
            dados = {campo: request.form.get(campo) for campo in campos}

            if not all(dados.values()):
                flash("Todos os campos são obrigatórios.", "danger")
                return redirect(url_for("lancar"))

            try:
                valor = float(dados["valor"].replace(",", "."))
                if valor <= 0:
                    raise ValueError
            except ValueError:
                flash("Valor inválido. Use números positivos com ponto ou vírgula.", "danger")
                return redirect(url_for("lancar"))

            try:
                data = datetime.strptime(dados["data"], "%Y-%m-%d").date()
            except ValueError:
                flash("Data inválida. Use o formato AAAA-MM-DD.", "danger")
                return redirect(url_for("lancar"))

            categoria_nome = sugerir_categoria(f"{dados['descricao']} {dados['estabelecimento']}")
            categoria_obj = Categoria.query.filter_by(nome=categoria_nome).first()
            if not categoria_obj:
                categoria_obj = Categoria(nome=categoria_nome, tipo=dados["tipo"], meta_mensal=0.0)
                db.session.add(categoria_obj)
                db.session.commit()

            novo = Lancamento(
                competencia=dados["competencia"],
                data=data,
                descricao=dados["descricao"],
                estabelecimento=dados["estabelecimento"],
                valor=valor,
                tipo=dados["tipo"],
                categoria=categoria_obj.nome,
                forma_pagamento=dados["forma_pagamento"]
            )
            db.session.add(novo)
            db.session.commit()
            flash("Lançamento cadastrado com sucesso!", "success")

        df_lancamentos = carregar_lancamentos()
        receitas = df_lancamentos[df_lancamentos['tipo'] == 'Receita']['valor'].sum()
        despesas = df_lancamentos[df_lancamentos['tipo'] == 'Despesa']['valor'].sum()
        saldo_disponivel = receitas - despesas

        hoje = date.today()
        parcelas_futuras = ParcelaCartao.query.filter(
            ParcelaCartao.vencimento >= hoje,
            ParcelaCartao.paga == False
        ).all()
        total_parcelas_futuras = sum(float(p.valor) for p in parcelas_futuras)
        saldo_ajustado = saldo_disponivel - total_parcelas_futuras

        if saldo_disponivel > 1000:
            dica_aplicacao = "💼 Com esse saldo, você pode aplicar em CDBs com liquidez diária ou Tesouro Selic."
        elif saldo_disponivel > 500:
            dica_aplicacao = "📈 Que tal iniciar uma reserva de emergência com aportes mensais?"
        elif saldo_disponivel > 0:
            dica_aplicacao = "🔒 Evite gastos impulsivos. Considere guardar esse valor para imprevistos."
        else:
            dica_aplicacao = "⚠️ Seu saldo está negativo. Reveja seus gastos e priorize despesas essenciais."

        alertas_texto = gerar_alertas(df_lancamentos, saldo_disponivel)
        previsao_gastos = prever_gastos(df_lancamentos)

        alertas = []
        for texto in alertas_texto:
            alertas.append({
                'tipo': 'warning',
                'icone': '⚠️',
                'mensagem': texto,
                'acao': None
            })

        if previsao_gastos > 0:
            alertas.append({
                'tipo': 'info',
                'icone': '📊',
                'mensagem': f'Estimativa de gastos até o fim do mês: R$ {previsao_gastos:.2f}',
                'acao': 'Planejar orçamento'
            })

        categorias = df_lancamentos[df_lancamentos['tipo'] == 'Despesa'].groupby('categoria')['valor'].sum()
        categorias_json = {
            'labels': list(categorias.index),
            'valores': list(categorias.values)
        }

        df_lancamentos['data'] = pd.to_datetime(df_lancamentos['data'], errors='coerce')
        evolucao = df_lancamentos.groupby('data')['valor'].sum().reset_index()
        evolucao_json = {
            'datas': evolucao['data'].dt.strftime('%d/%m').tolist(),
            'saldos': evolucao['valor'].tolist()
        }

        resumo = {
            'receitas': round(receitas, 2),
            'despesas': round(despesas, 2),
            'saldo': round(saldo_disponivel, 2),
            'parcelas_futuras': round(total_parcelas_futuras, 2),
            'saldo_ajustado': round(saldo_ajustado, 2)
        }

        return render_template(
            "lancar.html",
            alertas=alertas,
            resumo=resumo,
            categorias_json=categorias_json,
            evolucao_json=evolucao_json,
            previsao_gastos=previsao_gastos,
            dica_aplicacao=dica_aplicacao
        )

    except Exception as e:
        print("❌ Erro interno na rota /lancar:", e)
        traceback.print_exc()
        flash("Ocorreu um erro inesperado. Tente novamente mais tarde.", "danger")

        return render_template(
            "lancar.html",
            alertas=[],
            resumo={
                'receitas': 0.0,
                'despesas': 0.0,
                'saldo': 0.0,
                'parcelas_futuras': 0.0,
                'saldo_ajustado': 0.0
            },
            categorias_json={'labels': [], 'valores': []},
            evolucao_json={'datas': [], 'saldos': []},
            previsao_gastos=0.0,
            dica_aplicacao=""
        )


# 🖥️ Abre o navegador com atraso
def abrir_navegador():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")

# 🚀 Executa o servidor
if __name__ == "__main__":
    threading.Thread(target=abrir_navegador).start()

    with app.app_context():
        db.create_all()

    print("🔧 Iniciando aplicação...")
    app.run(debug=False)


import os
import secrets

# 🔹 Pasta de uploads
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔹 Modelos do banco de dados
class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # Receita ou Despesa
    meta_mensal = db.Column(db.Float, nullable=True)

class Lancamento(db.Model):
    __tablename__ = 'lancamento'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    competencia = db.Column(db.String(7), nullable=False)
    data = db.Column(db.String(10), nullable=False)
    descricao = db.Column(db.String(100), nullable=False)
    estabelecimento = db.Column(db.String(100), nullable=True)
    valor = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=True)


# 🔹 Classe auxiliar para dicas de economia
class Insights:
    def __init__(self):
        self.dicas_economia = [
            "Evite gastos supérfluos.",
            "Use planilhas para controlar seu orçamento.",
            "Compare preços antes de comprar.",
            "Tenha uma reserva de emergência.",
            "Acompanhe seus gastos semanalmente."
        ]

    def dica_aleatoria(self):
        return secrets.choice(self.dicas_economia)

# 🔹 Importações de IA
from modelo_ia import classificar_texto, gerar_insights


# 🔹 Injeta a data atual nos templates
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# 🔹 Sugestão de aplicação com base em perfil e situação financeira
def gerar_dica_ia(saldo, perfil_risco, despesas_mes, meta_mensal):
    if saldo > 1000 and perfil_risco == "Conservador":
        return "Considere aplicar parte do seu saldo em um CDB com liquidez diária. Segurança e rendimento acima da poupança."
    elif saldo > 5000 and perfil_risco == "Arrojado":
        return "Você pode explorar fundos multimercado ou ações. Avalie com cautela e diversifique seus investimentos."
    elif despesas_mes == 0:
        return "Você ainda não lançou nenhuma despesa este mês. Que tal começar por uma categoria fixa como Alimentação?"
    elif saldo < meta_mensal:
        return "Você está abaixo da meta mensal. Reveja seus gastos com lazer ou delivery esta semana."
    else:
        return None

# 🔹 Wrapper para classificação de categoria via IA
def sugerir_categoria(texto):
    return classificar_texto(texto, "")



# 🔹 Rota para registrar nova compra parcelada no cartão
@app.route("/cartao/nova", methods=["GET", "POST"])
def nova_compra_cartao():
    if request.method == "POST":
        try:
            descricao = request.form["descricao"]
            cartao = request.form["cartao"]
            valor_total = float(request.form["valor_total"])
            total_parcelas = int(request.form["total_parcelas"])
            data_primeira = datetime.strptime(request.form["data_primeira_fatura"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            flash("Preencha todos os campos corretamente.", "danger")
            return redirect(url_for("nova_compra_cartao"))

        # 🔍 Verificação contra duplicatas
        compra_existente = CompraCartao.query.filter_by(
            descricao=descricao,
            cartao=cartao,
            valor_total=valor_total,
            total_parcelas=total_parcelas,
            data_primeira_fatura=data_primeira
        ).first()

        if compra_existente:
            flash("Essa compra já foi registrada anteriormente!", "warning")
            return redirect(url_for("nova_compra_cartao"))

        # ✅ Criação da nova compra
        compra = CompraCartao(
            descricao=descricao,
            cartao=cartao,
            valor_total=valor_total,
            total_parcelas=total_parcelas,
            data_primeira_fatura=data_primeira
        )

        db.session.add(compra)
        db.session.flush()

        parcelas = gerar_parcelas(compra)
        db.session.add_all(parcelas)
        db.session.commit()

        # 🧮 Verifica se houve ajuste na última parcela
        soma = sum(p.valor for p in parcelas)
        ajuste_final = round(Decimal(str(valor_total)) - soma, 2) != 0

        flash("Compra parcelada cadastrada com sucesso!", "success")
        return render_template("nova_compra_cartao.html", ajuste_final=ajuste_final, valor_total=valor_total)

    return render_template("nova_compra_cartao.html")

# 🔹 Rota para listar parcelas do cartão
@app.route("/cartao/parcelas")
def listar_parcelas():
    mes = request.args.get("mes")
    cartao = request.args.get("cartao")

    CompraAlias = aliased(CompraCartao)

    query = db.session.query(ParcelaCartao).select_from(ParcelaCartao).join(
        CompraAlias, ParcelaCartao.compra
    ).options(joinedload(ParcelaCartao.compra))

    if cartao:
        query = query.filter(CompraAlias.cartao.ilike(f"%{cartao}%"))

    if mes:
        try:
            ano, mes_num = map(int, mes.split("-"))
            query = query.filter(
                extract("year", ParcelaCartao.vencimento) == ano,
                extract("month", ParcelaCartao.vencimento) == mes_num
            )
        except ValueError:
            flash("Formato de mês inválido. Use AAAA-MM.", "warning")

    parcelas = query.order_by(ParcelaCartao.vencimento).all()
    total_valor = sum(p.valor for p in parcelas)
    total_parcelas = len(parcelas)

    return render_template(
        "parcelas_cartao.html",
        parcelas=parcelas,
        mes=mes,
        cartao=cartao,
        total_valor=total_valor,
        total_parcelas=total_parcelas
    )



# 🔹 Editar parcela individual
@app.route("/cartao/parcela/editar/<int:id>", methods=["GET", "POST"])
def editar_parcela(id):
    parcela = ParcelaCartao.query.get_or_404(id)

    if request.method == "POST":
        try:
            parcela.valor = float(request.form["valor"])
            parcela.vencimento = datetime.strptime(request.form["vencimento"], "%Y-%m-%d").date()
            db.session.commit()
            flash("Parcela atualizada com sucesso!", "success")
            return redirect(url_for("listar_parcelas"))
        except (ValueError, KeyError):
            flash("Erro ao atualizar parcela. Verifique os dados informados.", "danger")

    return render_template("editar_parcela.html", parcela=parcela)

# 🔹 Editar dados da compra (sem alterar parcelas)
@app.route("/cartao/editar/<int:id>", methods=["GET", "POST"])
def editar_compra_cartao(id):
    compra = CompraCartao.query.get_or_404(id)

    if request.method == "POST":
        try:
            compra.descricao = request.form["descricao"]
            compra.cartao = request.form["cartao"]
            compra.valor_total = float(request.form["valor_total"])
            compra.data_primeira_fatura = datetime.strptime(request.form["data_primeira_fatura"], "%Y-%m-%d").date()
            db.session.commit()
            flash("Compra atualizada com sucesso!", "success")
            return redirect(url_for("listar_parcelas"))
        except (ValueError, KeyError):
            flash("Erro ao atualizar compra. Verifique os dados informados.", "danger")

    return render_template("editar_compra_cartao.html", compra=compra)

# 🔹 Editar compra completa com todas as parcelas
@app.route("/cartao/compra/editar-completo/<int:id>", methods=["GET", "POST"])
def editar_compra_completa(id):
    compra = CompraCartao.query.get_or_404(id)

    if request.method == "POST":
        try:
            compra.descricao = request.form["descricao"]
            compra.cartao = request.form.get("cartao", "")
            compra.total_parcelas = int(request.form.get("total_parcelas", 0))

            for parcela in compra.parcelas:
                valor_key = f"valor_{parcela.id}"
                vencimento_key = f"vencimento_{parcela.id}"

                valor = request.form.get(valor_key)
                vencimento = request.form.get(vencimento_key)

                if valor:
                    parcela.valor = float(valor)

                if vencimento:
                    try:
                        parcela.vencimento = datetime.strptime(vencimento, "%Y-%m-%d").date()
                    except ValueError:
                        flash(f"Data inválida para a parcela {parcela.numero}. Use o formato AAAA-MM-DD.", "danger")

            db.session.commit()
            flash("Compra atualizada com sucesso!", "success")
            return redirect(url_for("listar_parcelas"))
        except Exception as e:
            flash("Erro ao atualizar compra completa.", "danger")
            print("❌ Erro:", e)

    return render_template("editar_compra_completa.html", compra=compra)

# 🔹 Alternar status de pagamento da parcela
@app.route("/cartao/parcela/<int:parcela_id>/toggle", methods=["POST"])
def toggle_parcela(parcela_id):
    parcela = ParcelaCartao.query.get_or_404(parcela_id)
    parcela.paga = not parcela.paga
    db.session.commit()
    status = "paga" if parcela.paga else "a vencer"
    flash(f"Parcela {parcela.numero}/{parcela.compra.total_parcelas} marcada como {status}.", "success")
    return redirect(request.referrer or url_for("listar_parcelas"))

# 🔹 API: Total de parcelas por mês
@app.route("/api/parcelas-por-mes")
def api_parcelas_por_mes():
    dados = db.session.query(
        extract("year", ParcelaCartao.vencimento).label("ano"),
        extract("month", ParcelaCartao.vencimento).label("mes"),
        db.func.sum(ParcelaCartao.valor).label("total")
    ).group_by("ano", "mes").order_by("ano", "mes").all()

    resultado = [
        {
            "mes": f"{int(mes):02d}/{ano}",
            "total": float(total)
        }
        for ano, mes, total in dados
    ]
    return jsonify(resultado)

# 🔹 Página de planejamento financeiro futuro
@app.route("/planejamento")
def planejamento_futuro():
    hoje = date.today()
    ano_atual = hoje.year

    dados = db.session.query(
        extract("year", ParcelaCartao.vencimento).label("ano"),
        extract("month", ParcelaCartao.vencimento).label("mes"),
        CompraCartao.cartao,
        db.func.count(ParcelaCartao.id).label("quantidade"),
        db.func.sum(ParcelaCartao.valor).label("total")
    ).join(CompraCartao).filter(
        ParcelaCartao.vencimento >= hoje,
        extract("year", ParcelaCartao.vencimento) == ano_atual
    ).group_by("ano", "mes", CompraCartao.cartao).order_by("ano", "mes").all()

    meses = {}
    for ano, mes, cartao, quantidade, total in dados:
        chave = f"{int(mes):02d}/{ano}"
        if chave not in meses:
            meses[chave] = []
        meses[chave].append({
            "cartao": cartao or "Não informado",
            "quantidade": quantidade,
            "total": float(total)
        })

    return render_template("planejamento.html", meses=meses)

# 🔹 API: Planejamento por cartão
@app.route("/api/planejamento-por-cartao")
def api_planejamento_por_cartao():
    hoje = date.today()
    ano_atual = hoje.year

    dados = db.session.query(
        extract("year", ParcelaCartao.vencimento).label("ano"),
        extract("month", ParcelaCartao.vencimento).label("mes"),
        CompraCartao.cartao,
        db.func.sum(ParcelaCartao.valor).label("total")
    ).join(CompraCartao).filter(
        ParcelaCartao.vencimento >= hoje,
        extract("year", ParcelaCartao.vencimento) == ano_atual
    ).group_by("ano", "mes", CompraCartao.cartao).order_by("ano", "mes").all()

    resultado = {}
    for ano, mes, cartao, total in dados:
        chave = f"{int(mes):02d}/{ano}"
        if chave not in resultado:
            resultado[chave] = {}
        resultado[chave][cartao or "Não informado"] = float(total)

    return jsonify(resultado)

# 🔹 Importar extrato bancário (.csv ou .txt)
@app.route("/importar-extrato", methods=["POST"])
def importar_extrato():
    file = request.files.get("extrato")
    if not file or not file.filename.lower().endswith((".csv", ".txt")):
        flash("Arquivo inválido. Use .csv ou .txt.", "danger")
        return redirect(url_for("lancar"))

    try:
        df = pd.read_csv(file)
        df.columns = [c.lower().strip() for c in df.columns]

        for _, row in df.iterrows():
            descricao = str(row.get("lançamentos", "")).strip()
            try:
                valor = float(row.get("valor", 0))
            except ValueError:
                valor = 0.0
            data = str(row.get("data", ""))[:10] if row.get("data") else ""
            tipo = "Despesa" if valor < 0 else "Receita"
            categoria = classificar_texto(descricao, "")
            competencia = data[:7] if data else ""

            lanc = Lancamento(
                competencia=competencia,
                data=data,
                descricao=descricao,
                estabelecimento="",
                valor=abs(valor),
                tipo=tipo,
                categoria=categoria
            )
            db.session.add(lanc)

        db.session.commit()
        flash("Extrato bancário importado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao importar extrato: {str(e)}", "danger")

    return redirect(url_for("lancar"))

# 🔹 Importar planilha Excel (.xlsx)
@app.route("/importar-planilha", methods=["POST"])
def importar_planilha():
    file = request.files.get("planilha")
    if not file or not file.filename.lower().endswith(".xlsx"):
        flash("Arquivo inválido. Use .xlsx.", "danger")
        return redirect(url_for("lancar"))

    try:
        df = pd.read_excel(file)
        df.columns = [c.lower().strip() for c in df.columns]

        for _, row in df.iterrows():
            descricao = str(row.get("descricao", "")).strip()
            estabelecimento = str(row.get("estabelecimento", "")).strip()
            try:
                valor = float(row.get("valor", 0))
            except ValueError:
                valor = 0.0
            tipo = str(row.get("tipo", "")).strip()
            categoria = classificar_texto(descricao, estabelecimento)
            competencia = str(row.get("competencia", "")).strip()
            data = str(row.get("data", ""))[:10] if row.get("data") else ""

            lanc = Lancamento(
                competencia=competencia,
                data=data,
                descricao=descricao,
                estabelecimento=estabelecimento,
                valor=valor,
                tipo=tipo,
                categoria=categoria
            )
            db.session.add(lanc)

        db.session.commit()
        flash("Planilha Excel importada com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao importar planilha: {str(e)}", "danger")

    return redirect(url_for("lancar"))

# 🔹 Gerenciar categorias (cadastro e visualização)
@app.route("/categorias", methods=["GET", "POST"])
def categorias():
    if request.method == "POST":
        nome = request.form.get("nome")
        tipo = request.form.get("tipo")
        meta = request.form.get("meta_mensal")

        if nome and tipo:
            try:
                nova = Categoria(
                    nome=nome.strip(),
                    tipo=tipo,
                    meta_mensal=float(meta) if meta else None
                )
                db.session.add(nova)
                db.session.commit()
                flash("Categoria cadastrada com sucesso!", "success")
            except Exception as e:
                flash(f"Erro ao cadastrar categoria: {str(e)}", "danger")
        else:
            flash("Preencha os campos obrigatórios: nome e tipo.", "warning")

        return redirect(url_for("categorias"))

    todas = Categoria.query.order_by(Categoria.tipo.desc(), Categoria.nome).all()
    return render_template("categorias.html", categorias=todas)


# 🔹 Função auxiliar: últimos n meses no formato AAAA-MM
def get_last_months(n=6):
    today = datetime.today().replace(day=1)
    y, m = today.year, today.month
    months = []
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))

# 🔹 Reclassificar lançamentos com categoria "Outros"
@app.route("/reclassificar_antigos")
def reclassificar_antigos():
    lancamentos = Lancamento.query.filter_by(categoria="Outros").all()
    atualizados = 0

    for l in lancamentos:
        texto = f"{l.descricao} {l.estabelecimento}"
        nova_categoria = sugerir_categoria(texto)

        if nova_categoria and nova_categoria != "Outros":
            categoria_obj = Categoria.query.filter_by(nome=nova_categoria).first()
            if not categoria_obj:
                categoria_obj = Categoria(
                    nome=nova_categoria,
                    tipo="Despesa",  # ou "Receita", dependendo do contexto
                    meta_mensal=None
                )
                db.session.add(categoria_obj)
                db.session.commit()

            l.categoria = categoria_obj.nome
            atualizados += 1

    db.session.commit()
    flash(f"{atualizados} lançamentos reclassificados com sucesso!", "info")
    return redirect(url_for("lancar"))

# 🔹 Editar lançamento individual
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    lanc = Lancamento.query.get_or_404(id)

    if request.method == "POST":
        try:
            lanc.data = request.form["data"]
            lanc.descricao = request.form["descricao"]
            lanc.estabelecimento = request.form["estabelecimento"]
            lanc.valor = float(request.form["valor"])
            lanc.tipo = request.form["tipo"]
            lanc.forma_pagamento = request.form["forma_pagamento"]
            lanc.categoria = classificar_texto(lanc.descricao, lanc.estabelecimento)
            db.session.commit()
            flash("Lançamento atualizado com sucesso!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Erro ao atualizar lançamento: {str(e)}", "danger")

    return render_template("editar.html", lancamento=lanc)

# 🔹 Excluir compra parcelada e suas parcelas
@app.route("/cartao/excluir/<int:compra_id>", methods=["POST"])
def excluir_compra_cartao(compra_id):
    compra = CompraCartao.query.get_or_404(compra_id)

    for parcela in compra.parcelas:
        db.session.delete(parcela)

    db.session.delete(compra)
    db.session.commit()

    flash("Compra e parcelas excluídas com sucesso!", "success")
    return redirect(url_for("listar_parcelas"))



# 🔹 Excluir lançamento individual
@app.route("/excluir/<int:id>")
def excluir(id):
    lanc = Lancamento.query.get_or_404(id)
    db.session.delete(lanc)
    db.session.commit()
    flash("Lançamento excluído com sucesso!", "success")
    return redirect(url_for("index"))

# 🔹 API: listar competências disponíveis
@app.route("/api/competencias")
def api_competencias():
    rows = db.session.query(Lancamento.competencia).distinct().all()
    comps = sorted([c[0] for c in rows if c[0]], reverse=True)
    return jsonify({"competencias": comps})

# 🔹 API: métricas ajustadas para o dashboard
@app.route("/api/metrics-ajustado")
def api_metrics_ajustado():
    competencia = request.args.get("competencia")
    filtros = [Lancamento.competencia == competencia] if competencia else []

    total_receitas = db.session.query(func.coalesce(func.sum(Lancamento.valor), 0.0))\
        .filter(Lancamento.tipo == "Receita", *filtros).scalar() or 0.0

    total_despesas = db.session.query(func.coalesce(func.sum(Lancamento.valor), 0.0))\
        .filter(Lancamento.tipo == "Despesa", *filtros).scalar() or 0.0

    saldo_real = total_receitas - total_despesas

    meta_total = db.session.query(func.coalesce(func.sum(Categoria.meta_mensal), 0.0))\
        .filter(Categoria.tipo == "Despesa").scalar() or 0.0

    progresso_meta = (total_despesas / meta_total) * 100.0 if meta_total > 0 else None

    parcelas_futuras = db.session.query(func.coalesce(func.sum(ParcelaCartao.valor), 0.0))\
        .filter(ParcelaCartao.vencimento > date.today(), ParcelaCartao.paga == False).scalar() or 0.0

    saldo_ajustado = saldo_real - float(parcelas_futuras)

    mostrar_alerta = saldo_real < 0 or (saldo_ajustado < 0 and parcelas_futuras > 0)

    return jsonify({
        "totalReceitas": total_receitas,
        "totalDespesas": total_despesas,
        "saldoReal": saldo_real,
        "parcelasFuturas": parcelas_futuras,
        "saldoAjustado": saldo_ajustado,
        "metaTotal": meta_total,
        "progressoMeta": progresso_meta,
        "mostrarAlerta": mostrar_alerta
    })

# 🔹 API: métricas simples para o dashboard
@app.route("/api/metrics")
def api_metrics():
    competencia = request.args.get("competencia")
    filtros = [Lancamento.competencia == competencia] if competencia else []

    total_receitas = db.session.query(func.coalesce(func.sum(Lancamento.valor), 0.0))\
        .filter(Lancamento.tipo == "Receita", *filtros).scalar() or 0.0

    total_despesas = db.session.query(func.coalesce(func.sum(Lancamento.valor), 0.0))\
        .filter(Lancamento.tipo == "Despesa", *filtros).scalar() or 0.0

    saldo = total_receitas - total_despesas

    meta_total = db.session.query(func.coalesce(func.sum(Categoria.meta_mensal), 0.0))\
        .filter(Categoria.tipo == "Despesa").scalar() or 0.0

    progresso_meta = (total_despesas / meta_total) * 100.0 if meta_total > 0 else None

    return jsonify({
        "totalReceitas": total_receitas,
        "totalDespesas": total_despesas,
        "saldo": saldo,
        "metaTotal": meta_total,
        "progressoMeta": progresso_meta
    })


# 🔹 API: Despesas por categoria
@app.route("/api/charts/despesas-por-categoria")
def api_despesas_por_categoria():
    competencia = request.args.get("competencia")
    q = db.session.query(
        Lancamento.categoria,
        func.coalesce(func.sum(Lancamento.valor), 0.0).label("total")
    ).filter(Lancamento.tipo == "Despesa")

    if competencia:
        q = q.filter(Lancamento.competencia == competencia)

    q = q.group_by(Lancamento.categoria).order_by(func.sum(Lancamento.valor).desc())
    data = [{"categoria": r.categoria, "total": float(r.total or 0)} for r in q.all()]
    return jsonify({"data": data})

# 🔹 API: Fluxo mensal (últimos 6 meses)
@app.route("/api/charts/fluxo-mensal")
def api_fluxo_mensal():
    months = get_last_months(6)
    rows = db.session.query(
        Lancamento.competencia,
        Lancamento.tipo,
        func.coalesce(func.sum(Lancamento.valor), 0.0).label("total")
    ).filter(Lancamento.competencia.in_(months))\
     .group_by(Lancamento.competencia, Lancamento.tipo).all()

    agg = {m: {"Receita": 0.0, "Despesa": 0.0} for m in months}
    for comp, tipo, total in rows:
        if comp in agg:
            agg[comp][tipo] = float(total or 0.0)

    return jsonify({
        "labels": months,
        "receitas": [agg[m]["Receita"] for m in months],
        "despesas": [agg[m]["Despesa"] for m in months]
    })



# 🔧 Função auxiliar
def carregar_lancamentos():
    try:
        lancamentos = Lancamento.query.all()
        dados = [{
            "data": l.data,
            "competencia": l.competencia,
            "descricao": l.descricao,
            "estabelecimento": l.estabelecimento,
            "valor": float(l.valor),
            "tipo": l.tipo,
            "categoria": l.categoria,
            "forma_pagamento": l.forma_pagamento
        } for l in lancamentos]

        df = pd.DataFrame(dados)
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        return df
    except Exception as e:
        print("⚠️ Erro ao carregar lançamentos:", e)
        return pd.DataFrame()

# 🔹 API: Sugestão de aplicação financeira
@app.route('/api/sugestao_aplicacao', methods=['POST'])
def sugestao_aplicacao():
    data = request.json
    saldo = float(data.get('saldo_atual', 0))
    meta = float(data.get('meta', 0))
    aporte = float(data.get('aporte_mensal', 0))
    perfil = data.get('perfil', 'conservador')
    prazo = int(data.get('prazo_meses', 12))

    if perfil == "conservador":
        opcoes = ["Tesouro Selic", "CDB com liquidez diária"]
    elif perfil == "moderado":
        opcoes = ["CDB com vencimento curto", "Fundos de Renda Fixa"]
    else:
        opcoes = ["Fundos multimercado", "ETFs de renda fixa"]

    crescimento = []
    saldo_simulado = saldo
    for mes in range(prazo):
        saldo_simulado += aporte
        saldo_simulado *= 1.003
        crescimento.append(round(saldo_simulado, 2))

    meta_atingida = saldo_simulado >= meta
    alerta = "Meta será atingida!" if meta_atingida else "Meta não será atingida com esse aporte."

    if not meta_atingida:
        saldo_temp = saldo
        fator = sum([(1.003) ** i for i in range(1, prazo + 1)])
        try:
            aporte_ideal = (meta - saldo_temp * (1.003) ** prazo) / fator
        except ZeroDivisionError:
            aporte_ideal = aporte
    else:
        aporte_ideal = aporte

    return jsonify({
        "aporte_mensal": round(aporte, 2),
        "opcoes": opcoes,
        "projecao": crescimento,
        "alerta": alerta,
        "aporte_ideal": round(aporte_ideal, 2)
    })

# 🔹 Impressão das rotas registradas
print("Rotas registradas:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint} → {rule.rule}")

# 🔹 Geração de alertas com IA
with app.app_context():
    try:
        engine = db.engine
        df = pd.read_sql('SELECT * FROM lancamento', engine)

        if df.empty:
            print("⚠️ Nenhum lançamento encontrado.")
        else:
            if 'data' in df.columns:
                df['data'] = pd.to_datetime(df['data'], errors='coerce')

            saldo = 1200.00
            alertas = gerar_alertas(df, saldo)
            for alerta in alertas:
                print(alerta)

    except Exception as e:
        print(f"❌ Erro ao carregar dados: {e}")

# 🔹 Função auxiliar para carregar dados ao iniciar
def carregar_dados_iniciais():
    with app.app_context():
        try:
            df = pd.read_sql('SELECT * FROM lancamento', db.engine)
            print("📊 Dados carregados com sucesso:")
            print(df.head())
        except Exception as e:
            print(f"⚠️ Erro ao carregar dados: {e}")

# 🔹 Função para carregar DataFrame
def carregar_dataframe():
    engine = db.get_engine(current_app)
    df = pd.read_sql('SELECT * FROM lancamento', engine)
    return df


# 🔹 Rota para exibir tabela de lançamentos
@app.route("/tabela")
def mostrar_tabela():
    try:
        query = '''
            SELECT descricao, valor, data, tipo, categoria, forma_pagamento FROM lancamento
        '''
        df = pd.read_sql(query, db.engine)

        df = df.rename(columns={
            'descricao': 'compra',
            'data': 'vencimento'
        })

        df['vencimento'] = pd.to_datetime(df['vencimento'], errors='coerce')
        compras = df.to_dict(orient="records")

        return render_template("tabela.html", compras=compras)

    except Exception as e:
        print(f"❌ Erro ao carregar dados para a tabela: {e}")
        return render_template("tabela.html", compras=[])

# 🔹 Rota para marcar lançamento como pago
@app.route("/marcar-paga/<int:id>", methods=["POST"])
def marcar_paga(id):
    lancamento = Lancamento.query.get_or_404(id)
    if hasattr(lancamento, "status"):
        lancamento.status = "Paga"
        db.session.commit()
    return redirect(url_for("mostrar_tabela"))

# 🧪 Rota de exemplo para criar compra fictícia
@app.route("/debug/criar_compra_exemplo")
def criar_compra_exemplo():
    compra = CompraCartao(
        descricao="Notebook",
        cartao="Nubank",
        valor_total=3000.00,
        total_parcelas=10,
        data_primeira_fatura=date(2025, 10, 5),
    )
    db.session.add(compra)
    db.session.flush()

    parcelas = gerar_parcelas(compra)
    db.session.add_all(parcelas)
    db.session.commit()

    return jsonify({
        "compra_id": compra.id,
        "descricao": compra.descricao,
        "total_parcelas": compra.total_parcelas,
        "parcelas_criadas": [
            {
                "n": p.numero,
                "valor": float(p.valor),
                "vencimento": p.vencimento.isoformat(),
                "paga": p.paga
            } for p in compra.parcelas
        ]
    })
    
    

    

# 🔍 Diagnóstico de lançamentos em HTML
@app.route("/diagnostico/lancamentos")
def diagnostico_lancamentos():
    df = carregar_dataframe()

    if df.empty:
        return "<h3 style='color:orange;'>⚠️ Nenhum lançamento encontrado.</h3>"

    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.strftime('%d/%m/%Y')

    html_tabela = df.to_html(classes="table table-bordered table-striped", index=False)

    return f"""
    <html>
    <head>
      <title>Diagnóstico de Lançamentos</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="container mt-4">
      <h2><i class="bi bi-search me-2"></i>Diagnóstico de Lançamentos</h2>
      {html_tabela}
    </body>
    </html>
    """




# 🔧 Função auxiliar para testar conexão
def testar_conexao():
    try:
        query = '''
            SELECT descricao, valor, data, tipo, categoria, forma_pagamento FROM lancamento
        '''
        df = pd.read_sql(query, db.engine)
        print("✅ Conexão bem-sucedida:")
        print(df.head())
    except Exception as e:
        print(f"❌ Erro ao carregar dados: {e}")

@app.route("/")
def index():
    try:
        lancamentos = Lancamento.query.order_by(Lancamento.data.desc()).all()
        categorias = Categoria.query.all()
        dica = Insights().dica_aleatoria()
        return render_template("index.html", lancamentos=lancamentos, categorias=categorias, dica=dica, now=datetime.now())
    except Exception as e:
        return f"<h1>Erro na rota /</h1><p>{e}</p>"



# 🔁 Executa a aplicação Flask
if __name__ == "__main__":
    from time import sleep
    import webbrowser

    with app.app_context():
        print("🔧 Testando conexão com o banco...")
        try:
            df = pd.read_sql('SELECT * FROM lancamento', db.engine)
            print("✅ Conexão bem-sucedida. Primeiros lançamentos:")
            print(df.head())
        except Exception as e:
            print(f"❌ Erro ao carregar dados iniciais: {e}")

        print("\n🔍 Rotas registradas:")
        for rule in app.url_map.iter_rules():
            print(f"📌 {rule.endpoint} → {rule.rule}")

    # 🧭 Abre o navegador após pequeno atraso
    sleep(2)
    webbrowser.open("http://127.0.0.1:5000")

    # 🚀 Inicia o servidor Flask
    print("\n🚀 Iniciando aplicação...")
    app.run(debug=False, use_reloader=False)






