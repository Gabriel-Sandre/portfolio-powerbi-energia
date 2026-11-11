"""
Regras de qualidade de dados para cada tipo de arquivo.

Cada validador recebe o CSV cru (tudo texto) e devolve:
    validos    -> DataFrame já tipado, com as colunas da tabela de staging
    rejeicoes  -> lista de (linha_no_arquivo, motivo, conteúdo_original)

Nada é descartado em silêncio: toda linha rejeitada vai para dw.Rejeicao com o motivo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

Rejeicao = tuple[int, str, str]


@dataclass
class Contexto:
    """O que já existe no banco e é usado para validar integridade referencial."""
    alimentadores: set[str] = field(default_factory=set)
    clientes: set[int] = field(default_factory=set)


class Validador:
    def __init__(self, bruto: pd.DataFrame):
        self.df = bruto.copy()
        self.original = bruto
        self.rejeicoes: list[Rejeicao] = []

    def rejeitar(self, mascara: pd.Series, motivo: str) -> None:
        mascara = mascara.fillna(True)
        for idx in self.df.index[mascara]:
            conteudo = ";".join(str(v) for v in self.original.loc[idx].tolist())[:500]
            self.rejeicoes.append((int(idx) + 2, motivo, conteudo))  # +2 = cabeçalho + base 1
        self.df = self.df[~mascara].copy()

    def obrigatorio(self, *colunas: str) -> None:
        for coluna in colunas:
            self.rejeitar(self.df[coluna].str.strip() == "", f"{coluna} vazio")

    def inteiro(self, coluna: str, minimo: int | None = None) -> None:
        convertido = pd.to_numeric(self.df[coluna].str.strip(), errors="coerce")
        self.rejeitar(convertido.isna() | (convertido % 1 != 0), f"{coluna} não é número inteiro")
        if minimo is not None:
            self.rejeitar(convertido.loc[self.df.index] < minimo, f"{coluna} menor que {minimo}")
        self.df[coluna] = convertido.loc[self.df.index].astype("int64")

    def decimal_br(self, coluna: str) -> None:
        convertido = pd.to_numeric(self.df[coluna].str.strip().str.replace(",", ".", regex=False), errors="coerce")
        self.rejeitar(convertido.isna(), f"{coluna} não é número")
        self.df[coluna] = convertido.loc[self.df.index].astype(float)

    def data_br(self, coluna: str) -> None:
        convertido = pd.to_datetime(self.df[coluna].str.strip(), format="%d/%m/%Y", errors="coerce")
        self.rejeitar(convertido.isna(), f"{coluna} não é data dd/mm/aaaa")
        self.df[coluna] = convertido.loc[self.df.index].dt.date

    def competencia(self, esperada: date) -> None:
        texto = f"{esperada.month:02d}/{esperada.year}"
        self.rejeitar(self.df["Competencia"].str.strip() != texto, f"Competência diferente de {texto}")
        self.df["Competencia"] = esperada

    def dominio(self, coluna: str, permitidos: set[str]) -> None:
        self.rejeitar(~self.df[coluna].str.strip().isin(permitidos), f"{coluna} fora do domínio {sorted(permitidos)}")
        self.df[coluna] = self.df[coluna].str.strip()

    def existe(self, coluna: str, conhecidos: set, descricao: str) -> None:
        self.rejeitar(~self.df[coluna].isin(conhecidos), f"{descricao} não cadastrado")

    def unico(self, *chave: str) -> None:
        self.rejeitar(self.df.duplicated(list(chave), keep="first"), f"Duplicado ({', '.join(chave)})")

    def resultado(self, colunas: list[str]) -> tuple[pd.DataFrame, list[Rejeicao]]:
        return self.df[colunas].reset_index(drop=True), self.rejeicoes


def validar_alimentadores(bruto, ctx: Contexto, competencia=None):
    v = Validador(bruto)
    v.obrigatorio("Alimentador_ID", "Subestacao", "Municipio", "Regional")
    v.dominio("Area_Risco", {"S", "N"})
    v.decimal_br("Perda_Tecnica_Pct")
    v.rejeitar((v.df.Perda_Tecnica_Pct <= 0) | (v.df.Perda_Tecnica_Pct >= 0.5), "Perda técnica fora de 0-50%")
    v.unico("Alimentador_ID")
    v.df["Area_Risco"] = v.df.Area_Risco == "S"
    return v.resultado(["Alimentador_ID", "Subestacao", "Municipio", "Regional", "Area_Risco", "Perda_Tecnica_Pct"])


def validar_clientes(bruto, ctx: Contexto, competencia=None):
    v = Validador(bruto)
    v.inteiro("Cliente_ID", minimo=1)
    v.existe("Alimentador_ID", ctx.alimentadores, "Alimentador")
    v.dominio("Classe", {"Residencial", "Comercial", "Industrial"})
    v.obrigatorio("Tipo_Medidor")
    v.data_br("Data_Ligacao")
    v.unico("Cliente_ID")
    return v.resultado(["Cliente_ID", "Alimentador_ID", "Classe", "Tipo_Medidor", "Data_Ligacao"])


def validar_injecao(bruto, ctx: Contexto, competencia: date):
    v = Validador(bruto)
    v.existe("Alimentador_ID", ctx.alimentadores, "Alimentador")
    v.competencia(competencia)
    v.inteiro("Energia_Injetada_kWh", minimo=1)
    v.unico("Alimentador_ID")
    return v.resultado(["Alimentador_ID", "Competencia", "Energia_Injetada_kWh"])


def validar_leituras(bruto, ctx: Contexto, competencia: date):
    v = Validador(bruto)
    v.inteiro("Cliente_ID", minimo=1)
    v.existe("Cliente_ID", ctx.clientes, "Cliente")
    v.competencia(competencia)
    v.obrigatorio("Consumo_kWh")
    v.inteiro("Consumo_kWh", minimo=0)
    v.dominio("Tipo_Leitura", {"Real", "Estimada"})
    v.unico("Cliente_ID")
    v.df["Leitura_Estimada"] = v.df.Tipo_Leitura == "Estimada"
    return v.resultado(["Cliente_ID", "Competencia", "Consumo_kWh", "Leitura_Estimada"])


def validar_inspecoes(bruto, ctx: Contexto, competencia: date):
    v = Validador(bruto)
    v.inteiro("Inspecao_ID", minimo=1)
    v.inteiro("Cliente_ID", minimo=1)
    v.existe("Cliente_ID", ctx.clientes, "Cliente")
    v.data_br("Data_Inspecao")
    v.dominio("Origem", {"Aleatória", "Denúncia", "Regra de queda", "Score"})
    v.dominio("Resultado", {"Irregularidade", "Normal"})
    v.inteiro("Energia_Recuperada_kWh", minimo=0)
    v.unico("Inspecao_ID")
    return v.resultado(["Inspecao_ID", "Cliente_ID", "Data_Inspecao", "Origem", "Resultado", "Energia_Recuperada_kWh"])
