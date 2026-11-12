// =====================================================================
// Projeto 3 - Consultas Power Query (fonte: SQL Server, modo Importar)
// Mais simples: Obter dados > SQL Server > Servidor "localhost", Banco "RadarPerdas"
// e marcar as tabelas/views abaixo. O código está aqui para usar PARÂMETROS
// (trocar de servidor de desenvolvimento para produção muda só um valor).
// Cada consulta termina com os tipos explícitos: o modelo não depende de adivinhação.
// =====================================================================

// Consulta: Servidor
"localhost"

// Consulta: Banco
"RadarPerdas"

// Consulta: dAlimentador
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "dAlimentador"]}[Data],
    Colunas = Table.SelectColumns(Dados, {"Alimentador_ID", "Subestacao", "Municipio", "Regional", "Area_Risco", "Perda_Tecnica_Pct"}),
    // BIT do SQL vira verdadeiro/falso; para o usuário, um texto claro
    AreaTexto = Table.TransformColumns(Colunas, {{"Area_Risco", each if _ then "Área de risco" else "Área regular", type text}}),
    Tipos = Table.TransformColumnTypes(AreaTexto, {
        {"Alimentador_ID", type text}, {"Subestacao", type text}, {"Municipio", type text},
        {"Regional", type text}, {"Perda_Tecnica_Pct", type number}})
in
    Tipos

// Consulta: dCliente
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "dCliente"]}[Data],
    Colunas = Table.SelectColumns(Dados, {"Cliente_ID", "Alimentador_ID", "Classe", "Tipo_Medidor", "Data_Ligacao"}),
    Tipos = Table.TransformColumnTypes(Colunas, {
        {"Cliente_ID", Int64.Type}, {"Alimentador_ID", type text}, {"Classe", type text},
        {"Tipo_Medidor", type text}, {"Data_Ligacao", type date}})
in
    Tipos

// Consulta: fBalanco
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_balanco_energetico"]}[Data],
    Tipos = Table.TransformColumnTypes(Dados, {
        {"Alimentador_ID", type text}, {"Competencia", type date},
        {"Energia_Injetada_kWh", Int64.Type}, {"Energia_Faturada_kWh", Int64.Type},
        {"Perda_Tecnica_kWh", Int64.Type}, {"PNT_kWh", Int64.Type}, {"PNT_Pct_Injetada", type number},
        {"Clientes_Faturados", Int64.Type}, {"Leituras_Estimadas", Int64.Type}})
in
    Tipos

// Consulta: fScore
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "fScoreRisco"]}[Data],
    SemAuditoria = Table.RemoveColumns(Dados, {"Calculado_Em"}),
    Tipos = Table.TransformColumnTypes(SemAuditoria, {
        {"Cliente_ID", Int64.Type}, {"Competencia", type date}, {"Score", type number}, {"Faixa", type text},
        {"Motivo_Principal", type text}, {"Pts_Queda", type number}, {"Pts_Pares", type number},
        {"Pts_Consumo_Baixo", type number}, {"Pts_Estimada", type number}, {"Pts_PNT", type number},
        {"Pts_Historico", type number}})
in
    Tipos

// Consulta: fInspecoes
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_inspecoes_score"]}[Data],
    Tipos = Table.TransformColumnTypes(Dados, {
        {"Inspecao_ID", Int64.Type}, {"Cliente_ID", Int64.Type}, {"Data_Inspecao", type date},
        {"Competencia_Inspecao", type date}, {"Origem", type text}, {"Resultado", type text},
        {"Irregular", Int64.Type}, {"Energia_Recuperada_kWh", Int64.Type}, {"Score_Mes_Anterior", type number},
        {"Faixa_Mes_Anterior", type text}, {"Motivo_Mes_Anterior", type text}})
in
    Tipos

// Consulta: FilaInspecao
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "vw_fila_inspecao"]}[Data],
    AreaTexto = Table.TransformColumns(Dados, {{"Area_Risco", each if _ then "Área de risco" else "Área regular", type text}}),
    Tipos = Table.TransformColumnTypes(AreaTexto, {
        {"Cliente_ID", Int64.Type}, {"Competencia", type date}, {"Score", type number}, {"Faixa", type text},
        {"Motivo_Principal", type text}, {"Classe", type text}, {"Tipo_Medidor", type text},
        {"Alimentador_ID", type text}, {"Subestacao", type text}, {"Municipio", type text},
        {"Regional", type text}, {"Prioridade", Int64.Type}})
in
    Tipos

// Consulta: LogExecucao
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "LogExecucao"]}[Data],
    Tipos = Table.TransformColumnTypes(Dados, {
        {"Execucao_ID", Int64.Type}, {"Inicio", type datetime}, {"Fim", type datetime}, {"Status", type text},
        {"Arquivos", Int64.Type}, {"Linhas_Lidas", Int64.Type}, {"Linhas_Carregadas", Int64.Type},
        {"Linhas_Rejeitadas", Int64.Type}, {"Scores_Calculados", Int64.Type}, {"Mensagem", type text}})
in
    Tipos

// Consulta: LogArquivo
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "LogArquivo"]}[Data],
    Tipos = Table.TransformColumnTypes(Dados, {
        {"Execucao_ID", Int64.Type}, {"Arquivo", type text}, {"Tipo", type text}, {"Competencia", type date},
        {"Linhas_Lidas", Int64.Type}, {"Linhas_Carregadas", Int64.Type}, {"Linhas_Rejeitadas", Int64.Type},
        {"Status", type text}, {"Processado_Em", type datetime}})
in
    Tipos

// Consulta: Rejeicoes
// Agrupar no Power Query "dobra" para o SQL Server (vira um GROUP BY lá): só o resumo é importado.
let
    Fonte = Sql.Database(Servidor, Banco),
    Dados = Fonte{[Schema = "dw", Item = "Rejeicao"]}[Data],
    Agrupado = Table.Group(Dados, {"Execucao_ID", "Arquivo", "Motivo"}, {{"Linhas", each Table.RowCount(_), Int64.Type}}),
    Tipos = Table.TransformColumnTypes(Agrupado, {{"Execucao_ID", Int64.Type}, {"Arquivo", type text}, {"Motivo", type text}})
in
    Tipos
