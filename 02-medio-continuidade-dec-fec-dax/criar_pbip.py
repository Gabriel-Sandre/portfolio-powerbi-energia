"""
Gera o projeto do Power BI (PBIP) do Projeto 2 - Qualidade do Fornecimento (DEC/FEC).

Uso:
    python criar_pbip.py            (só se ainda não existir)
    python criar_pbip.py --forcar   (recria do zero, APAGANDO alterações salvas no Power BI)
    -> abra ContinuidadeDecFec.pbip no Power BI Desktop e clique em "Atualizar"

Fonte única: as consultas vêm de powerquery/consultas.pq e as medidas de dax/02_medidas.dax.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent / "ferramentas"))
import pbip  # noqa: E402
from pbip import Coluna as C, Tabela, cabecalho, cor_por_medida, visual  # noqa: E402

NOME = "ContinuidadeDecFec"

CALENDARIO = """
VAR DataMin = DATE ( YEAR ( MIN ( fInterrupcoes[Data] ) ), 1, 1 )
VAR DataMax = DATE ( YEAR ( MAX ( fInterrupcoes[Data] ) ), 12, 31 )
RETURN
    ADDCOLUMNS (
        CALENDAR ( DataMin, DataMax ),
        "Ano", YEAR ( [Date] ),
        "Mês Nº", MONTH ( [Date] ),
        "Mês", SWITCH ( MONTH ( [Date] ), 1, "Jan", 2, "Fev", 3, "Mar", 4, "Abr", 5, "Mai", 6, "Jun",
                        7, "Jul", 8, "Ago", 9, "Set", 10, "Out", 11, "Nov", 12, "Dez" ),
        "AnoMes", YEAR ( [Date] ) * 100 + MONTH ( [Date] ),
        "Mês/Ano", SWITCH ( MONTH ( [Date] ), 1, "Jan", 2, "Fev", 3, "Mar", 4, "Abr", 5, "Mai", 6, "Jun",
                            7, "Jul", 8, "Ago", 9, "Set", 10, "Out", 11, "Nov", 12, "Dez" )
                     & "/" & RIGHT ( YEAR ( [Date] ), 2 ),
        "Trimestre", "T" & QUARTER ( [Date] ),
        "Período Climático", IF ( MONTH ( [Date] ) IN { 12, 1, 2, 3 }, "Verão (chuvas)", "Demais meses" ),
        "Tem Dados", [Date] <= MAX ( fInterrupcoes[Data] )
    )
"""


def formato(nome: str) -> str | None:
    if nome.startswith(("Status", "Cor ", "Título", "Resumo")):
        return None
    if "%" in nome:
        return "0.0%"
    if nome.startswith(("Interrupções", "Conjuntos Acima", "Clientes", "CI", "Ranking")):
        return "#,0"
    return "#,0.00"


def main() -> None:
    consultas = pbip.ler_consultas(RAIZ / "powerquery" / "consultas.pq")
    medidas = [(n, e, p, formato(n)) for n, e, p in pbip.ler_medidas(RAIZ / "dax" / "02_medidas.dax")]

    tabelas = [
        Tabela("dConjuntos", [
            C("Conjunto_ID", "string", oculta=True), C("Conjunto", "string"), C("Municipio", "string"),
            C("Regional", "string"), C("Perfil", "string"), C("Clientes_Ref", "int64", formato="#,0"),
            C("Limite_DEC_Anual", "double", formato="0.0"), C("Limite_FEC_Anual", "double", formato="0.0"),
            C("Localizacao", "string", categoria="Place"),
        ], "m", consultas["dConjuntos"]),
        Tabela("dCausas", [
            C("Causa_ID", "int64", oculta=True), C("Causa", "string"), C("Grupo", "string"), C("Responsabilidade", "string"),
        ], "m", consultas["dCausas"]),
        Tabela("fBaseClientes", [
            C("Data", "dateTime", oculta=True, formato="dd/mm/yyyy"), C("Conjunto_ID", "string", oculta=True),
            C("Clientes", "int64", formato="#,0"),
        ], "m", consultas["fBaseClientes"]),
        Tabela("fInterrupcoes", [
            C("Interrupcao_ID", "int64", formato="0"), C("Conjunto_ID", "string", oculta=True), C("Alimentador", "string"),
            C("Causa_ID", "int64", oculta=True), C("Data", "dateTime", oculta=True, formato="dd/mm/yyyy"),
            C("Data_Hora_Inicio", "dateTime", formato="dd/mm/yyyy hh:nn"), C("Data_Hora_Fim", "dateTime", formato="dd/mm/yyyy hh:nn"),
            C("Duracao_min", "int64", formato="#,0"), C("Clientes_Afetados", "int64", formato="#,0"),
            C("Programada", "string"), C("Expurgavel", "string"),
        ], "m", consultas["fInterrupcoes"], medidas=medidas),
        Tabela("dCalendario", [
            C("Date", "dateTime", chave=True, formato="dd/mm/yyyy"), C("Ano", "int64", formato="0"),
            C("Mês Nº", "int64", oculta=True), C("Mês", "string", ordenar_por="Mês Nº"),
            C("AnoMes", "int64", oculta=True, formato="0"), C("Mês/Ano", "string", ordenar_por="AnoMes"),
            C("Trimestre", "string"), C("Período Climático", "string"), C("Tem Dados", "boolean"),
        ], "calculated", CALENDARIO, datas=True),
        Tabela("Top N", [C("Top N", "int64", formato="0")], "calculated",
               'SELECTCOLUMNS ( GENERATESERIES ( 3, 15, 1 ), "Top N", [Value] )'),
    ]
    relacionamentos = [
        ("fInterrupcoes.Conjunto_ID", "dConjuntos.Conjunto_ID"),
        ("fBaseClientes.Conjunto_ID", "dConjuntos.Conjunto_ID"),
        ("fInterrupcoes.Causa_ID", "dCausas.Causa_ID"),
        ("fInterrupcoes.Data", "dCalendario.Date"),
        ("fBaseClientes.Data", "dCalendario.Date"),
    ]

    F, CJ, CA, CAL = "fInterrupcoes", "dConjuntos", "dCausas", "dCalendario"
    filtros = lambda s, extra=None: [  # noqa: E731
        visual(f"segAno{s}", "slicer", 20, 80, 180, 110, {"Values": [(CAL, "Ano", False)]}),
        visual(f"segRegional{s}", "slicer", 20, 200, 180, 165, {"Values": [(CJ, "Regional", False)]}),
        extra or visual(f"segPerfil{s}", "slicer", 20, 375, 180, 130, {"Values": [(CJ, "Perfil", False)]}),
    ]
    cor_status = lambda ref: cor_por_medida(F, "Cor Status DEC", ref)  # noqa: E731

    pagina1 = [cabecalho("titulo1", "Continuidade do Fornecimento · DEC e FEC", "Indicadores dos últimos 12 meses contra o limite anual de cada conjunto")] + filtros("1") + [
        visual("cartaoDec", "card", 220, 80, 250, 100, {"Values": [(F, "DEC 12 Meses (h)", True)]}),
        visual("cartaoFec", "card", 482, 80, 250, 100, {"Values": [(F, "FEC 12 Meses (vezes)", True)]}),
        visual("cartaoLimite", "card", 744, 80, 250, 100, {"Values": [(F, "Limite DEC Anual (h)", True)]}),
        visual("cartaoAcima", "card", 1006, 80, 254, 100, {"Values": [(F, "Conjuntos Acima do Limite DEC", True)]}),
        visual("linhaDec", "lineChart", 220, 192, 1040, 250,
               {"Category": [(CAL, "Mês/Ano", False)], "Y": [(F, "DEC (h)", True), (F, "DEC Ano Anterior (h)", True)]},
               "DEC mensal (h) x mesmo mês do ano anterior: picos no verão"),
        visual("barrasRegional", "clusteredBarChart", 220, 454, 640, 246,
               {"Category": [(CJ, "Regional", False)], "Y": [(F, "DEC 12 Meses (h)", True), (F, "Limite DEC Anual (h)", True)]},
               "DEC 12 meses x limite, por regional (h)"),
        visual("roscaGrupo", "donutChart", 872, 454, 388, 246,
               {"Category": [(CA, "Grupo", False)], "Y": [(F, "DEC (h)", True)]}, "De onde vem o DEC (grupo de causa)"),
    ]
    pagina2 = [cabecalho("titulo2", "Continuidade do Fornecimento · Conjuntos", "Quem está fora do limite agora e quem está chegando perto")] + filtros("2") + [
        visual("tabelaConjuntos", "tableEx", 220, 80, 1040, 330,
               {"Values": [(CJ, "Conjunto", False), (CJ, "Regional", False), (F, "Clientes Atendidos", True),
                           (F, "DEC 12 Meses (h)", True), (F, "Limite DEC Anual (h)", True), (F, "% do Limite DEC", True),
                           (F, "Status DEC", True), (F, "Ranking DEC Conjunto", True)]},
               "Ranking de conjuntos pelo DEC dos últimos 12 meses (vermelho: acima do limite · amarelo: acima de 90%)",
               objects={"values": cor_status(f"{F}.% do Limite DEC")["values"] + cor_status(f"{F}.Status DEC")["values"]},
               sort=((F, "% do Limite DEC", True), "Descending")),
        visual("dispersao", "scatterChart", 220, 422, 620, 278,
               {"Category": [(CJ, "Conjunto", False)], "X": [(F, "% do Limite FEC", True)],
                "Y": [(F, "% do Limite DEC", True)], "Size": [(F, "Clientes Atendidos", True)]},
               "% do limite: FEC (horizontal) x DEC (vertical). Acima de 100% = fora do limite"),
        visual("barrasPerfil", "clusteredBarChart", 852, 422, 408, 278,
               {"Category": [(CJ, "Perfil", False)], "Y": [(F, "DEC 12 Meses (h)", True), (F, "Limite DEC Anual (h)", True)]},
               "DEC x limite por perfil de conjunto (h)"),
    ]
    seg_top = visual("segTopN", "slicer", 20, 375, 180, 280, {"Values": [("Top N", "Top N", False)]}, "Top N causas")
    pagina3 = [cabecalho("titulo3", "Continuidade do Fornecimento · Causas", "Pareto das causas e o peso das causas externas (furto, abalroamento, área de risco)")] + filtros("3", seg_top) + [
        visual("pareto", "lineClusteredColumnComboChart", 220, 80, 1040, 320,
               {"Category": [(CA, "Causa", False)], "Y": [(F, "DEC (h)", True)], "Y2": [(F, "DEC % Acumulado (Pareto)", True)]},
               "Pareto do DEC por causa: barras = horas, linha = % acumulado (eixo da direita)",
               objects={"valueAxis": [{"properties": {"show": pbip.lit("true"), "secShow": pbip.lit("true")}}]},
               sort=((F, "DEC (h)", True), "Descending")),
        visual("barrasTopN", "clusteredBarChart", 220, 412, 520, 288,
               {"Category": [(CA, "Causa", False)], "Y": [(F, "DEC Top N Causas (h)", True)]},
               "Top N causas (escolha o N no filtro ao lado)", sort=((F, "DEC Top N Causas (h)", True), "Descending")),
        visual("roscaResp", "donutChart", 752, 412, 250, 288,
               {"Category": [(CA, "Responsabilidade", False)], "Y": [(F, "DEC (h)", True)]}, "Interna x externa"),
        visual("cartaoExternas", "card", 1014, 412, 246, 136, {"Values": [(F, "% DEC Causas Externas", True)]}),
        visual("cartaoDuracao", "card", 1014, 560, 246, 140, {"Values": [(F, "Duração Média por Interrupção (h)", True)]}),
    ]
    seg_conj = visual("segConjunto", "slicer", 20, 375, 180, 325, {"Values": [(CJ, "Conjunto", False)]})
    pagina4 = [cabecalho("titulo4", "Continuidade do Fornecimento · Detalhe operacional", "Cada interrupção, o efeito dos dias críticos e as interrupções curtas que não entram no indicador")] + filtros("4", seg_conj) + [
        visual("cartaoDecMes", "card", 220, 80, 250, 100, {"Values": [(F, "DEC (h)", True)]}),
        visual("cartaoSemExpurgo", "card", 482, 80, 250, 100, {"Values": [(F, "DEC Sem Expurgo (h)", True)]}),
        visual("cartaoDiasCriticos", "card", 744, 80, 250, 100, {"Values": [(F, "Impacto dos Dias Críticos (h)", True)]}),
        visual("cartaoCurtas", "card", 1006, 80, 254, 100, {"Values": [(F, "Interrupções Curtas (< 3 min)", True)]}),
        visual("tabelaEventos", "tableEx", 220, 192, 1040, 508,
               {"Values": [(F, "Interrupcao_ID", False), (F, "Data_Hora_Inicio", False), (CJ, "Conjunto", False),
                           (F, "Alimentador", False), (CA, "Causa", False), (F, "Duracao_min", False),
                           (F, "Clientes_Afetados", False), (F, "Expurgavel", False)]},
               "Interrupções (maiores em clientes afetados primeiro)",
               sort=((F, "Clientes_Afetados", False), "Descending")),
    ]
    paginas = [("Executivo", "Painel Executivo", pagina1), ("Conjuntos", "Conjuntos", pagina2),
               ("Causas", "Causas", pagina3), ("Detalhe", "Detalhe operacional", pagina4)]
    pbip.gerar_projeto(RAIZ, NOME, tabelas, {"PastaDados": str(RAIZ / "dados")}, relacionamentos, paginas,
                       forcar="--forcar" in sys.argv)


if __name__ == "__main__":
    main()
