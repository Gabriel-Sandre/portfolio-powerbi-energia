// DeParaClasses - tabela auxiliar de padronização (NÃO carregar no modelo:
// botão direito na consulta > desmarcar "Habilitar carga").
let
    Origem = Csv.Document(
        File.Contents(PastaDados & "\de_para_classes.csv"),
        [Delimiter = ";", Columns = 2, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    CabecalhosPromovidos = Table.PromoteHeaders(Origem, [PromoteAllScalars = true]),
    TiposAlterados = Table.TransformColumnTypes(
        CabecalhosPromovidos,
        {{"Classe_Original", type text}, {"Classe_Padrao", type text}}
    )
in
    TiposAlterados
