"""Acesso ao SQL Server: conexão, execução de scripts .sql e carga em massa."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import pyodbc

SERVIDOR = os.getenv("RADAR_SERVIDOR", "localhost")
BANCO = os.getenv("RADAR_BANCO", "RadarPerdas")

_DRIVERS_PREFERIDOS = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]


def _driver() -> str:
    instalados = pyodbc.drivers()
    for driver in _DRIVERS_PREFERIDOS:
        if driver in instalados:
            return driver
    raise RuntimeError(f"Nenhum driver ODBC do SQL Server encontrado. Instalados: {instalados}")


def conectar(banco: str | None = None, autocommit: bool = False) -> pyodbc.Connection:
    """Conecta com autenticação do Windows (sem senha no código)."""
    texto = (
        f"DRIVER={{{_driver()}}};SERVER={SERVIDOR};DATABASE={banco or BANCO};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(texto, autocommit=autocommit)


def garantir_banco() -> None:
    conexao = conectar("master", autocommit=True)
    try:
        conexao.execute(f"IF DB_ID(N'{BANCO}') IS NULL CREATE DATABASE [{BANCO}]")
    finally:
        conexao.close()


def executar_script(conexao: pyodbc.Connection, caminho: Path) -> None:
    """Executa um .sql com vários lotes separados por GO (o pyodbc não entende GO)."""
    texto = caminho.read_text(encoding="utf-8")
    lotes = re.split(r"^\s*GO\s*$", texto, flags=re.IGNORECASE | re.MULTILINE)
    cursor = conexao.cursor()
    for lote in lotes:
        if lote.strip():
            cursor.execute(lote)
    conexao.commit()


def inserir(conexao: pyodbc.Connection, tabela: str, df: pd.DataFrame) -> int:
    """INSERT em massa com fast_executemany (ordens de grandeza mais rápido que linha a linha)."""
    if df.empty:
        return 0
    colunas = list(df.columns)
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})"
    # pyodbc não aceita tipos do numpy: converte tudo para tipos nativos do Python (e NaN -> None)
    linhas = df.astype(object).where(pd.notna(df), None).values.tolist()
    cursor = conexao.cursor()
    cursor.fast_executemany = True
    cursor.executemany(sql, linhas)
    return len(linhas)


def consultar(conexao: pyodbc.Connection, sql: str, parametros: list | tuple = ()) -> pd.DataFrame:
    cursor = conexao.cursor()
    cursor.execute(sql, parametros)
    colunas = [c[0] for c in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=colunas)
