// dMunicipios - dimensão de municípios (lida do Excel).
let
    Origem = Excel.Workbook(File.Contents(PastaDados & "\municipios.xlsx"), null, true),
    Planilha = Origem{[Item = "Municipios", Kind = "Sheet"]}[Data],
    CabecalhosPromovidos = Table.PromoteHeaders(Planilha, [PromoteAllScalars = true]),
    TiposAlterados = Table.TransformColumnTypes(
        CabecalhosPromovidos,
        {{"Cod_Municipio", type text}, {"Municipio", type text}, {"Regional", type text}, {"UF", type text}}
    ),
    // Texto completo ajuda o mapa do Power BI a não confundir "Rio Claro (RJ)" com "Rio Claro (SP)".
    // Em Modelagem, defina a Categoria de Dados desta coluna como "Local".
    ColunaLocalizacao = Table.AddColumn(
        TiposAlterados, "Localizacao", each [Municipio] & ", " & [UF] & ", Brasil", type text
    )
in
    ColunaLocalizacao
