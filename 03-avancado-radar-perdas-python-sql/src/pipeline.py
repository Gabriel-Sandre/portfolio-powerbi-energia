"""
Pipeline do Radar de Perdas: entrada/*.csv -> validação -> SQL Server -> score -> Power BI

Uso:
    python src/pipeline.py                     # processa o que estiver em entrada/
    python src/pipeline.py --recalcular-tudo   # refaz o score de todos os meses

Configuração por variável de ambiente (opcional):
    RADAR_SERVIDOR  (padrão: localhost)
    RADAR_BANCO     (padrão: RadarPerdas)

Cada execução:
    1. cria o banco/tabelas/procedures/views se não existirem (scripts em sql/);
    2. processa os arquivos na ordem certa (cadastros -> injeção -> leituras -> inspeções, mês a mês);
    3. valida cada linha; o que é ruim vai para dw.Rejeicao com o motivo;
    4. carrega em staging e faz MERGE no dw (reprocessar não duplica);
    5. move o arquivo para processados/ (ou rejeitados/ se falhar inteiro);
    6. recalcula o score de risco dos meses afetados;
    7. registra tudo em dw.LogExecucao / dw.LogArquivo (o Power BI mostra a saúde do pipeline).
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import db
import score
import validacao as val

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "entrada"
PROCESSADOS = RAIZ / "processados"
REJEITADOS = RAIZ / "rejeitados"
LOGS = RAIZ / "logs"
SQL = RAIZ / "sql"

# tipo: (validador, tabela de staging, procedure de merge, ordem dentro do mês)
TIPOS = {
    "cadastro_alimentadores": (val.validar_alimentadores, "stg.Alimentadores", "dw.usp_carregar_alimentadores", 0),
    "cadastro_clientes": (val.validar_clientes, "stg.Clientes", "dw.usp_carregar_clientes", 1),
    "injecao": (val.validar_injecao, "stg.Injecao", "dw.usp_carregar_injecao", 0),
    "leituras": (val.validar_leituras, "stg.Leituras", "dw.usp_carregar_leituras", 1),
    "inspecoes": (val.validar_inspecoes, "stg.Inspecoes", "dw.usp_carregar_inspecoes", 2),
}
LOTE_SCORE_MESES = 3
PADRAO_MENSAL = re.compile(r"^(injecao|leituras|inspecoes)_(\d{4})-(\d{2})\.csv$", re.IGNORECASE)

log = logging.getLogger("radar")


def configurar_log() -> None:
    LOGS.mkdir(exist_ok=True)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    arquivo = logging.FileHandler(LOGS / f"pipeline_{datetime.now():%Y%m%d}.log", encoding="utf-8")
    tela = logging.StreamHandler(sys.stdout)
    for handler in (arquivo, tela):
        handler.setFormatter(formato)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def identificar(arquivo: Path) -> tuple[str, date | None] | None:
    nome = arquivo.name.lower()
    if nome in ("cadastro_alimentadores.csv", "cadastro_clientes.csv"):
        return nome.removesuffix(".csv"), None
    m = PADRAO_MENSAL.match(arquivo.name)
    if m:
        return m.group(1).lower(), date(int(m.group(2)), int(m.group(3)), 1)
    return None


def ordenar(arquivos: list[Path]) -> list[tuple[Path, str, date | None]]:
    identificados = []
    for arq in arquivos:
        info = identificar(arq)
        if info is None:
            log.warning("Arquivo ignorado (nome fora do padrão): %s", arq.name)
            continue
        tipo, comp = info
        chave = (date.min, TIPOS[tipo][3]) if comp is None else (comp, TIPOS[tipo][3])
        identificados.append((chave, arq, tipo, comp))
    return [(a, t, c) for _, a, t, c in sorted(identificados, key=lambda x: x[0])]


def carregar_contexto(conexao) -> val.Contexto:
    cur = conexao.cursor()
    alimentadores = {r[0] for r in cur.execute("SELECT Alimentador_ID FROM dw.dAlimentador").fetchall()}
    clientes = {r[0] for r in cur.execute("SELECT Cliente_ID FROM dw.dCliente").fetchall()}
    return val.Contexto(alimentadores, clientes)


def mover(arquivo: Path, destino: Path) -> None:
    destino.mkdir(exist_ok=True)
    alvo = destino / arquivo.name
    if alvo.exists():
        alvo.unlink()
    shutil.move(str(arquivo), str(alvo))


def processar_arquivo(conexao, execucao_id: int, arquivo: Path, tipo: str, comp: date | None,
                      ctx: val.Contexto) -> tuple[int, int, int]:
    validador, staging, procedure, _ = TIPOS[tipo]
    bruto = pd.read_csv(arquivo, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    validos, rejeicoes = validador(bruto, ctx, comp)

    cur = conexao.cursor()
    cur.execute(f"TRUNCATE TABLE {staging}")
    db.inserir(conexao, staging, validos)
    cur.execute(f"EXEC {procedure}")
    if rejeicoes:
        db.inserir(conexao, "dw.Rejeicao", pd.DataFrame(
            [(execucao_id, arquivo.name, linha, motivo, conteudo) for linha, motivo, conteudo in rejeicoes],
            columns=["Execucao_ID", "Arquivo", "Linha", "Motivo", "Conteudo"]))
    cur.execute(
        "INSERT INTO dw.LogArquivo (Execucao_ID, Arquivo, Tipo, Competencia, Linhas_Lidas, Linhas_Carregadas, "
        "Linhas_Rejeitadas, Status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        execucao_id, arquivo.name, tipo, comp, len(bruto), len(validos), len(rejeicoes),
        "OK" if not rejeicoes else "OK com rejeições")
    conexao.commit()
    return len(bruto), len(validos), len(rejeicoes)


def recalcular_scores(conexao, competencias_carregadas: set[date], tudo: bool) -> int:
    pendentes = db.consultar(conexao, """
        SELECT DISTINCT l.Competencia FROM dw.fLeitura AS l
        WHERE NOT EXISTS (SELECT 1 FROM dw.fScoreRisco AS s WHERE s.Competencia = l.Competencia)""")
    todas = db.consultar(conexao, "SELECT DISTINCT Competencia FROM dw.fLeitura").Competencia.tolist()
    alvo = set(pendentes.Competencia.tolist())
    if tudo:
        alvo = set(todas)
    elif competencias_carregadas:
        # uma inspeção nova muda o "histórico" dos meses seguintes: refaz a partir do mês mais antigo afetado
        inicio = min(competencias_carregadas)
        alvo |= {c for c in todas if c >= inicio}
    if not alvo:
        log.info("Score: nada a recalcular")
        return 0

    comps = sorted(alvo)
    t0 = time.perf_counter()
    total, faixas = 0, {}
    cur = conexao.cursor()
    # lotes pequenos = consultas leves (o servidor pode ter pouca memória livre) e commit parcial
    for i in range(0, len(comps), LOTE_SCORE_MESES):
        lote = comps[i:i + LOTE_SCORE_MESES]
        features = db.consultar(conexao, "SELECT * FROM dw.fn_features_cliente(?, ?)", [lote[0], lote[-1]])
        features = features[features.Competencia.isin(lote)]
        resultado = score.pontuar(features)
        cur.execute(f"DELETE FROM dw.fScoreRisco WHERE Competencia IN ({', '.join('?' * len(lote))})", lote)
        db.inserir(conexao, "dw.fScoreRisco", resultado)
        conexao.commit()
        total += len(resultado)
        for faixa, n in resultado.Faixa.value_counts().items():
            faixas[faixa] = faixas.get(faixa, 0) + int(n)
        log.info("Score %s a %s: %d linhas", lote[0], lote[-1], len(resultado))
    log.info("Score: %d linhas em %d competências (%.1fs) | faixas: %s",
             total, len(comps), time.perf_counter() - t0, faixas)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recalcular-tudo", action="store_true", help="refaz o score de todos os meses")
    args = parser.parse_args()

    configurar_log()
    ENTRADA.mkdir(exist_ok=True)
    log.info("Início | servidor=%s banco=%s", db.SERVIDOR, db.BANCO)

    db.garantir_banco()
    conexao = db.conectar()
    for script in sorted(SQL.glob("0[1-3]_*.sql")):
        db.executar_script(conexao, script)

    cur = conexao.cursor()
    execucao_id = cur.execute(
        "INSERT INTO dw.LogExecucao (Inicio, Status) OUTPUT INSERTED.Execucao_ID VALUES (SYSDATETIME(), N'Em execução')"
    ).fetchval()
    conexao.commit()

    totais = {"arquivos": 0, "lidas": 0, "carregadas": 0, "rejeitadas": 0}
    erros: list[str] = []
    competencias: set[date] = set()
    try:
        ctx = carregar_contexto(conexao)
        for arquivo, tipo, comp in ordenar(list(ENTRADA.glob("*.csv"))):
            try:
                lidas, carregadas, rejeitadas = processar_arquivo(conexao, execucao_id, arquivo, tipo, comp, ctx)
            except Exception as exc:  # um arquivo ruim não derruba o lote inteiro
                conexao.rollback()
                erros.append(f"{arquivo.name}: {exc}")
                log.error("FALHA em %s: %s", arquivo.name, exc)
                mover(arquivo, REJEITADOS)
                continue
            totais["arquivos"] += 1
            totais["lidas"] += lidas
            totais["carregadas"] += carregadas
            totais["rejeitadas"] += rejeitadas
            if comp is not None:
                competencias.add(comp)
            if tipo.startswith("cadastro"):
                ctx = carregar_contexto(conexao)
            log.info("%-32s lidas=%6d carregadas=%6d rejeitadas=%4d", arquivo.name, lidas, carregadas, rejeitadas)
            mover(arquivo, PROCESSADOS)

        n_scores = recalcular_scores(conexao, competencias, args.recalcular_tudo)
        status = "Sucesso" if not erros else "Concluído com erros"
        mensagem = "; ".join(erros)[:4000] or None
    except Exception as exc:
        conexao.rollback()
        n_scores, status, mensagem = 0, "Falha", str(exc)[:4000]
        log.exception("Execução interrompida")

    cur.execute(
        "UPDATE dw.LogExecucao SET Fim = SYSDATETIME(), Status = ?, Arquivos = ?, Linhas_Lidas = ?, "
        "Linhas_Carregadas = ?, Linhas_Rejeitadas = ?, Scores_Calculados = ?, Mensagem = ? WHERE Execucao_ID = ?",
        status, totais["arquivos"], totais["lidas"], totais["carregadas"], totais["rejeitadas"], n_scores, mensagem,
        execucao_id)
    conexao.commit()
    conexao.close()
    log.info("Fim | execução %d | %s | arquivos=%d linhas=%d rejeitadas=%d scores=%d", execucao_id, status,
             totais["arquivos"], totais["lidas"], totais["rejeitadas"], n_scores)
    return 0 if status == "Sucesso" else 1


if __name__ == "__main__":
    sys.exit(main())
