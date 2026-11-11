/* =====================================================================
   Radar de Perdas - 02: procedures de carga (staging -> dw)
   Todas usam MERGE: reprocessar o mesmo arquivo NÃO duplica dados
   (a carga é idempotente). Uma correção enviada depois pelo sistema
   de origem simplesmente atualiza o registro.
   ===================================================================== */

CREATE OR ALTER PROCEDURE dw.usp_carregar_alimentadores
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.dAlimentador AS d
    USING stg.Alimentadores AS s
        ON d.Alimentador_ID = s.Alimentador_ID
    WHEN MATCHED AND (d.Subestacao <> s.Subestacao OR d.Municipio <> s.Municipio OR d.Regional <> s.Regional
                      OR d.Area_Risco <> s.Area_Risco OR d.Perda_Tecnica_Pct <> s.Perda_Tecnica_Pct) THEN
        UPDATE SET Subestacao = s.Subestacao, Municipio = s.Municipio, Regional = s.Regional,
                   Area_Risco = s.Area_Risco, Perda_Tecnica_Pct = s.Perda_Tecnica_Pct, Atualizado_Em = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (Alimentador_ID, Subestacao, Municipio, Regional, Area_Risco, Perda_Tecnica_Pct)
        VALUES (s.Alimentador_ID, s.Subestacao, s.Municipio, s.Regional, s.Area_Risco, s.Perda_Tecnica_Pct);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_carregar_clientes
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.dCliente AS d
    USING stg.Clientes AS s
        ON d.Cliente_ID = s.Cliente_ID
    WHEN MATCHED AND (d.Alimentador_ID <> s.Alimentador_ID OR d.Classe <> s.Classe
                      OR d.Tipo_Medidor <> s.Tipo_Medidor OR d.Data_Ligacao <> s.Data_Ligacao) THEN
        UPDATE SET Alimentador_ID = s.Alimentador_ID, Classe = s.Classe, Tipo_Medidor = s.Tipo_Medidor,
                   Data_Ligacao = s.Data_Ligacao, Atualizado_Em = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (Cliente_ID, Alimentador_ID, Classe, Tipo_Medidor, Data_Ligacao)
        VALUES (s.Cliente_ID, s.Alimentador_ID, s.Classe, s.Tipo_Medidor, s.Data_Ligacao);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_carregar_leituras
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.fLeitura AS d
    USING stg.Leituras AS s
        ON d.Cliente_ID = s.Cliente_ID AND d.Competencia = s.Competencia
    WHEN MATCHED AND (d.Consumo_kWh <> s.Consumo_kWh OR d.Leitura_Estimada <> s.Leitura_Estimada) THEN
        UPDATE SET Consumo_kWh = s.Consumo_kWh, Leitura_Estimada = s.Leitura_Estimada, Carregado_Em = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (Cliente_ID, Competencia, Consumo_kWh, Leitura_Estimada)
        VALUES (s.Cliente_ID, s.Competencia, s.Consumo_kWh, s.Leitura_Estimada);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_carregar_injecao
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.fInjecao AS d
    USING stg.Injecao AS s
        ON d.Alimentador_ID = s.Alimentador_ID AND d.Competencia = s.Competencia
    WHEN MATCHED AND d.Energia_Injetada_kWh <> s.Energia_Injetada_kWh THEN
        UPDATE SET Energia_Injetada_kWh = s.Energia_Injetada_kWh, Carregado_Em = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (Alimentador_ID, Competencia, Energia_Injetada_kWh)
        VALUES (s.Alimentador_ID, s.Competencia, s.Energia_Injetada_kWh);
END
GO

CREATE OR ALTER PROCEDURE dw.usp_carregar_inspecoes
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dw.fInspecao AS d
    USING stg.Inspecoes AS s
        ON d.Inspecao_ID = s.Inspecao_ID
    WHEN MATCHED AND (d.Resultado <> s.Resultado OR d.Energia_Recuperada_kWh <> s.Energia_Recuperada_kWh) THEN
        UPDATE SET Resultado = s.Resultado, Energia_Recuperada_kWh = s.Energia_Recuperada_kWh, Carregado_Em = SYSDATETIME()
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (Inspecao_ID, Cliente_ID, Data_Inspecao, Origem, Resultado, Energia_Recuperada_kWh)
        VALUES (s.Inspecao_ID, s.Cliente_ID, s.Data_Inspecao, s.Origem, s.Resultado, s.Energia_Recuperada_kWh);
END
GO
