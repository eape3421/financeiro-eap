from datetime import date
from calendar import monthrange
from flask_sqlalchemy import SQLAlchemy

# 🔹 Inicializa o SQLAlchemy
db = SQLAlchemy()

# ============================
# 🔹 Modelo: Lançamento Geral
# ============================
class Lancamento(db.Model):
    __tablename__ = "lancamento"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # Receita ou Despesa
    categoria = db.Column(db.String(100), nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=False)

# ============================
# 🔹 Modelo: Categoria
# ============================
class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

# ============================
# 🔹 Modelo: Compra com Cartão
# ============================
class CompraCartao(db.Model):
    __tablename__ = "compras_cartao"

    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    cartao = db.Column(db.String(100), nullable=True)
    valor_total = db.Column(db.Numeric(12, 2), nullable=False)
    total_parcelas = db.Column(db.Integer, nullable=False)
    data_primeira_fatura = db.Column(db.Date, nullable=False)
    criado_em = db.Column(db.Date, default=date.today, nullable=False)

    parcelas = db.relationship(
        "ParcelaCartao",
        back_populates="compra",
        cascade="all, delete-orphan",
        lazy="joined"
    )

# ============================
# 🔹 Modelo: Parcela de Compra
# ============================
class ParcelaCartao(db.Model):
    __tablename__ = "parcelas_cartao"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    paga = db.Column(db.Boolean, default=False, nullable=False)

    compra_id = db.Column(db.Integer, db.ForeignKey("compras_cartao.id"), nullable=False, index=True)
    compra = db.relationship("CompraCartao", back_populates="parcelas")

# ============================
# 🔹 Função: Gerar Parcelas
# ============================
def gerar_parcelas(compra: CompraCartao):
    """Gera as parcelas com base no valor total e na data da primeira fatura."""
    valor_parcela = round(compra.valor_total / compra.total_parcelas, 2)
    parcelas = []
    data = compra.data_primeira_fatura

    for n in range(1, compra.total_parcelas + 1):
        parcela = ParcelaCartao(
            compra=compra,
            numero=n,
            valor=valor_parcela,
            vencimento=data,
            paga=False,
        )
        parcelas.append(parcela)
        data = proximo_mes(data)

    return parcelas

# ============================
# 🔹 Função Auxiliar: Próximo Mês
# ============================
def proximo_mes(d: date) -> date:
    """Calcula a mesma data no mês seguinte, ajustando para meses com menos dias."""
    ano = d.year + (1 if d.month == 12 else 0)
    mes = 1 if d.month == 12 else d.month + 1
    dia = min(d.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)



