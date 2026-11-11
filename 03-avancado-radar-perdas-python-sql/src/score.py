"""
Score de risco de perda não técnica (0 a 100), por cliente e mês.

Escolha deliberada: um score de REGRAS PONDERADAS, e não um modelo de machine learning.
    - cada ponto tem explicação ("perdeu 30 pontos por queda brusca de consumo");
    - a equipe de campo e o jurídico entendem o motivo da inspeção;
    - funciona sem histórico rotulado. Quando houver inspeções suficientes,
      os pesos podem ser calibrados (ou trocados por um modelo), usando o backtest
      da view dw.vw_inspecoes_score como régua.

Componentes (pontos máximos):
    queda       40  consumo dos últimos 3 meses caiu em relação à linha de base do próprio cliente
    pares       20  consumo muito abaixo da mediana de clientes da mesma classe no mesmo alimentador
    baixo       10  meses com consumo mínimo (<= 30 kWh) no último semestre
    estimada    10  leituras estimadas (leiturista sem acesso ao medidor)
    pnt         15  alimentador com perda não técnica alta (o "bairro" já perde muito)
    historico    5  irregularidade confirmada anteriormente
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PESOS = {"queda": 40, "pares": 20, "baixo": 10, "estimada": 10, "pnt": 15, "historico": 5}
MOTIVOS = {
    "queda": "Queda brusca de consumo",
    "pares": "Consumo muito abaixo de clientes semelhantes",
    "baixo": "Meses com consumo mínimo ou zerado",
    "estimada": "Leituras estimadas (sem acesso ao medidor)",
    "pnt": "Alimentador com perda elevada",
    "historico": "Irregularidade anterior",
}
# Cortes calibrados no backtest: "Alto" ~ 3% dos clientes (cabe em ~2 meses de equipes de campo),
# "Médio" ~ 4%. As escalas de cada componente também foram ajustadas comparando variações.
CORTE_ALTO = 45
CORTE_MEDIO = 25


def _escala(valor: pd.Series, inicio: float, fim: float) -> pd.Series:
    """0 até 'inicio', 1 a partir de 'fim', linear no meio."""
    return ((valor - inicio) / (fim - inicio)).clip(0, 1)


def pontuar(features: pd.DataFrame) -> pd.DataFrame:
    """Recebe as linhas de dw.fn_features_cliente (todos os clientes dos meses pedidos)."""
    f = features.copy()
    numericas = ["Consumo_kWh", "Media_3m", "Media_Base", "Meses_Base", "Meses_Baixos_6m", "Leituras_Estimadas_6m",
                 "PNT_Pct_Alimentador", "Historico_Irregularidade"]
    f[numericas] = f[numericas].astype(float)
    # "clientes parecidos": mediana da mesma classe, no mesmo alimentador, no mesmo mês
    f["Mediana_Pares"] = f.groupby(["Alimentador_ID", "Classe", "Competencia"]).Consumo_kWh.transform("median")

    base_valida = (f.Meses_Base >= 3) & (f.Media_Base > 0)
    queda = (1 - f.Media_3m / f.Media_Base).where(base_valida, 0)
    razao_pares = (f.Media_3m / f.Mediana_Pares.replace(0, np.nan)).fillna(1)

    pts = pd.DataFrame({
        "queda": PESOS["queda"] * _escala(queda, 0.10, 0.50),
        "pares": PESOS["pares"] * _escala(1 - razao_pares, 0.30, 0.85),
        "baixo": PESOS["baixo"] * (f.Meses_Baixos_6m.clip(upper=6) / 6),
        "estimada": PESOS["estimada"] * _escala(f.Leituras_Estimadas_6m, 0, 3),
        "pnt": PESOS["pnt"] * _escala(f.PNT_Pct_Alimentador.fillna(0), 0.05, 0.30),
        "historico": PESOS["historico"] * f.Historico_Irregularidade,
    }, index=f.index).round(1)

    score = pts.sum(axis=1).round(1)
    faixa = np.select([score >= CORTE_ALTO, score >= CORTE_MEDIO], ["Alto", "Médio"], "Baixo")
    motivo = pts.idxmax(axis=1).map(MOTIVOS).where(score > 0, "Sem sinais relevantes")

    return pd.DataFrame({
        "Cliente_ID": f.Cliente_ID.astype(int),
        "Competencia": f.Competencia,
        "Score": score,
        "Faixa": faixa,
        "Motivo_Principal": motivo,
        "Pts_Queda": pts.queda,
        "Pts_Pares": pts.pares,
        "Pts_Consumo_Baixo": pts.baixo,
        "Pts_Estimada": pts.estimada,
        "Pts_PNT": pts.pnt,
        "Pts_Historico": pts.historico,
    })
