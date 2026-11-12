// =====================================================================
// Projeto 2 - Consultas Power Query (carga simples; o foco aqui é DAX)
// Crie cada uma em: Nova Fonte > Consulta Nula > Editor Avançado.
// O nome da consulta é o que está no comentário "// Consulta:".
// O "pt-BR" no fim de cada TransformColumnTypes garante que 8,5 vire 8.5 e que
// 03/01/2025 seja 3 de janeiro, independente do idioma do seu Power BI.
// =====================================================================

// Consulta: PastaDados  (parâmetro - ajuste o caminho)
"C:\Users\gabri\Downloads\portfolio-powerbi-energia\02-medio-continuidade-dec-fec-dax\dados"
    meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]


// Consulta: dConjuntos
let
    Origem = Csv.Document(File.Contents(PastaDados & "\dConjuntos.csv"), [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Origem, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos, {
        {"Conjunto_ID", type text}, {"Conjunto", type text}, {"Municipio", type text}, {"Regional", type text},
        {"Perfil", type text}, {"Clientes_Ref", Int64.Type},
        {"Limite_DEC_Anual", type number}, {"Limite_FEC_Anual", type number}}, "pt-BR"),
    // o arquivo traz "urbano", "periferia", "interior": deixa com inicial maiúscula para os visuais
    PerfilFormatado = Table.TransformColumns(Tipos, {{"Perfil", Text.Proper, type text}}),
    Localizacao = Table.AddColumn(PerfilFormatado, "Localizacao", each [Municipio] & ", RJ, Brasil", type text)
in
    Localizacao


// Consulta: dCausas
let
    Origem = Csv.Document(File.Contents(PastaDados & "\dCausas.csv"), [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Origem, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos, {
        {"Causa_ID", Int64.Type}, {"Causa", type text}, {"Grupo", type text}, {"Responsabilidade", type text}}, "pt-BR")
in
    Tipos


// Consulta: fBaseClientes
let
    Origem = Csv.Document(File.Contents(PastaDados & "\fBaseClientes.csv"), [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Origem, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos, {
        {"Data", type date}, {"Conjunto_ID", type text}, {"Clientes", Int64.Type}}, "pt-BR")
in
    Tipos


// Consulta: fInterrupcoes
let
    Origem = Csv.Document(File.Contents(PastaDados & "\fInterrupcoes.csv"), [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.None]),
    Cabecalhos = Table.PromoteHeaders(Origem, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos, {
        {"Interrupcao_ID", Int64.Type}, {"Conjunto_ID", type text}, {"Alimentador", type text},
        {"Causa_ID", Int64.Type}, {"Data", type date}, {"Data_Hora_Inicio", type datetime},
        {"Data_Hora_Fim", type datetime}, {"Duracao_min", Int64.Type}, {"Clientes_Afetados", Int64.Type},
        {"Programada", type text}, {"Expurgavel", type text}}, "pt-BR")
in
    Tipos
