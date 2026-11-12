"""
Gera o projeto do Power BI (PBIP) do Projeto 3 - Radar de Perdas Não Técnicas.

Pré-requisito: o pipeline já rodou e o banco RadarPerdas existe no SQL Server local
(python src/gerar_dados.py, python src/simular_chegada.py --tudo, python src/pipeline.py).

Uso:
    python criar_pbip.py            (só se ainda não existir)
    python criar_pbip.py --forcar   (recria do zero, APAGANDO alterações salvas no Power BI)
    -> abra RadarPerdas.pbip no Power BI Desktop e clique em "Atualizar"
       (na 1ª vez ele pede a credencial do SQL Server: "Usar minhas credenciais atuais")

Fonte única: consultas em powerbi/consultas.pq, medidas em powerbi/medidas.dax,
tabelas calculadas em powerbi/tabelas_calculadas.dax.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent / "ferramentas"))
import pbip  # noqa: E402
from pbip import Coluna as C, Tabela, cabecalho, visual  # noqa: E402

NOME = "RadarPerdas"


def tabela_calculada(nome: str) -> str:
    """Pega o corpo de 'Nome =' no arquivo de tabelas calculadas (até a linha em branco)."""
    texto = (RAIZ / "powerbi" / "tabelas_calculadas.dax").read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(nome)} =\n(.*?)(?:\n\n|\Z)", texto, flags=re.S | re.M)
    return m.group(1)


def formato(nome: str) -> str | None:
    if nome.startswith(("Status", "Cor ", "Texto")):
        return None
    if nome == "Última Execução":
        return "dd/mm/yyyy hh:nn"
    if nome == "Última Competência Score":
        return "mm/yyyy"
    if "%" in nome or nome.startswith("Taxa de Acerto"):
        return "0.0%"
    if "(R$/kWh)" in nome:
        return "R$ 0.00"
    if "(R$)" in nome:
        return "R$ #,0"
    if "(x)" in nome or nome in ("Score Médio",) or "(min)" in nome:
        return "0.0"
    return "#,0"


def main() -> None:
    consultas = pbip.ler_consultas(RAIZ / "powerbi" / "consultas.pq")
    medidas = [(n, e, p, formato(n)) for n, e, p in pbip.ler_medidas(RAIZ / "powerbi" / "medidas.dax")]
    m = lambda n: consultas[n]  # noqa: E731

    tabelas = [
        Tabela("dAlimentador", [
            C("Alimentador_ID", "string"), C("Subestacao", "string"), C("Municipio", "string"), C("Regional", "string"),
            C("Area_Risco", "string"), C("Perda_Tecnica_Pct", "double", formato="0.0%"),
        ], "m", m("dAlimentador")),
        Tabela("dCliente", [
            C("Cliente_ID", "int64", formato="0"), C("Alimentador_ID", "string", oculta=True), C("Classe", "string"),
            C("Tipo_Medidor", "string"), C("Data_Ligacao", "dateTime", formato="dd/mm/yyyy"),
        ], "m", m("dCliente")),
        Tabela("fBalanco", [
            C("Alimentador_ID", "string", oculta=True), C("Competencia", "dateTime", oculta=True, formato="dd/mm/yyyy"),
            C("Energia_Injetada_kWh", "int64", formato="#,0"), C("Energia_Faturada_kWh", "int64", formato="#,0"),
            C("Perda_Tecnica_kWh", "int64", formato="#,0"), C("PNT_kWh", "int64", formato="#,0"),
            C("PNT_Pct_Injetada", "double", formato="0.0%"), C("Clientes_Faturados", "int64", formato="#,0"),
            C("Leituras_Estimadas", "int64", formato="#,0"),
        ], "m", m("fBalanco"), medidas=medidas),
        Tabela("fScore", [
            C("Cliente_ID", "int64", oculta=True), C("Competencia", "dateTime", oculta=True, formato="dd/mm/yyyy"),
            C("Score", "double", formato="0.0"), C("Faixa", "string"), C("Motivo_Principal", "string"),
            C("Pts_Queda", "double"), C("Pts_Pares", "double"), C("Pts_Consumo_Baixo", "double"),
            C("Pts_Estimada", "double"), C("Pts_PNT", "double"), C("Pts_Historico", "double"),
        ], "m", m("fScore")),
        Tabela("fInspecoes", [
            C("Inspecao_ID", "int64", formato="0"), C("Cliente_ID", "int64", oculta=True),
            C("Data_Inspecao", "dateTime", oculta=True, formato="dd/mm/yyyy"),
            C("Competencia_Inspecao", "dateTime", formato="mm/yyyy"), C("Origem", "string"), C("Resultado", "string"),
            C("Irregular", "int64"), C("Energia_Recuperada_kWh", "int64", formato="#,0"),
            C("Score_Mes_Anterior", "double", formato="0.0"), C("Faixa_Mes_Anterior", "string"),
            C("Motivo_Mes_Anterior", "string"),
        ], "m", m("fInspecoes")),
        Tabela("FilaInspecao", [
            C("Cliente_ID", "int64", formato="0"), C("Competencia", "dateTime", oculta=True), C("Score", "double", formato="0.0"),
            C("Faixa", "string"), C("Motivo_Principal", "string"), C("Classe", "string"), C("Tipo_Medidor", "string"),
            C("Alimentador_ID", "string"), C("Subestacao", "string"), C("Municipio", "string"), C("Regional", "string"),
            C("Area_Risco", "string"), C("Prioridade", "int64", formato="0"),
        ], "m", m("FilaInspecao")),
        Tabela("LogExecucao", [
            C("Execucao_ID", "int64", formato="0"), C("Inicio", "dateTime", formato="dd/mm/yyyy hh:nn"),
            C("Fim", "dateTime", formato="dd/mm/yyyy hh:nn"), C("Status", "string"), C("Arquivos", "int64", formato="#,0"),
            C("Linhas_Lidas", "int64", formato="#,0"), C("Linhas_Carregadas", "int64", formato="#,0"),
            C("Linhas_Rejeitadas", "int64", formato="#,0"), C("Scores_Calculados", "int64", formato="#,0"),
            C("Mensagem", "string"),
        ], "m", m("LogExecucao")),
        Tabela("LogArquivo", [
            C("Execucao_ID", "int64", formato="0"), C("Arquivo", "string"), C("Tipo", "string"),
            C("Competencia", "dateTime", formato="mm/yyyy"), C("Linhas_Lidas", "int64", formato="#,0"),
            C("Linhas_Carregadas", "int64", formato="#,0"), C("Linhas_Rejeitadas", "int64", formato="#,0"),
            C("Status", "string"), C("Processado_Em", "dateTime", formato="dd/mm/yyyy hh:nn"),
        ], "m", m("LogArquivo")),
        Tabela("Rejeicoes", [
            C("Execucao_ID", "int64", oculta=True), C("Arquivo", "string"), C("Motivo", "string"),
            C("Linhas", "int64", formato="#,0"),
        ], "m", m("Rejeicoes")),
        Tabela("dCalendario", [
            C("Date", "dateTime", chave=True, formato="dd/mm/yyyy"), C("Ano", "int64", formato="0"),
            C("AnoMes", "int64", oculta=True, formato="0"), C("Mês/Ano", "string", ordenar_por="AnoMes"),
        ], "calculated", tabela_calculada("dCalendario"), datas=True),
        Tabela("Tarifa Referencia", [C("Tarifa Referencia", "double", formato="R$ 0.00")], "calculated",
               tabela_calculada("'Tarifa Referencia'")),
    ]
    relacionamentos = [
        ("dCliente.Alimentador_ID", "dAlimentador.Alimentador_ID"),
        ("fBalanco.Alimentador_ID", "dAlimentador.Alimentador_ID"),
        ("fScore.Cliente_ID", "dCliente.Cliente_ID"),
        ("fInspecoes.Cliente_ID", "dCliente.Cliente_ID"),
        ("FilaInspecao.Cliente_ID", "dCliente.Cliente_ID"),
        ("fBalanco.Competencia", "dCalendario.Date"),
        ("fScore.Competencia", "dCalendario.Date"),
        ("fInspecoes.Data_Inspecao", "dCalendario.Date"),
        ("LogArquivo.Execucao_ID", "LogExecucao.Execucao_ID"),
        ("Rejeicoes.Execucao_ID", "LogExecucao.Execucao_ID"),
    ]

    B, A, S, I, Q, L, CAL = "fBalanco", "dAlimentador", "fScore", "fInspecoes", "FilaInspecao", "LogExecucao", "dCalendario"
    seg = lambda n, x, y, h, campo, titulo=None: visual(n, "slicer", x, y, 180, h, {"Values": [campo]}, titulo)  # noqa: E731

    pagina1 = [cabecalho("titulo1", "Radar de Perdas · Balanço Energético", "Energia injetada na rede x energia faturada: o que sobra é perda")] + [
        seg("segAno1", 20, 80, 110, (CAL, "Ano", False)),
        seg("segRegional1", 20, 200, 190, (A, "Regional", False)),
        seg("segRisco1", 20, 400, 100, (A, "Area_Risco", False)),
        seg("segTarifa1", 20, 510, 190, ("Tarifa Referencia", "Tarifa Referencia", False), "Tarifa para valorar a perda (R$/kWh)"),
        visual("cartaoInjetada", "card", 220, 80, 250, 100, {"Values": [(B, "Energia Injetada (MWh)", True)]}),
        visual("cartaoPnt", "card", 482, 80, 250, 100, {"Values": [(B, "PNT (MWh)", True)]}),
        visual("cartaoPntPct", "card", 744, 80, 250, 100, {"Values": [(B, "PNT % da Energia Injetada", True)]}),
        visual("cartaoPntRs", "card", 1006, 80, 254, 100, {"Values": [(B, "PNT (R$)", True)]}),
        visual("linhaPnt", "lineChart", 220, 192, 1040, 240,
               {"Category": [(CAL, "Mês/Ano", False)], "Y": [(B, "PNT % da Energia Injetada", True)], "Series": [(A, "Area_Risco", False)]},
               "PNT % da energia injetada por mês: áreas de risco perdem várias vezes mais"),
        visual("tabelaSubestacoes", "tableEx", 220, 444, 640, 256,
               {"Values": [(A, "Regional", False), (A, "Subestacao", False), (B, "Energia Injetada (MWh)", True),
                           (B, "PNT (MWh)", True), (B, "PNT % da Energia Injetada", True), (B, "PNT (R$)", True)]},
               "Perdas por subestação", sort=((B, "PNT (MWh)", True), "Descending")),
        visual("barrasRegional", "clusteredBarChart", 872, 444, 388, 256,
               {"Category": [(A, "Regional", False)], "Y": [(B, "PNT % da Energia Injetada", True)]},
               "PNT % por regional", sort=((B, "PNT % da Energia Injetada", True), "Descending")),
    ]
    pagina2 = [cabecalho("titulo2", "Radar de Perdas · Risco de Clientes", "Score de 0 a 100 por cliente; a fila mostra quem inspecionar primeiro")] + [
        seg("segRegional2", 20, 80, 190, (A, "Regional", False)),
        seg("segFaixa2", 20, 280, 110, (Q, "Faixa", False)),
        seg("segClasse2", 20, 400, 120, ("dCliente", "Classe", False)),
        visual("cartaoMonitorados", "card", 220, 80, 250, 100, {"Values": [(B, "Clientes Monitorados", True)]}),
        visual("cartaoAlto", "card", 482, 80, 250, 100, {"Values": [(B, "Clientes Risco Alto", True)]}),
        visual("cartaoMedio", "card", 744, 80, 250, 100, {"Values": [(B, "Clientes Risco Médio", True)]}),
        visual("cartaoFila", "card", 1006, 80, 254, 100, {"Values": [(B, "Clientes na Fila de Inspeção", True)]}),
        visual("tabelaFila", "tableEx", 220, 192, 700, 508,
               {"Values": [(Q, "Prioridade", False), (Q, "Cliente_ID", False), (Q, "Score", False), (Q, "Faixa", False),
                           (Q, "Motivo_Principal", False), (Q, "Classe", False), (Q, "Subestacao", False)]},
               "Fila de inspeção do mês (sem quem foi inspecionado nos últimos 6 meses)",
               sort=((Q, "Prioridade", False), "Ascending")),
        visual("barrasMotivo", "clusteredBarChart", 932, 192, 328, 508,
               {"Category": [(S, "Motivo_Principal", False)], "Y": [(B, "Clientes Risco Alto", True)]},
               "Clientes de risco alto por motivo", sort=((B, "Clientes Risco Alto", True), "Descending")),
    ]
    pagina3 = [cabecalho("titulo3", "Radar de Perdas · Efetividade das Inspeções", "Backtest: quem o score marcava no mês anterior tinha mesmo irregularidade?")] + [
        seg("segAno3", 20, 80, 110, (CAL, "Ano", False)),
        seg("segOrigem3", 20, 200, 150, (I, "Origem", False)),
        visual("cartaoInspecoes", "card", 220, 80, 250, 100, {"Values": [(B, "Inspeções", True)]}),
        visual("cartaoAcerto", "card", 482, 80, 250, 100, {"Values": [(B, "Taxa de Acerto", True)]}),
        visual("cartaoGanho", "card", 744, 80, 250, 100, {"Values": [(B, "Ganho do Score (x)", True)]}),
        visual("cartaoReceita", "card", 1006, 80, 254, 100, {"Values": [(B, "Receita Recuperada (R$)", True)]}),
        visual("colunasFaixa", "clusteredColumnChart", 220, 192, 515, 300,
               {"Category": [(I, "Faixa_Mes_Anterior", False)], "Y": [(B, "Taxa de Acerto Aleatória", True)]},
               "Backtest (só inspeções aleatórias): irregularidade por faixa do score",
               sort=((B, "Taxa de Acerto Aleatória", True), "Descending")),
        visual("colunasOrigem", "clusteredColumnChart", 745, 192, 515, 300,
               {"Category": [(I, "Origem", False)], "Y": [(B, "Taxa de Acerto", True)]},
               "Taxa de acerto por origem da inspeção", sort=((B, "Taxa de Acerto", True), "Descending")),
        visual("linhaIrregularidades", "lineChart", 220, 504, 1040, 196,
               {"Category": [(CAL, "Mês/Ano", False)], "Y": [(B, "Irregularidades", True)]},
               "Irregularidades encontradas por mês"),
    ]
    pagina4 = [cabecalho("titulo4", "Radar de Perdas · Saúde do Pipeline", "Cada execução do Python fica registrada no banco: arquivos, linhas, rejeições e scores")] + [
        visual("cartaoUltima", "card", 20, 80, 340, 100, {"Values": [(B, "Última Execução", True)]}),
        visual("cartaoExecucoes", "card", 372, 80, 290, 100, {"Values": [(B, "Execuções", True)]}),
        visual("cartaoLidas", "card", 674, 80, 290, 100, {"Values": [(B, "Linhas Lidas", True)]}),
        visual("cartaoRejeicao", "card", 976, 80, 284, 100, {"Values": [(B, "% Rejeição", True)]}),
        visual("tabelaExecucoes", "tableEx", 20, 192, 840, 230,
               {"Values": [(L, "Execucao_ID", False), (L, "Inicio", False), (L, "Fim", False), (L, "Status", False),
                           (L, "Arquivos", False), (L, "Linhas_Lidas", False), (L, "Linhas_Rejeitadas", False),
                           (L, "Scores_Calculados", False)]},
               "Execuções do pipeline", sort=((L, "Execucao_ID", False), "Descending")),
        visual("barrasMotivos", "clusteredBarChart", 872, 192, 388, 508,
               {"Category": [("Rejeicoes", "Motivo", False)], "Y": [(B, "Linhas Rejeitadas por Motivo", True)]},
               "Linhas rejeitadas por motivo", sort=((B, "Linhas Rejeitadas por Motivo", True), "Descending")),
        visual("tabelaArquivos", "tableEx", 20, 434, 840, 266,
               {"Values": [("LogArquivo", "Arquivo", False), ("LogArquivo", "Tipo", False), ("LogArquivo", "Linhas_Lidas", False),
                           ("LogArquivo", "Linhas_Carregadas", False), ("LogArquivo", "Linhas_Rejeitadas", False),
                           ("LogArquivo", "Status", False)]},
               "Arquivos processados", sort=(("LogArquivo", "Linhas_Rejeitadas", False), "Descending")),
    ]
    paginas = [("Balanco", "Balanço Energético", pagina1), ("Risco", "Risco de Clientes", pagina2),
               ("Inspecoes", "Efetividade das Inspeções", pagina3), ("Pipeline", "Saúde do Pipeline", pagina4)]
    pbip.gerar_projeto(RAIZ, NOME, tabelas, {"Servidor": "localhost", "Banco": "RadarPerdas"}, relacionamentos, paginas,
                       forcar="--forcar" in sys.argv)


if __name__ == "__main__":
    main()
