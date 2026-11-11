// =====================================================================
// Projeto 3 - Consultas Power Query (fonte: SQL Server, modo Importar)
// Mais simples: Obter dados > SQL Server > Servidor "localhost", Banco "RadarPerdas"
// e marcar as tabelas/views abaixo. O código está aqui para usar PARÂMETROS
// (trocar de servidor de desenvolvimento para produção muda só um valor).
// =====================================================================

// Consulta: Servidor  (parâmetro)
"localhost" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]

// Consulta: Banco  (parâmetro)
"RadarPerdas" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]


// Consulta: dAlimentador
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "dAlimentador"]}[Data],
    Colunas = Table.SelectColumns(Dados, {"Alimentador_ID", "Subestacao", "Municipio", "Regional", "Area_Risco", "Perda_Tecnica_Pct"}),
    AreaTexto = Table.TransformColumns(Colunas, {{"Area_Risco", each if _ then "Área de risco" else "Área regular", type text}})
in
    AreaTexto

// Consulta: dCliente
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "dCliente"]}[Data],
    Colunas = Table.SelectColumns(Dados, {"Cliente_ID", "Alimentador_ID", "Classe", "Tipo_Medidor", "Data_Ligacao"})
in
    Colunas

// Consulta: fBalanco
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_balanco_energetico"]}[Data]
in
    Dados

// Consulta: fScore  (histórico mensal do score de cada cliente)
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "fScoreRisco"]}[Data],
    SemAuditoria = Table.RemoveColumns(Dados, {"Calculado_Em"})
in
    SemAuditoria

// Consulta: fInspecoes  (inspeções + score que o cliente tinha no mês anterior)
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_inspecoes_score"]}[Data]
in
    Dados

// Consulta: FilaInspecao  (lista de trabalho para as equipes de campo)
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_fila_inspecao"]}[Data],
    AreaTexto = Table.TransformColumns(Dados, {{"Area_Risco", each if _ then "Área de risco" else "Área regular", type text}})
in
    AreaTexto

// Consulta: LogExecucao
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "LogExecucao"]}[Data]
in
    Dados

// Consulta: LogArquivo
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "LogArquivo"]}[Data]
in
    Dados

// Consulta: Rejeicoes  (motivo agregado - não precisa trazer linha a linha)
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Value.NativeQuery(
        Fonte,
        "SELECT Execucao_ID, Arquivo, Motivo, COUNT(*) AS Linhas FROM dw.Rejeicao GROUP BY Execucao_ID, Arquivo, Motivo",
        null,
        [EnableFolding = true]
    )
in
    Dados
