// fFaturamento - tabela fato. Junta os 22 CSVs mensais e trata os problemas do sistema de origem:
//   1. 2 linhas de "relatório" antes do cabeçalho          -> Table.Skip
//   2. linha "TOTAL GERAL" no fim de cada arquivo           -> filtro de linhas
//   3. códigos de município com espaço e minúsculas         -> Aparar + Maiúsculas
//   4. nome do município escrito de 5 jeitos diferentes     -> descartado; o nome oficial vem de dMunicipios
//   5. classe escrita de 15 jeitos ("RES", "Res.", ...)     -> Mesclar com a tabela DeParaClasses
//   6. números em pt-BR ("1.234.567,89") e "R$ " no valor   -> Substituir + Alterar tipo usando localidade
//   7. competência como texto "01/2025"                     -> coluna Data (1º dia do mês)
//   8. linhas exportadas em duplicidade                     -> Remover duplicatas
let
    Origem = Folder.Files(PastaDados & "\faturamento"),
    ApenasCsv = Table.SelectRows(Origem, each Text.Lower([Extension]) = ".csv"),

    // Lê cada arquivo: pula as 2 linhas de cabeçalho do relatório e promove a 3ª linha a cabeçalho.
    ArquivosLidos = Table.AddColumn(
        ApenasCsv, "Tabela",
        each Table.PromoteHeaders(
            Table.Skip(
                Csv.Document([Content], [Delimiter = ";", Columns = 7, Encoding = 65001, QuoteStyle = QuoteStyle.None]),
                2
            ),
            [PromoteAllScalars = true]
        )
    ),
    Combinado = Table.Combine(ArquivosLidos[Tabela]),

    SemTotais = Table.SelectRows(
        Combinado,
        each [Competencia] <> null and [Competencia] <> "" and not Text.StartsWith(Text.Upper([Competencia]), "TOTAL")
    ),

    TextosPadronizados = Table.TransformColumns(
        SemTotais,
        {
            {"Competencia", Text.Trim, type text},
            {"Cod_Municipio", each Text.Upper(Text.Trim(_)), type text},
            {"Classe", each Text.Upper(Text.Trim(_)), type text},
            {"Valor_Faturado", each Text.Trim(Text.Replace(_, "R$", "")), type text}
        }
    ),

    // O 3º argumento "pt-BR" é o que faz "1.234,56" virar 1234,56 (e não 123456 ou erro).
    TiposAlterados = Table.TransformColumnTypes(
        TextosPadronizados,
        {{"Qtd_Clientes", Int64.Type}, {"Consumo_kWh", type number}, {"Valor_Faturado", Currency.Type}},
        "pt-BR"
    ),

    ColunaData = Table.AddColumn(
        TiposAlterados, "Data",
        each #date(Number.From(Text.End([Competencia], 4)), Number.From(Text.Start([Competencia], 2)), 1),
        type date
    ),

    MesclarDePara = Table.NestedJoin(ColunaData, {"Classe"}, DeParaClasses, {"Classe_Original"}, "DePara", JoinKind.LeftOuter),
    ExpandirDePara = Table.ExpandTableColumn(MesclarDePara, "DePara", {"Classe_Padrao"}),

    ColunasBrutasRemovidas = Table.RemoveColumns(ExpandirDePara, {"Competencia", "Municipio", "Classe"}),
    Renomeado = Table.RenameColumns(ColunasBrutasRemovidas, {{"Classe_Padrao", "Classe"}}),

    // Só agora (com tudo padronizado) as duplicatas ficam idênticas e podem ser removidas.
    SemDuplicatas = Table.Distinct(Renomeado),

    Final = Table.SelectColumns(
        SemDuplicatas,
        {"Data", "Cod_Municipio", "Classe", "Qtd_Clientes", "Consumo_kWh", "Valor_Faturado"}
    )
in
    Final
