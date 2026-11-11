"""
Avalia o score de risco de duas formas:

1. BACKTEST (o que daria para fazer na vida real): taxa de irregularidade nas inspeções
   ALEATÓRIAS, separada pela faixa de score que o cliente tinha no mês anterior.
2. GABARITO (só possível porque os dados são simulados): compara a faixa do último mês
   com quem realmente estava desviando energia.

Uso:
    python src/avaliar_score.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import db

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    conexao = db.conectar()

    print("=== 1. Backtest: inspeções aleatórias x faixa do score no mês anterior ===")
    bt = db.consultar(conexao, """
        SELECT Faixa_Mes_Anterior AS Faixa, COUNT(*) AS Inspecoes, SUM(Irregular) AS Irregulares
        FROM dw.vw_inspecoes_score
        WHERE Origem = N'Aleatória'
        GROUP BY Faixa_Mes_Anterior""")
    bt["Taxa_Acerto"] = (bt.Irregulares / bt.Inspecoes).round(3)
    geral = bt.Irregulares.sum() / bt.Inspecoes.sum()
    print(bt.sort_values("Taxa_Acerto", ascending=False).to_string(index=False))
    print(f"Taxa geral das aleatórias: {geral:.1%}")

    print("\n=== 2. Por origem da inspeção (todas) ===")
    origem = db.consultar(conexao, """
        SELECT Origem, COUNT(*) AS Inspecoes, AVG(CAST(Irregular AS FLOAT)) AS Taxa_Acerto
        FROM dw.vw_inspecoes_score GROUP BY Origem ORDER BY Taxa_Acerto DESC""")
    print(origem.round(3).to_string(index=False))

    gabarito_arq = RAIZ / "dados_fonte" / "_gabarito_nao_carregar.csv.txt"
    if gabarito_arq.exists():
        print("\n=== 3. Gabarito da simulação (último mês com score) ===")
        gab = pd.read_csv(gabarito_arq, sep=";")
        ultimo = db.consultar(conexao, """
            SELECT Cliente_ID, Faixa, Score FROM dw.fScoreRisco
            WHERE Competencia = (SELECT MAX(Competencia) FROM dw.fScoreRisco)""")
        # quem já foi pego e regularizado deixa de ser fraudador ativo
        pegos = set(db.consultar(conexao, "SELECT Cliente_ID FROM dw.fInspecao WHERE Resultado = N'Irregularidade'").Cliente_ID)
        df = ultimo.merge(gab, on="Cliente_ID")
        df["Score"] = df.Score.astype(float)  # DECIMAL do SQL chega como Decimal do Python
        df["Desviando"] = df.Fraudador & ~df.Cliente_ID.isin(pegos)
        tabela = df.groupby("Faixa").agg(Clientes=("Cliente_ID", "size"), Desviando=("Desviando", "sum"))
        tabela["Precisao"] = (tabela.Desviando / tabela.Clientes).round(3)
        tabela["Pct_dos_Desvios"] = (tabela.Desviando / df.Desviando.sum()).round(3)
        print(tabela.to_string())
        top = df.nlargest(500, "Score")
        print(f"Top 500 por score: {top.Desviando.mean():.1%} estão desviando "
              f"(base: {df.Desviando.mean():.1%} dos clientes)")
    conexao.close()


if __name__ == "__main__":
    main()
