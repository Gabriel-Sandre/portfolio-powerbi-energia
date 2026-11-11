// dRegional - dimensão de regionais, DERIVADA de dMunicipios (referência, não duplica a leitura do arquivo).
// É ela que permite ligar as metas (que só existem por regional) ao faturamento (que é por município)
// sem criar relacionamento muitos-para-muitos.
let
    Origem = dMunicipios,
    SoRegional = Table.SelectColumns(Origem, {"Regional"}),
    Distintos = Table.Distinct(SoRegional),
    // Ordem de exibição fixa nos gráficos (use "Classificar por coluna" > Ordem)
    Ordem = Table.AddColumn(
        Distintos, "Ordem",
        each List.PositionOf({"Capital", "Baixada Fluminense", "Sul Fluminense", "Centro-Sul Fluminense"}, [Regional]) + 1,
        Int64.Type
    )
in
    Ordem
