"""
Projeto 2 (intermediário) - Qualidade do Fornecimento: DEC e FEC
Gera um modelo estrela já limpo (o foco deste projeto é DAX, não tratamento de dados).

Uso:
    python gerar_dados.py

Saída (pasta dados/, CSV com ";" e vírgula decimal - padrão pt-BR):
    dConjuntos.csv     conjuntos elétricos, clientes de referência e limites anuais de DEC/FEC
    dCausas.csv        causas de interrupção
    fBaseClientes.csv  clientes por conjunto por mês (denominador do DEC/FEC)
    fInterrupcoes.csv  cada interrupção: início, fim, duração, clientes afetados, causa

Regras simplificadas, inspiradas no PRODIST Módulo 8 (ANEEL):
    DEC = soma(clientes afetados x horas interrompidas) / clientes do conjunto
    FEC = soma(clientes afetados) / clientes do conjunto
    entram só interrupções >= 3 minutos e não expurgáveis (ex.: dia crítico)

Todos os dados são SIMULADOS. Os "conjuntos" usam nomes de bairros e municípios apenas para dar contexto.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEMENTE = 7
PASTA = Path(__file__).resolve().parent / "dados"
MESES = pd.period_range("2025-01", "2026-10", freq="M")

# (conjunto, município, regional, clientes de referência, perfil, exposição a área de risco 0-1)
CONJUNTOS = [
    ("Centro", "Rio de Janeiro", "Capital", 95000, "urbano", 0.10),
    ("Copacabana", "Rio de Janeiro", "Capital", 120000, "urbano", 0.05),
    ("Botafogo", "Rio de Janeiro", "Capital", 105000, "urbano", 0.05),
    ("Tijuca", "Rio de Janeiro", "Capital", 110000, "urbano", 0.15),
    ("Méier", "Rio de Janeiro", "Capital", 98000, "urbano", 0.20),
    ("Barra da Tijuca", "Rio de Janeiro", "Capital", 130000, "urbano", 0.05),
    ("Recreio", "Rio de Janeiro", "Capital", 70000, "urbano", 0.05),
    ("Ilha do Governador", "Rio de Janeiro", "Capital", 75000, "urbano", 0.20),
    ("Jacarepaguá", "Rio de Janeiro", "Capital", 150000, "periferia", 0.35),
    ("Madureira", "Rio de Janeiro", "Capital", 125000, "periferia", 0.40),
    ("Penha", "Rio de Janeiro", "Capital", 90000, "periferia", 0.45),
    ("Irajá", "Rio de Janeiro", "Capital", 85000, "periferia", 0.35),
    ("Pavuna", "Rio de Janeiro", "Capital", 80000, "periferia", 0.50),
    ("Bangu", "Rio de Janeiro", "Capital", 140000, "periferia", 0.45),
    ("Realengo", "Rio de Janeiro", "Capital", 95000, "periferia", 0.40),
    ("Campo Grande", "Rio de Janeiro", "Capital", 175000, "periferia", 0.40),
    ("Santa Cruz", "Rio de Janeiro", "Capital", 110000, "periferia", 0.55),
    ("Guaratiba", "Rio de Janeiro", "Capital", 45000, "periferia", 0.30),
    ("Duque de Caxias", "Duque de Caxias", "Baixada Fluminense", 160000, "periferia", 0.50),
    ("Xerém", "Duque de Caxias", "Baixada Fluminense", 35000, "interior", 0.20),
    ("Nova Iguaçu", "Nova Iguaçu", "Baixada Fluminense", 170000, "periferia", 0.45),
    ("Belford Roxo", "Belford Roxo", "Baixada Fluminense", 120000, "periferia", 0.55),
    ("São João de Meriti", "São João de Meriti", "Baixada Fluminense", 115000, "periferia", 0.50),
    ("Nilópolis", "Nilópolis", "Baixada Fluminense", 55000, "periferia", 0.35),
    ("Mesquita", "Mesquita", "Baixada Fluminense", 58000, "periferia", 0.40),
    ("Queimados", "Queimados", "Baixada Fluminense", 50000, "periferia", 0.45),
    ("Japeri", "Japeri", "Baixada Fluminense", 35000, "periferia", 0.50),
    ("Seropédica", "Seropédica", "Baixada Fluminense", 30000, "interior", 0.25),
    ("Itaguaí", "Itaguaí", "Baixada Fluminense", 45000, "interior", 0.25),
    ("Volta Redonda", "Volta Redonda", "Sul Fluminense", 110000, "urbano", 0.10),
    ("Barra Mansa", "Barra Mansa", "Sul Fluminense", 70000, "urbano", 0.15),
    ("Resende", "Resende", "Sul Fluminense", 55000, "urbano", 0.10),
    ("Barra do Piraí", "Barra do Piraí", "Sul Fluminense", 38000, "interior", 0.10),
    ("Valença", "Valença", "Sul Fluminense", 30000, "interior", 0.05),
    ("Piraí", "Piraí", "Sul Fluminense", 15000, "interior", 0.05),
    ("Vassouras", "Vassouras", "Centro-Sul Fluminense", 17000, "interior", 0.05),
    ("Miguel Pereira", "Miguel Pereira", "Centro-Sul Fluminense", 14000, "interior", 0.05),
    ("Paty do Alferes", "Paty do Alferes", "Centro-Sul Fluminense", 12000, "interior", 0.05),
    ("Mendes", "Mendes", "Centro-Sul Fluminense", 9000, "interior", 0.05),
]

LIMITES = {  # perfil: (faixa DEC anual em h, faixa FEC anual em vezes)
    "urbano": ((6.5, 8.5), (4.5, 6.0)),
    "periferia": ((8.0, 11.0), (5.5, 7.5)),
    "interior": ((11.0, 16.0), (7.5, 10.0)),
}

# causa_id: (causa, grupo, responsabilidade, peso base, peso verão, peso área de risco, fator de duração)
CAUSAS = {
    1: ("Descarga atmosférica", "Meio ambiente", "Externa", 0.08, 2.5, 1.0, 1.1),
    2: ("Vegetação na rede", "Meio ambiente", "Externa", 0.16, 1.6, 1.0, 1.0),
    3: ("Falha em equipamento", "Rede própria", "Interna", 0.20, 1.0, 1.0, 1.0),
    4: ("Sobrecarga", "Rede própria", "Interna", 0.06, 2.2, 1.0, 0.7),
    5: ("Furto de cabos e equipamentos", "Terceiros", "Externa", 0.07, 1.0, 3.0, 1.9),
    6: ("Abalroamento de poste", "Terceiros", "Externa", 0.06, 1.0, 1.0, 1.5),
    7: ("Restrição de acesso (área de risco)", "Terceiros", "Externa", 0.04, 1.0, 4.0, 2.4),
    8: ("Manutenção programada", "Programada", "Interna", 0.12, 0.7, 1.0, 1.6),
    9: ("Causa não identificada", "Não identificada", "Interna", 0.21, 1.0, 1.0, 0.6),
}
VERAO = {12, 1, 2, 3}
SAZONALIDADE_EVENTOS = {12: 1.5, 1: 1.7, 2: 1.6, 3: 1.4, 4: 1.0, 5: 0.8, 6: 0.7, 7: 0.7, 8: 0.8, 9: 0.9, 10: 1.0, 11: 1.2}
DIAS_CRITICOS = [datetime(2025, 1, 14), datetime(2025, 2, 27), datetime(2025, 12, 19), datetime(2026, 2, 9), datetime(2026, 3, 3)]


def sigla(nome: str) -> str:
    limpo = "".join(c for c in unicodedata.normalize("NFD", nome) if unicodedata.category(c) != "Mn")
    partes = limpo.upper().replace("DE ", "").replace("DA ", "").replace("DO ", "").split()
    return (partes[0][:3] if len(partes) == 1 else partes[0][:2] + partes[-1][0])


def lognormal(rng, media, sigma, n):
    return rng.lognormal(np.log(media) - sigma**2 / 2, sigma, n)


def fmt_br(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def main() -> None:
    rng = np.random.default_rng(SEMENTE)
    PASTA.mkdir(parents=True, exist_ok=True)

    conjuntos, base_clientes, eventos = [], [], []
    for idx, (nome, municipio, regional, clientes, perfil, risco) in enumerate(CONJUNTOS, start=1):
        cid = f"CJ{idx:03d}"
        (dec_lo, dec_hi), (fec_lo, fec_hi) = LIMITES[perfil]
        lim_dec, lim_fec = round(rng.uniform(dec_lo, dec_hi), 1), round(rng.uniform(fec_lo, fec_hi), 1)
        conjuntos.append((cid, nome, municipio, regional, perfil, clientes, lim_dec, lim_fec))

        # desempenho "real" do conjunto em relação ao limite (área de risco piora tudo)
        razao = max(0.45, rng.normal(0.88, 0.2) + 0.45 * risco)
        n_alimentadores = int(np.clip(clientes / 9000, 3, 20))
        siglas = [f"{sigla(nome)}-{i:02d}" for i in range(1, n_alimentadores + 1)]
        pesos_causa = np.array([c[3] for c in CAUSAS.values()])

        for ano in (2025, 2026):
            tendencia = 1.0 if ano == 2025 else 0.9  # 2026: plano de investimento começando a surtir efeito
            meses_ano = [p for p in MESES if p.year == ano]
            dec_alvo = lim_dec * razao * tendencia * len(meses_ano) / 12
            fec_alvo = lim_fec * razao * rng.uniform(0.9, 1.1) * tendencia * len(meses_ano) / 12
            eventos_ano = []
            n_ano = int(np.clip(clientes / 350, 40, 500))
            for p in meses_ano:
                cc_mes = round(clientes * (1.001 ** (MESES.get_loc(p))))
                base_clientes.append((p.start_time.date(), cid, cc_mes))
                n = rng.poisson(n_ano / 12 * SAZONALIDADE_EVENTOS[p.month])
                ajuste = pesos_causa * np.array([
                    (c[4] if p.month in VERAO else 1.0) * (1 + (c[5] - 1) * risco) for c in CAUSAS.values()
                ])
                causas = rng.choice(list(CAUSAS), size=n, p=ajuste / ajuste.sum())
                dias = rng.integers(1, p.days_in_month + 1, n)
                for causa, dia in zip(causas, dias):
                    eventos_ano.append({"Conjunto_ID": cid, "Causa_ID": int(causa), "ano": ano, "mes": p.month, "dia": int(dia),
                                        "Programada": "S" if causa == 8 else "N", "Expurgavel": "N",
                                        "Alimentador": rng.choice(siglas), "fator": CAUSAS[causa][6]})
            df = pd.DataFrame(eventos_ano)
            # clientes afetados e duração brutos; depois calibrados para bater o DEC/FEC alvo do ano
            ca = lognormal(rng, 1.0, 1.0, len(df))
            dur = lognormal(rng, 1.0, 0.85, len(df)) * df.fator.to_numpy()
            ca = np.maximum(1, np.round(ca * fec_alvo * clientes / ca.sum())).astype(int)
            ca = np.minimum(ca, int(clientes * 0.35))
            horas = dur * (dec_alvo * clientes) / (ca * dur).sum()
            df["Clientes_Afetados"] = ca
            df["Duracao_min"] = np.maximum(3, np.round(horas * 60)).astype(int)
            eventos.append(df)

            # interrupções curtas (< 3 min): existem, mas não entram no indicador
            n_curtas = int(len(df) * 0.08)
            curtas = df.sample(n_curtas, random_state=int(rng.integers(1e9))).copy()
            curtas["Duracao_min"] = rng.integers(1, 3, n_curtas)
            curtas["Clientes_Afetados"] = np.maximum(1, (curtas.Clientes_Afetados * rng.uniform(0.5, 2, n_curtas)).astype(int))
            curtas["Causa_ID"] = rng.choice([3, 4, 9], n_curtas)
            curtas["Programada"] = "N"
            eventos.append(curtas)

        # dias críticos (temporais): muitas ocorrências no mesmo dia, expurgáveis
        for dia_critico in DIAS_CRITICOS:
            if pd.Period(dia_critico, "M") not in MESES:
                continue
            n = int(rng.integers(2, 7) * (1 + risco))
            eventos.append(pd.DataFrame({
                "Conjunto_ID": cid, "Causa_ID": rng.choice([1, 2], n, p=[0.6, 0.4]), "ano": dia_critico.year,
                "mes": dia_critico.month, "dia": dia_critico.day, "Programada": "N", "Expurgavel": "S",
                "Alimentador": rng.choice(siglas, n), "fator": 1.0,
                "Clientes_Afetados": rng.integers(int(clientes * 0.02), int(clientes * 0.12), n),
                "Duracao_min": np.round(lognormal(rng, 300, 0.6, n)).astype(int),
            }))

    ev = pd.concat(eventos, ignore_index=True)
    # horário de início: programadas em horário comercial; descargas à tarde; demais ao longo do dia
    horas_inicio = np.where(ev.Programada == "S", rng.integers(8, 15, len(ev)),
                            np.where(ev.Causa_ID == 1, rng.integers(14, 21, len(ev)), rng.integers(0, 24, len(ev))))
    inicio = [datetime(a, m, d, int(h), int(mi)) for a, m, d, h, mi in
              zip(ev.ano, ev.mes, ev.dia, horas_inicio, rng.integers(0, 60, len(ev)))]
    ev["Data_Hora_Inicio"] = inicio
    ev["Data_Hora_Fim"] = [i + timedelta(minutes=int(d)) for i, d in zip(inicio, ev.Duracao_min)]
    ev = ev.sort_values("Data_Hora_Inicio").reset_index(drop=True)
    ev.insert(0, "Interrupcao_ID", np.arange(1, len(ev) + 1))
    ev["Data"] = ev.Data_Hora_Inicio.dt.strftime("%d/%m/%Y")
    ev["Data_Hora_Inicio"] = ev.Data_Hora_Inicio.dt.strftime("%d/%m/%Y %H:%M")
    ev["Data_Hora_Fim"] = ev.Data_Hora_Fim.dt.strftime("%d/%m/%Y %H:%M")
    colunas = ["Interrupcao_ID", "Conjunto_ID", "Alimentador", "Causa_ID", "Data", "Data_Hora_Inicio",
               "Data_Hora_Fim", "Duracao_min", "Clientes_Afetados", "Programada", "Expurgavel"]
    ev[colunas].to_csv(PASTA / "fInterrupcoes.csv", sep=";", index=False, encoding="utf-8")

    pd.DataFrame(
        [(c, n, m, r, p, cl, fmt_br(ld), fmt_br(lf)) for c, n, m, r, p, cl, ld, lf in conjuntos],
        columns=["Conjunto_ID", "Conjunto", "Municipio", "Regional", "Perfil", "Clientes_Ref", "Limite_DEC_Anual", "Limite_FEC_Anual"],
    ).to_csv(PASTA / "dConjuntos.csv", sep=";", index=False, encoding="utf-8")

    pd.DataFrame(
        [(k, v[0], v[1], v[2]) for k, v in CAUSAS.items()],
        columns=["Causa_ID", "Causa", "Grupo", "Responsabilidade"],
    ).to_csv(PASTA / "dCausas.csv", sep=";", index=False, encoding="utf-8")

    bc = pd.DataFrame(base_clientes, columns=["Data", "Conjunto_ID", "Clientes"])
    bc["Data"] = pd.to_datetime(bc.Data).dt.strftime("%d/%m/%Y")
    bc.to_csv(PASTA / "fBaseClientes.csv", sep=";", index=False, encoding="utf-8")

    # conferência rápida: DEC/FEC de 2025 da empresa toda, pela regra oficial simplificada
    valido = ev[(ev.Duracao_min >= 3) & (ev.Expurgavel == "N") & (ev.ano == 2025)]
    cc = bc[bc.Data.str.endswith("2025")].groupby("Data").Clientes.sum().mean()
    dec = (valido.Clientes_Afetados * valido.Duracao_min / 60).sum() / cc
    fec = valido.Clientes_Afetados.sum() / cc
    print(f"OK: {len(ev)} interrupções, {len(conjuntos)} conjuntos -> {PASTA}")
    print(f"Conferência 2025 (empresa): DEC ~ {dec:.2f} h | FEC ~ {fec:.2f} vezes")


if __name__ == "__main__":
    main()
