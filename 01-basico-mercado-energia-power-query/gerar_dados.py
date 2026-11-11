"""
Projeto 1 (básico) - Mercado de Energia da Área de Concessão
Gera os dados brutos, PROPOSITALMENTE SUJOS, que serão tratados no Power Query.

Uso:
    python gerar_dados.py

Saída (pasta dados/brutos):
    faturamento/faturamento_AAAA-MM.csv  -> um arquivo por mês, exportado do "sistema comercial"
    municipios.xlsx                       -> cadastro de municípios e regionais
    metas_regionais.xlsx                  -> metas de mercado em formato "largo" (meses nas colunas)
    de_para_classes.csv                   -> tabela de padronização das classes de consumo

Todos os dados são SIMULADOS. A mesma semente gera sempre os mesmos arquivos.
"""
from __future__ import annotations

import random
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

SEMENTE = 2025
PASTA = Path(__file__).resolve().parent / "dados" / "brutos"
MESES = pd.period_range("2025-01", "2026-10", freq="M")          # dados realizados
MESES_META = pd.period_range("2025-01", "2026-12", freq="M")     # metas vão até dez/2026

# (município, regional, peso do mercado, participação de clientes rurais)
MUNICIPIOS = [
    ("Rio de Janeiro", "Capital", 6200, 0.001),
    ("Duque de Caxias", "Baixada Fluminense", 810, 0.004),
    ("Nova Iguaçu", "Baixada Fluminense", 790, 0.006),
    ("Belford Roxo", "Baixada Fluminense", 480, 0.002),
    ("São João de Meriti", "Baixada Fluminense", 440, 0.0),
    ("Mesquita", "Baixada Fluminense", 165, 0.0),
    ("Nilópolis", "Baixada Fluminense", 150, 0.0),
    ("Queimados", "Baixada Fluminense", 140, 0.004),
    ("Itaguaí", "Baixada Fluminense", 120, 0.012),
    ("Japeri", "Baixada Fluminense", 100, 0.01),
    ("Seropédica", "Baixada Fluminense", 80, 0.03),
    ("Paracambi", "Baixada Fluminense", 50, 0.03),
    ("Volta Redonda", "Sul Fluminense", 260, 0.004),
    ("Barra Mansa", "Sul Fluminense", 170, 0.02),
    ("Resende", "Sul Fluminense", 130, 0.025),
    ("Barra do Piraí", "Sul Fluminense", 95, 0.04),
    ("Valença", "Sul Fluminense", 70, 0.07),
    ("Itatiaia", "Sul Fluminense", 30, 0.03),
    ("Piraí", "Sul Fluminense", 28, 0.06),
    ("Pinheiral", "Sul Fluminense", 25, 0.03),
    ("Porto Real", "Sul Fluminense", 20, 0.02),
    ("Rio Claro", "Sul Fluminense", 18, 0.09),
    ("Quatis", "Sul Fluminense", 13, 0.07),
    ("Rio das Flores", "Sul Fluminense", 9, 0.12),
    ("Vassouras", "Centro-Sul Fluminense", 35, 0.08),
    ("Paty do Alferes", "Centro-Sul Fluminense", 27, 0.11),
    ("Miguel Pereira", "Centro-Sul Fluminense", 25, 0.06),
    ("Mendes", "Centro-Sul Fluminense", 18, 0.05),
    ("Engenheiro Paulo de Frontin", "Centro-Sul Fluminense", 14, 0.08),
]

# classe: (participação nos clientes, kWh por cliente/mês, tarifa média R$/kWh em 2025, peso da sazonalidade)
CLASSES = {
    "Residencial": (None, 175, 1.02, 1.0),   # participação = o que sobra
    "Comercial": (0.080, 1050, 0.98, 0.8),
    "Industrial": (0.004, 14000, 0.82, 0.3),
    "Rural": (None, 320, 0.68, 0.5),          # participação vem do município
    "Poder Público": (0.006, 2800, 0.93, 0.6),
}

# verão carioca = ar-condicionado ligado
SAZONALIDADE = [1.12, 1.15, 1.10, 1.02, 0.95, 0.90, 0.88, 0.90, 0.94, 0.98, 1.03, 1.08]

# como cada classe aparece "escrita" no sistema de origem (o problema que o Power Query vai resolver)
VARIANTES_CLASSE = {
    "Residencial": (["Residencial", "RESIDENCIAL", "RES", "Res.", " residencial"], [0.55, 0.2, 0.1, 0.1, 0.05]),
    "Comercial": (["Comercial", "COMERCIAL", "COM", "Com.", "Comercial/Serviços"], [0.55, 0.2, 0.1, 0.1, 0.05]),
    "Industrial": (["Industrial", "INDUSTRIAL", "IND", "Ind."], [0.6, 0.2, 0.1, 0.1]),
    "Rural": (["Rural", "RURAL", "RUR"], [0.7, 0.2, 0.1]),
    "Poder Público": (["Poder Público", "PODER PUBLICO", "PP", "Poder Publico"], [0.6, 0.2, 0.1, 0.1]),
}


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def fmt_inteiro(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_decimal(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_base_limpa(rng: np.random.Generator) -> pd.DataFrame:
    """Gera o faturamento 'verdadeiro' (limpo). Depois ele é sujado na exportação."""
    linhas = []
    for i, periodo in enumerate(MESES):
        mes, ano = periodo.month, periodo.year
        reajuste = 1.065 if (ano, mes) >= (2026, 3) else 1.0  # reajuste tarifário anual
        crescimento = 1.015 if ano == 2026 else 1.0
        for cod, (nome, regional, peso, rural) in enumerate(MUNICIPIOS, start=1):
            total_clientes = peso * 450 * (1.0012 ** i)
            participacao = {
                "Comercial": 0.080, "Industrial": 0.004, "Poder Público": 0.006, "Rural": rural,
            }
            participacao["Residencial"] = 1 - sum(participacao.values())
            for classe, (_, kwh, tarifa, peso_saz) in CLASSES.items():
                clientes = round(total_clientes * participacao[classe])
                if clientes == 0:
                    continue
                kwh_cliente = kwh * (1.8 if classe == "Industrial" and regional == "Sul Fluminense" else 1.0)
                saz = 1 + (SAZONALIDADE[mes - 1] - 1) * peso_saz
                consumo = clientes * kwh_cliente * saz * crescimento * rng.normal(1, 0.03)
                tarifa_mes = tarifa * reajuste * rng.normal(1, 0.01)
                linhas.append({
                    "Periodo": periodo, "Cod_Municipio": f"MUN{cod:03d}", "Municipio": nome,
                    "Regional": regional, "Classe": classe, "Qtd_Clientes": clientes,
                    "Consumo_kWh": round(consumo, 2), "Valor_Faturado": round(consumo * tarifa_mes, 2),
                })
    return pd.DataFrame(linhas)


def exportar_faturamento(base: pd.DataFrame, rnd: random.Random) -> None:
    pasta = PASTA / "faturamento"
    pasta.mkdir(parents=True, exist_ok=True)
    for periodo, df in base.groupby("Periodo"):
        registros = []
        for r in df.itertuples(index=False):
            nome = rnd.choices(
                [r.Municipio, r.Municipio.upper(), sem_acento(r.Municipio), r.Municipio + "  ", sem_acento(r.Municipio).upper()],
                [0.6, 0.15, 0.1, 0.1, 0.05])[0]
            cod = rnd.choices([r.Cod_Municipio, " " + r.Cod_Municipio, r.Cod_Municipio.lower(), r.Cod_Municipio + " "],
                              [0.85, 0.05, 0.05, 0.05])[0]
            variantes, pesos = VARIANTES_CLASSE[r.Classe]
            classe = rnd.choices(variantes, pesos)[0]
            linha = ";".join([
                f"{periodo.month:02d}/{periodo.year}", cod, nome, classe, fmt_inteiro(r.Qtd_Clientes),
                fmt_decimal(r.Consumo_kWh), "R$ " + fmt_decimal(r.Valor_Faturado),
            ])
            registros.append(linha)
            if rnd.random() < 0.015:  # o sistema exportou a mesma linha duas vezes
                registros.append(linha)
        rnd.shuffle(registros)
        emissao = (periodo + 1).to_timestamp() + pd.Timedelta(days=rnd.randint(2, 6), hours=rnd.randint(7, 18), minutes=rnd.randint(0, 59))
        rodape = ";".join(["TOTAL GERAL", "", "", "", fmt_inteiro(df.Qtd_Clientes.sum()),
                           fmt_decimal(df.Consumo_kWh.sum()), "R$ " + fmt_decimal(df.Valor_Faturado.sum())])
        conteudo = [
            "Relatorio de Faturamento Mensal - Sistema Comercial (DADOS SIMULADOS)",
            f"Emitido em: {emissao:%d/%m/%Y %H:%M}",
            "Competencia;Cod_Municipio;Municipio;Classe;Qtd_Clientes;Consumo_kWh;Valor_Faturado",
            *registros,
            rodape,
        ]
        (pasta / f"faturamento_{periodo.year}-{periodo.month:02d}.csv").write_text("\n".join(conteudo) + "\n", encoding="utf-8")


def exportar_municipios() -> None:
    df = pd.DataFrame(
        [(f"MUN{i:03d}", nome, regional, "RJ") for i, (nome, regional, _, _) in enumerate(MUNICIPIOS, start=1)],
        columns=["Cod_Municipio", "Municipio", "Regional", "UF"],
    )
    df.to_excel(PASTA / "municipios.xlsx", sheet_name="Municipios", index=False)


def exportar_metas(base: pd.DataFrame, rng: np.random.Generator) -> None:
    nomes_mes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    real = base.groupby(["Regional", "Periodo"]).Consumo_kWh.sum() / 1e6  # GWh
    linhas = []
    for regional in base.Regional.unique():
        linha = {"Regional": regional}
        for periodo in MESES_META:
            if (regional, periodo) in real.index:
                valor = real[(regional, periodo)] * rng.uniform(0.96, 1.04)
            else:  # mês ainda sem realizado: meta = mesmo mês do ano anterior + 2%
                valor = real[(regional, periodo - 12)] * 1.02
            linha[f"{nomes_mes[periodo.month - 1]}/{str(periodo.year)[2:]}"] = round(valor, 1)
        linha["Total"] = round(sum(v for k, v in linha.items() if k != "Regional"), 1)
        linhas.append(linha)
    pd.DataFrame(linhas).to_excel(PASTA / "metas_regionais.xlsx", sheet_name="Metas", index=False)


def exportar_de_para() -> None:
    linhas = sorted({(v.strip().upper(), classe) for classe, (vs, _) in VARIANTES_CLASSE.items() for v in vs})
    texto = "Classe_Original;Classe_Padrao\n" + "\n".join(f"{o};{p}" for o, p in linhas) + "\n"
    (PASTA / "de_para_classes.csv").write_text(texto, encoding="utf-8")


def main() -> None:
    rng = np.random.default_rng(SEMENTE)
    rnd = random.Random(SEMENTE)
    PASTA.mkdir(parents=True, exist_ok=True)
    base = gerar_base_limpa(rng)
    exportar_faturamento(base, rnd)
    exportar_municipios()
    exportar_metas(base, rng)
    exportar_de_para()
    print(f"OK: {len(MESES)} arquivos de faturamento, {len(base)} linhas limpas -> {PASTA}")
    print(f"Consumo total simulado: {base.Consumo_kWh.sum() / 1e9:.1f} TWh | Faturamento: R$ {base.Valor_Faturado.sum() / 1e9:.1f} bi")


if __name__ == "__main__":
    main()
