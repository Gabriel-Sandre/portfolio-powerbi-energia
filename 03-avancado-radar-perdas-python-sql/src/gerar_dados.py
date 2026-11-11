"""
Projeto 3 (avançado) - Radar de Perdas Não Técnicas
Simula as exportações de um sistema comercial/medição de uma distribuidora.

Uso:
    python src/gerar_dados.py

Saída (pasta dados_fonte/, CSV ";" pt-BR):
    cadastro_alimentadores.csv
    cadastro_clientes.csv
    injecao_AAAA-MM.csv      energia injetada em cada alimentador (medição da subestação)
    leituras_AAAA-MM.csv     consumo faturado de cada cliente (com problemas de qualidade de propósito)
    inspecoes_AAAA-MM.csv    inspeções de campo e resultado

O que está "escondido" nos dados (o pipeline e o score precisam descobrir):
    - clientes que passam a desviar energia: o consumo FATURADO cai, o REAL não;
    - ligações clandestinas (quem nem é cliente) em áreas de risco: a energia injetada sobe;
    - falsos positivos: casa vazia por alguns meses, instalação de energia solar;
    - leituras estimadas (o leiturista não acessou o medidor), mais comuns onde há desvio.

Todos os dados são SIMULADOS.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

SEMENTE = 99
RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "dados_fonte"
MESES = pd.period_range("2025-01", "2026-10", freq="M")
N_CLIENTES = 12_000
SAZONALIDADE = np.array([1.12, 1.15, 1.10, 1.02, 0.95, 0.90, 0.88, 0.90, 0.94, 0.98, 1.03, 1.08])

# (subestação, município, regional, subestação em área de risco?, nº de alimentadores)
SUBESTACOES = [
    ("Campo Grande", "Rio de Janeiro", "Capital - Zona Oeste", True, 5),
    ("Santa Cruz", "Rio de Janeiro", "Capital - Zona Oeste", True, 4),
    ("Bangu", "Rio de Janeiro", "Capital - Zona Oeste", True, 4),
    ("Jacarepaguá", "Rio de Janeiro", "Capital - Zona Oeste", False, 4),
    ("Barra", "Rio de Janeiro", "Capital - Zona Oeste", False, 3),
    ("Madureira", "Rio de Janeiro", "Capital - Zona Norte", True, 4),
    ("Penha", "Rio de Janeiro", "Capital - Zona Norte", True, 3),
    ("Tijuca", "Rio de Janeiro", "Capital - Zona Norte", False, 3),
    ("Botafogo", "Rio de Janeiro", "Capital - Zona Sul", False, 3),
    ("Duque de Caxias", "Duque de Caxias", "Baixada Fluminense", True, 4),
    ("Nova Iguaçu", "Nova Iguaçu", "Baixada Fluminense", True, 4),
    ("Belford Roxo", "Belford Roxo", "Baixada Fluminense", True, 3),
    ("São João de Meriti", "São João de Meriti", "Baixada Fluminense", True, 3),
    ("Volta Redonda", "Volta Redonda", "Sul Fluminense", False, 3),
    ("Resende", "Resende", "Sul Fluminense", False, 2),
    ("Vassouras", "Vassouras", "Centro-Sul Fluminense", False, 2),
]


def gerar_alimentadores(rng) -> pd.DataFrame:
    linhas = []
    for se, municipio, regional, se_risco, n in SUBESTACOES:
        palavras = unicodedata.normalize("NFD", se.upper()).encode("ascii", "ignore").decode().replace(" DE ", " ").split()
        prefixo = palavras[0][:3] if len(palavras) == 1 else palavras[0][:2] + palavras[-1][0]
        for i in range(1, n + 1):
            risco = bool(rng.random() < (0.75 if se_risco else 0.08))
            linhas.append({
                "Alimentador_ID": f"{prefixo}{i:02d}",
                "Subestacao": f"SE {se}",
                "Municipio": municipio,
                "Regional": regional,
                "Area_Risco": risco,
                "Perda_Tecnica_Pct": round(rng.uniform(0.06, 0.10), 4),
                # ligações clandestinas (energia consumida por quem nem é cliente)
                "clandestino": rng.uniform(0.08, 0.25) if risco else rng.uniform(0.0, 0.02),
            })
    return pd.DataFrame(linhas)


def gerar_clientes(rng, alim: pd.DataFrame) -> pd.DataFrame:
    n = N_CLIENTES
    idx_alim = rng.integers(0, len(alim), n)
    risco = alim.Area_Risco.to_numpy()[idx_alim]
    classe = rng.choice(["Residencial", "Comercial", "Industrial"], n, p=[0.87, 0.11, 0.02])
    mediana = np.select([classe == "Residencial", classe == "Comercial"], [150, 800], 5000)
    sigma = np.select([classe == "Residencial", classe == "Comercial"], [0.5, 0.7], 0.8)
    medidor = np.where(
        risco,
        rng.choice(["Eletromecânico", "Eletrônico", "Inteligente"], n, p=[0.55, 0.40, 0.05]),
        rng.choice(["Eletromecânico", "Eletrônico", "Inteligente"], n, p=[0.30, 0.50, 0.20]),
    )
    ligacao = pd.to_datetime("1995-01-01") + pd.to_timedelta(rng.integers(0, 365 * 30, n), unit="D")
    return pd.DataFrame({
        "Cliente_ID": np.arange(100001, 100001 + n),
        "Alimentador_ID": alim.Alimentador_ID.to_numpy()[idx_alim],
        "Classe": classe,
        "Tipo_Medidor": medidor,
        "Data_Ligacao": ligacao,
        "risco": risco,
        "base_kwh": rng.lognormal(np.log(mediana), sigma),
    })


def simular(rng, alim: pd.DataFrame, cli: pd.DataFrame):
    n, T = len(cli), len(MESES)
    risco = cli.risco.to_numpy()
    classe = cli.Classe.to_numpy()

    # quem vai desviar energia e a partir de quando (alguns já desviavam antes de 2025)
    p_fraude = np.where(risco, 0.16, 0.035) * np.select([classe == "Comercial", classe == "Industrial"], [1.2, 0.6], 1.0)
    p_fraude *= np.where(cli.Tipo_Medidor.to_numpy() == "Eletromecânico", 1.4, np.where(cli.Tipo_Medidor.to_numpy() == "Inteligente", 0.3, 1.0))
    fraudador = rng.random(n) < p_fraude
    inicio_fraude = np.where(fraudador, rng.integers(-6, T - 1, n), 10_000)
    mult_fraude = rng.uniform(0.15, 0.6, n)

    # falsos positivos legítimos
    vazio = rng.random(n) < 0.06
    inicio_vazio = rng.integers(0, T, n)
    dur_vazio = rng.integers(2, 5, n)
    solar = (rng.random(n) < np.where(risco, 0.01, 0.04)) & ~fraudador
    inicio_solar = rng.integers(0, T, n)

    sazonal_peso = np.select([classe == "Industrial"], [0.3], 1.0)
    detectado_em = np.full(n, 10_000)
    ultima_inspecao = np.full(n, -100)
    faturado = np.zeros((n, T))
    real = np.zeros((n, T))
    estimada = np.zeros((n, T), dtype=bool)
    inspecoes = []
    insp_id = 1

    for t, periodo in enumerate(MESES):
        # ---- inspeções do mês t (decididas com o que se sabia até t-1) ----
        if t >= 2:
            fraude_ativa = (inicio_fraude <= t - 1) & (detectado_em > t - 1)
            elegivel = (t - ultima_inspecao) > 6
            escolhidos = []
            # aleatória
            escolhidos += [(c, "Aleatória") for c in rng.choice(np.flatnonzero(elegivel), 80, replace=False)]
            # denúncia: metade cai em quem realmente desvia
            pool_denuncia = np.flatnonzero(elegivel & fraude_ativa)
            k = min(len(pool_denuncia), rng.binomial(40, 0.45))
            escolhidos += [(c, "Denúncia") for c in rng.choice(pool_denuncia, k, replace=False)]
            escolhidos += [(c, "Denúncia") for c in rng.choice(np.flatnonzero(elegivel), 40 - k, replace=False)]
            # rotina: regra antiga "caiu mais de 50% em relação a 3 meses atrás"
            if t >= 4:
                queda = faturado[:, t - 1] < 0.5 * faturado[:, t - 4]
                pool = np.flatnonzero(elegivel & queda)
                escolhidos += [(c, "Regra de queda") for c in rng.choice(pool, min(40, len(pool)), replace=False)]
            vistos = set()
            for c, origem in escolhidos:
                if c in vistos:
                    continue
                vistos.add(c)
                irregular = bool(fraude_ativa[c] and rng.random() < 0.9) or rng.random() < 0.02
                recuperada = 0
                if irregular and fraude_ativa[c]:
                    detectado_em[c] = t
                    meses = range(max(0, inicio_fraude[c]), t)
                    recuperada = int(sum(max(0.0, real[c, m] - faturado[c, m]) for m in meses))
                    if inicio_fraude[c] < 0:  # desvio anterior a 2025: estima pelos meses perdidos
                        recuperada += int(-inicio_fraude[c] * cli.base_kwh.iat[c] * (1 - mult_fraude[c]))
                    recuperada = min(recuperada, int(cli.base_kwh.iat[c] * 36))  # limite legal simplificado
                ultima_inspecao[c] = t
                dia = int(rng.integers(1, periodo.days_in_month + 1))
                inspecoes.append({
                    "Inspecao_ID": insp_id, "Cliente_ID": int(cli.Cliente_ID.iat[c]),
                    "Data_Inspecao": periodo.start_time.replace(day=dia), "Origem": origem,
                    "Resultado": "Irregularidade" if irregular else "Normal",
                    "Energia_Recuperada_kWh": recuperada, "periodo": periodo,
                })
                insp_id += 1

        # ---- consumo do mês t ----
        saz = 1 + (SAZONALIDADE[periodo.month - 1] - 1) * sazonal_peso
        consumo_real = cli.base_kwh.to_numpy() * saz * rng.lognormal(0, 0.08, n) * (1.015 ** (t / 12))
        em_vazio = vazio & (t >= inicio_vazio) & (t < inicio_vazio + dur_vazio)
        consumo_real = np.where(em_vazio, consumo_real * rng.uniform(0.05, 0.3, n), consumo_real)
        consumo_medido = np.where(solar & (t >= inicio_solar), consumo_real * 0.35, consumo_real)
        desviando = (inicio_fraude <= t) & (detectado_em > t)
        fat = np.where(desviando, consumo_medido * mult_fraude, consumo_medido)

        p_estimada = np.where(risco, 0.10, 0.025) + np.where(desviando, 0.12, 0.0)
        est = (rng.random(n) < p_estimada) & (t > 0)
        fat = np.where(est, faturado[:, t - 1] if t > 0 else fat, fat)  # estimada = repete o mês anterior

        real[:, t] = consumo_real
        faturado[:, t] = np.round(fat)
        estimada[:, t] = est

    return faturado, real, estimada, pd.DataFrame(inspecoes), fraudador


def fmt_comp(p: pd.Period) -> str:
    return f"{p.month:02d}/{p.year}"


def main() -> None:
    rng = np.random.default_rng(SEMENTE)
    PASTA.mkdir(parents=True, exist_ok=True)
    for antigo in PASTA.glob("*.csv"):
        antigo.unlink()

    alim = gerar_alimentadores(rng)
    cli = gerar_clientes(rng, alim)
    faturado, real, estimada, insp, fraudador = simular(rng, alim, cli)

    alim.assign(
        Area_Risco=np.where(alim.Area_Risco, "S", "N"),
        Perda_Tecnica_Pct=alim.Perda_Tecnica_Pct.map(lambda x: f"{x:.4f}".replace(".", ",")),
    )[["Alimentador_ID", "Subestacao", "Municipio", "Regional", "Area_Risco", "Perda_Tecnica_Pct"]].to_csv(
        PASTA / "cadastro_alimentadores.csv", sep=";", index=False, encoding="utf-8")
    cli.assign(Data_Ligacao=cli.Data_Ligacao.dt.strftime("%d/%m/%Y"))[
        ["Cliente_ID", "Alimentador_ID", "Classe", "Tipo_Medidor", "Data_Ligacao"]].to_csv(
        PASTA / "cadastro_clientes.csv", sep=";", index=False, encoding="utf-8")

    alim_de_cliente = cli.Alimentador_ID.to_numpy()
    for t, periodo in enumerate(MESES):
        sufixo = f"{periodo.year}-{periodo.month:02d}"
        comp = fmt_comp(periodo)

        # injeção = consumo real dos clientes + clandestinos, "subindo" a perda técnica
        real_alim = pd.Series(real[:, t]).groupby(alim_de_cliente).sum()
        inj = alim.set_index("Alimentador_ID")
        energia = real_alim.reindex(inj.index) * (1 + inj.clandestino) / (1 - inj.Perda_Tecnica_Pct)
        energia *= rng.normal(1, 0.01, len(energia))
        pd.DataFrame({"Alimentador_ID": inj.index, "Competencia": comp,
                      "Energia_Injetada_kWh": np.round(energia.to_numpy()).astype(int)}).to_csv(
            PASTA / f"injecao_{sufixo}.csv", sep=";", index=False, encoding="utf-8")

        # leituras, com problemas de qualidade inseridos de propósito
        le = pd.DataFrame({
            "Cliente_ID": cli.Cliente_ID.astype(str), "Competencia": comp,
            "Consumo_kWh": faturado[:, t].astype(int).astype(str),
            "Tipo_Leitura": np.where(estimada[:, t], "Estimada", "Real"),
        })
        n = len(le)
        neg = rng.random(n) < 0.0008
        le.loc[neg, "Consumo_kWh"] = "-" + le.loc[neg, "Consumo_kWh"]
        vazio = rng.random(n) < 0.0005
        le.loc[vazio, "Consumo_kWh"] = ""
        desconhecido = rng.random(n) < 0.0005
        le.loc[desconhecido, "Cliente_ID"] = (rng.integers(900000, 999999, desconhecido.sum())).astype(str)
        duplicadas = le.sample(frac=0.001, random_state=int(rng.integers(1e9)))
        le = pd.concat([le, duplicadas]).sample(frac=1, random_state=int(rng.integers(1e9)))
        le.to_csv(PASTA / f"leituras_{sufixo}.csv", sep=";", index=False, encoding="utf-8")

        ins = insp[insp.periodo == periodo].drop(columns="periodo")
        ins.assign(Data_Inspecao=ins.Data_Inspecao.dt.strftime("%d/%m/%Y")).to_csv(
            PASTA / f"inspecoes_{sufixo}.csv", sep=";", index=False, encoding="utf-8")

    # gabarito (NÃO é carregado no banco - serve só para avaliar o score honestamente)
    pd.DataFrame({"Cliente_ID": cli.Cliente_ID, "Fraudador": fraudador}).to_csv(
        RAIZ / "dados_fonte" / "_gabarito_nao_carregar.csv.txt", sep=";", index=False)

    print(f"OK: {len(alim)} alimentadores, {len(cli)} clientes, {len(MESES)} meses, {len(insp)} inspeções -> {PASTA}")
    print(f"Fraudadores simulados: {fraudador.sum()} ({fraudador.mean():.1%}) | taxa de acerto das inspeções: "
          f"{(insp.Resultado == 'Irregularidade').mean():.1%}")


if __name__ == "__main__":
    main()
