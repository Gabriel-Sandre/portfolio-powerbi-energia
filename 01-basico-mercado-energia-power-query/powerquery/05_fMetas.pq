// fMetas - metas de mercado. O Excel vem no formato "largo" (um mês por coluna + coluna Total),
// que é ótimo para ler e péssimo para analisar. Aqui ele é DESPIVOTADO para o formato "longo".
let
    Origem = Excel.Workbook(File.Contents(PastaDados & "\metas_regionais.xlsx"), null, true),
    Planilha = Origem{[Item = "Metas", Kind = "Sheet"]}[Data],
    CabecalhosPromovidos = Table.PromoteHeaders(Planilha, [PromoteAllScalars = true]),

    // Se o Total não sair antes, ele vira um "mês" falso no despivotar e duplica a meta.
    SemTotal = Table.RemoveColumns(CabecalhosPromovidos, {"Total"}),

    Despivotado = Table.UnpivotOtherColumns(SemTotal, {"Regional"}, "MesAno", "Meta_GWh"),

    // "jan/25" -> 01/01/2025
    NomesMes = {"jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"},
    ColunaData = Table.AddColumn(
        Despivotado, "Data",
        each
            let
                Partes = Text.Split([MesAno], "/"),
                Mes = List.PositionOf(NomesMes, Text.Lower(Text.Trim(Partes{0}))) + 1,
                Ano = 2000 + Number.From(Partes{1})
            in
                #date(Ano, Mes, 1),
        type date
    ),

    TiposAlterados = Table.TransformColumnTypes(ColunaData, {{"Regional", type text}, {"Meta_GWh", type number}}),
    Final = Table.SelectColumns(TiposAlterados, {"Data", "Regional", "Meta_GWh"})
in
    Final
