// dCalendario - tabela de datas criada no próprio Power Query (sem depender de arquivo).
// Depois de carregar: Ferramentas de tabela > Marcar como tabela de datas > coluna Data.
// Classifique "Mes" e "Mes_Ano" pela coluna "AnoMes" (senão os meses saem em ordem alfabética).
let
    Inicio = #date(2025, 1, 1),
    Fim = #date(2026, 12, 31),
    ListaDatas = List.Dates(Inicio, Duration.Days(Fim - Inicio) + 1, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(ListaDatas, Splitter.SplitByNothing(), {"Data"}),
    TipoData = Table.TransformColumnTypes(Tabela, {{"Data", type date}}),

    NomesMes = {"Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"},

    Ano = Table.AddColumn(TipoData, "Ano", each Date.Year([Data]), Int64.Type),
    MesNum = Table.AddColumn(Ano, "Mes_Num", each Date.Month([Data]), Int64.Type),
    Mes = Table.AddColumn(MesNum, "Mes", each NomesMes{[Mes_Num] - 1}, type text),
    MesAno = Table.AddColumn(Mes, "Mes_Ano", each [Mes] & "/" & Text.End(Text.From([Ano]), 2), type text),
    AnoMes = Table.AddColumn(MesAno, "AnoMes", each [Ano] * 100 + [Mes_Num], Int64.Type),
    Trimestre = Table.AddColumn(AnoMes, "Trimestre", each "T" & Text.From(Date.QuarterOfYear([Data])), type text),
    Estacao = Table.AddColumn(
        Trimestre, "Periodo_Climatico",
        each if List.Contains({12, 1, 2, 3}, [Mes_Num]) then "Verão" else "Demais meses",
        type text
    )
in
    Estacao
