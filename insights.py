import secrets

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
