/* =====================================================================
   Radar de Perdas - 03: views
   vw_balanco_energetico  -> perdas por alimentador e mês         (Power BI)
   fn_features_cliente    -> variáveis do score (funções de janela) (Python)
   vw_inspecoes_score     -> inspeções x score do mês anterior     (Power BI)
   vw_fila_inspecao       -> quem inspecionar agora                 (Power BI)
   ===================================================================== */

/* Balanço energético: tudo que entrou no alimentador e não foi faturado é perda.
   Perda total = injetada - faturada
   Perda técnica = estimada (efeito Joule, transformadores) = injetada x % técnico
   Perda NÃO técnica (PNT) = o resto: furto, fraude, ligação clandestina, erro de medição */
CREATE OR ALTER VIEW dw.vw_balanco_energetico
AS
WITH faturada AS (
    SELECT c.Alimentador_ID,
           l.Competencia,
           SUM(CAST(l.Consumo_kWh AS BIGINT)) AS Energia_Faturada_kWh,
           COUNT(*)                           AS Clientes_Faturados,
           SUM(CAST(l.Leitura_Estimada AS INT)) AS Leituras_Estimadas
    FROM dw.fLeitura AS l
    JOIN dw.dCliente AS c ON c.Cliente_ID = l.Cliente_ID
    GROUP BY c.Alimentador_ID, l.Competencia
)
SELECT i.Alimentador_ID,
       i.Competencia,
       i.Energia_Injetada_kWh,
       COALESCE(f.Energia_Faturada_kWh, 0)                                    AS Energia_Faturada_kWh,
       CAST(ROUND(i.Energia_Injetada_kWh * a.Perda_Tecnica_Pct, 0) AS BIGINT) AS Perda_Tecnica_kWh,
       i.Energia_Injetada_kWh - COALESCE(f.Energia_Faturada_kWh, 0)
           - CAST(ROUND(i.Energia_Injetada_kWh * a.Perda_Tecnica_Pct, 0) AS BIGINT) AS PNT_kWh,
       CAST((i.Energia_Injetada_kWh - COALESCE(f.Energia_Faturada_kWh, 0)
             - i.Energia_Injetada_kWh * a.Perda_Tecnica_Pct)
            / NULLIF(CAST(i.Energia_Injetada_kWh AS FLOAT), 0) AS DECIMAL(9,4)) AS PNT_Pct_Injetada,
       COALESCE(f.Clientes_Faturados, 0)  AS Clientes_Faturados,
       COALESCE(f.Leituras_Estimadas, 0)  AS Leituras_Estimadas
FROM dw.fInjecao     AS i
JOIN dw.dAlimentador AS a ON a.Alimentador_ID = i.Alimentador_ID
LEFT JOIN faturada   AS f ON f.Alimentador_ID = i.Alimentador_ID AND f.Competencia = i.Competencia;
GO

/* Variáveis do score de risco, uma linha por cliente x mês, para um intervalo de competências.

   Por que FUNÇÃO (e não view)? Uma view com funções de janela é calculada sobre a tabela
   INTEIRA antes do WHERE de quem a consulta (o filtro não "desce" para dentro da janela).
   A função recebe o intervalo e lê só o necessário: os meses pedidos + 12 meses de histórico.

   Desempenho: as janelas usam PARTITION BY Cliente_ID ORDER BY Competencia, exatamente a
   ordem da chave primária de dw.fLeitura - o SQL Server lê em ordem e não precisa ordenar
   nada (pouca memória). A mediana dos "clientes parecidos" ficou no Python (pandas), porque
   PERCENTILE_CONT como função de janela exige ordenar tudo e pede muita memória ao servidor.

   Observação: ROWS BETWEEN conta LINHAS. Se uma leitura foi rejeitada num mês, a janela
   daquele cliente cobre um mês a mais. Aceitável aqui; em produção, completar o calendário. */
DROP VIEW IF EXISTS dw.vw_features_cliente;
GO
CREATE OR ALTER FUNCTION dw.fn_features_cliente (@inicio DATE, @fim DATE)
RETURNS TABLE
AS
RETURN
WITH janelas AS (
    SELECT l.Cliente_ID,
           l.Competencia,
           l.Consumo_kWh,
           -- consumo recente: mês atual + 2 anteriores
           AVG(CAST(l.Consumo_kWh AS FLOAT)) OVER (PARTITION BY l.Cliente_ID ORDER BY l.Competencia
                                                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)  AS Media_3m,
           -- linha de base: do 12º ao 3º mês antes (não se mistura com o período recente)
           AVG(CAST(l.Consumo_kWh AS FLOAT)) OVER (PARTITION BY l.Cliente_ID ORDER BY l.Competencia
                                                   ROWS BETWEEN 12 PRECEDING AND 3 PRECEDING) AS Media_Base,
           COUNT(*) OVER (PARTITION BY l.Cliente_ID ORDER BY l.Competencia
                          ROWS BETWEEN 12 PRECEDING AND 3 PRECEDING)                          AS Meses_Base,
           SUM(CASE WHEN l.Consumo_kWh <= 30 THEN 1 ELSE 0 END)
               OVER (PARTITION BY l.Cliente_ID ORDER BY l.Competencia
                     ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)                                AS Meses_Baixos_6m,
           SUM(CAST(l.Leitura_Estimada AS INT))
               OVER (PARTITION BY l.Cliente_ID ORDER BY l.Competencia
                     ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)                                AS Leituras_Estimadas_6m
    FROM dw.fLeitura AS l
    WHERE l.Competencia BETWEEN DATEADD(MONTH, -12, @inicio) AND @fim
),
faturada AS (
    SELECT c.Alimentador_ID, l.Competencia, SUM(CAST(l.Consumo_kWh AS BIGINT)) AS Energia_Faturada_kWh
    FROM dw.fLeitura AS l
    JOIN dw.dCliente AS c ON c.Cliente_ID = l.Cliente_ID
    WHERE l.Competencia BETWEEN @inicio AND @fim
    GROUP BY c.Alimentador_ID, l.Competencia
),
pnt AS (
    SELECT i.Alimentador_ID,
           i.Competencia,
           (i.Energia_Injetada_kWh - COALESCE(f.Energia_Faturada_kWh, 0) - i.Energia_Injetada_kWh * a.Perda_Tecnica_Pct)
               / NULLIF(CAST(i.Energia_Injetada_kWh AS FLOAT), 0) AS PNT_Pct
    FROM dw.fInjecao     AS i
    JOIN dw.dAlimentador AS a ON a.Alimentador_ID = i.Alimentador_ID
    LEFT JOIN faturada   AS f ON f.Alimentador_ID = i.Alimentador_ID AND f.Competencia = i.Competencia
    WHERE i.Competencia BETWEEN @inicio AND @fim
),
historico AS (
    SELECT Cliente_ID, MIN(Data_Inspecao) AS Primeira_Irregularidade
    FROM dw.fInspecao
    WHERE Resultado = N'Irregularidade'
    GROUP BY Cliente_ID
)
SELECT j.Cliente_ID,
       j.Competencia,
       c.Alimentador_ID,
       c.Classe,
       j.Consumo_kWh,
       j.Media_3m,
       j.Media_Base,
       j.Meses_Base,
       j.Meses_Baixos_6m,
       j.Leituras_Estimadas_6m,
       p.PNT_Pct AS PNT_Pct_Alimentador,
       CASE WHEN h.Primeira_Irregularidade < j.Competencia THEN 1 ELSE 0 END AS Historico_Irregularidade
FROM janelas         AS j
JOIN dw.dCliente     AS c ON c.Cliente_ID = j.Cliente_ID
LEFT JOIN pnt        AS p ON p.Alimentador_ID = c.Alimentador_ID AND p.Competencia = j.Competencia
LEFT JOIN historico  AS h ON h.Cliente_ID = j.Cliente_ID
WHERE j.Competencia BETWEEN @inicio AND @fim;
GO

/* Backtest honesto: para cada inspeção, qual era o score do cliente no MÊS ANTERIOR?
   (o score nunca "vê" o resultado da inspeção que está avaliando) */
CREATE OR ALTER VIEW dw.vw_inspecoes_score
AS
SELECT i.Inspecao_ID,
       i.Cliente_ID,
       i.Data_Inspecao,
       DATEFROMPARTS(YEAR(i.Data_Inspecao), MONTH(i.Data_Inspecao), 1) AS Competencia_Inspecao,
       i.Origem,
       i.Resultado,
       CASE WHEN i.Resultado = N'Irregularidade' THEN 1 ELSE 0 END    AS Irregular,
       i.Energia_Recuperada_kWh,
       s.Score                                AS Score_Mes_Anterior,
       COALESCE(s.Faixa, N'Sem score')        AS Faixa_Mes_Anterior,
       s.Motivo_Principal                     AS Motivo_Mes_Anterior
FROM dw.fInspecao AS i
LEFT JOIN dw.fScoreRisco AS s
       ON s.Cliente_ID = i.Cliente_ID
      AND s.Competencia = DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(i.Data_Inspecao), MONTH(i.Data_Inspecao), 1));
GO

/* Fila de inspeção: score do último mês, sem quem já foi inspecionado nos últimos 6 meses. */
CREATE OR ALTER VIEW dw.vw_fila_inspecao
AS
WITH ultimo AS (
    SELECT MAX(Competencia) AS Competencia FROM dw.fScoreRisco
)
SELECT s.Cliente_ID,
       s.Competencia,
       s.Score,
       s.Faixa,
       s.Motivo_Principal,
       c.Classe,
       c.Tipo_Medidor,
       a.Alimentador_ID,
       a.Subestacao,
       a.Municipio,
       a.Regional,
       a.Area_Risco,
       ROW_NUMBER() OVER (ORDER BY s.Score DESC, s.Cliente_ID) AS Prioridade
FROM dw.fScoreRisco  AS s
JOIN ultimo          AS u ON u.Competencia = s.Competencia
JOIN dw.dCliente     AS c ON c.Cliente_ID = s.Cliente_ID
JOIN dw.dAlimentador AS a ON a.Alimentador_ID = c.Alimentador_ID
WHERE s.Faixa IN (N'Alto', N'Médio')
  AND NOT EXISTS (SELECT 1
                  FROM dw.fInspecao AS i
                  WHERE i.Cliente_ID = s.Cliente_ID
                    AND i.Data_Inspecao >= DATEADD(MONTH, -6, u.Competencia));
GO
