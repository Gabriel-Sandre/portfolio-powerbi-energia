/* =====================================================================
   Radar de Perdas - 04: consultas analíticas (para estudar e mostrar em entrevista)
   Rode no SSMS / Azure Data Studio conectado ao banco RadarPerdas.
   ===================================================================== */

-- 1) Top 10 alimentadores com maior perda não técnica nos últimos 12 meses (CTE + TOP)
WITH ultimos12 AS (
    SELECT *
    FROM dw.vw_balanco_energetico
    WHERE Competencia > DATEADD(MONTH, -12, (SELECT MAX(Competencia) FROM dw.fInjecao))
)
SELECT TOP (10)
       u.Alimentador_ID,
       a.Subestacao,
       a.Regional,
       a.Area_Risco,
       SUM(u.PNT_kWh) / 1000.0                                          AS PNT_MWh,
       CAST(SUM(u.PNT_kWh) * 1.0 / SUM(u.Energia_Injetada_kWh) AS DECIMAL(6,3)) AS PNT_Pct
FROM ultimos12 AS u
JOIN dw.dAlimentador AS a ON a.Alimentador_ID = u.Alimentador_ID
GROUP BY u.Alimentador_ID, a.Subestacao, a.Regional, a.Area_Risco
ORDER BY PNT_MWh DESC;

-- 2) Evolução mensal da PNT por regional, com variação sobre o mês anterior (LAG)
WITH mensal AS (
    SELECT a.Regional, b.Competencia,
           SUM(b.PNT_kWh) * 1.0 / SUM(b.Energia_Injetada_kWh) AS PNT_Pct
    FROM dw.vw_balanco_energetico AS b
    JOIN dw.dAlimentador AS a ON a.Alimentador_ID = b.Alimentador_ID
    GROUP BY a.Regional, b.Competencia
)
SELECT Regional, Competencia,
       CAST(PNT_Pct AS DECIMAL(6,3)) AS PNT_Pct,
       CAST(PNT_Pct - LAG(PNT_Pct) OVER (PARTITION BY Regional ORDER BY Competencia) AS DECIMAL(6,3)) AS Var_vs_Mes_Anterior
FROM mensal
ORDER BY Regional, Competencia;

-- 3) Efetividade das inspeções por origem: a "regra de queda" e as denúncias acertam mais que o acaso?
SELECT Origem,
       COUNT(*)                                       AS Inspecoes,
       SUM(Irregular)                                 AS Irregularidades,
       CAST(AVG(CAST(Irregular AS FLOAT)) AS DECIMAL(5,3)) AS Taxa_Acerto,
       SUM(Energia_Recuperada_kWh) / 1000             AS MWh_Recuperados
FROM dw.vw_inspecoes_score
GROUP BY Origem
ORDER BY Taxa_Acerto DESC;

-- 4) Backtest do score: taxa de acerto por faixa (só inspeções aleatórias = amostra sem viés)
SELECT Faixa_Mes_Anterior,
       COUNT(*)                                       AS Inspecoes,
       CAST(AVG(CAST(Irregular AS FLOAT)) AS DECIMAL(5,3)) AS Taxa_Acerto
FROM dw.vw_inspecoes_score
WHERE Origem = N'Aleatória'
GROUP BY Faixa_Mes_Anterior
ORDER BY Taxa_Acerto DESC;

-- 5) Decis de score (NTILE): quanto da irregularidade está concentrada nos 10% mais arriscados?
WITH decis AS (
    SELECT Irregular, NTILE(10) OVER (ORDER BY Score_Mes_Anterior DESC) AS Decil
    FROM dw.vw_inspecoes_score
    WHERE Score_Mes_Anterior IS NOT NULL AND Origem = N'Aleatória'
)
SELECT Decil,
       COUNT(*)       AS Inspecoes,
       SUM(Irregular) AS Irregularidades,
       CAST(SUM(Irregular) * 1.0 / SUM(SUM(Irregular)) OVER () AS DECIMAL(5,3)) AS Pct_das_Irregularidades,
       CAST(SUM(SUM(Irregular)) OVER (ORDER BY Decil) * 1.0 / SUM(SUM(Irregular)) OVER () AS DECIMAL(5,3)) AS Pct_Acumulado
FROM decis
GROUP BY Decil
ORDER BY Decil;

-- 6) Saúde do pipeline: últimas execuções e arquivos com rejeição
SELECT TOP (10) * FROM dw.LogExecucao ORDER BY Execucao_ID DESC;

SELECT Motivo, COUNT(*) AS Linhas
FROM dw.Rejeicao
GROUP BY Motivo
ORDER BY Linhas DESC;
