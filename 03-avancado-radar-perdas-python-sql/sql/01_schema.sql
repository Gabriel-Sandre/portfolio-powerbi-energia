/* =====================================================================
   Radar de Perdas - 01: schemas e tabelas
   Idempotente: pode rodar quantas vezes quiser (o pipeline roda a cada execução).
   Camadas:
     stg  -> staging: recebe o arquivo do dia já validado, é truncada a cada carga
     dw   -> modelo dimensional consumido pelo Power BI + tabelas de log
   ===================================================================== */

IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
GO
IF SCHEMA_ID('dw') IS NULL EXEC('CREATE SCHEMA dw');
GO

/* ----------------------------- STAGING -----------------------------
   Cada tabela de staging tem a MESMA chave primária da tabela de destino.
   Assim o MERGE junta as duas "em ordem" (merge join) sem precisar ordenar
   nem montar tabela hash, o que economiza memória do servidor. */
IF OBJECT_ID('stg.Alimentadores') IS NULL
CREATE TABLE stg.Alimentadores (
    Alimentador_ID     VARCHAR(10)   NOT NULL,
    Subestacao         NVARCHAR(60)  NOT NULL,
    Municipio          NVARCHAR(60)  NOT NULL,
    Regional           NVARCHAR(40)  NOT NULL,
    Area_Risco         BIT           NOT NULL,
    Perda_Tecnica_Pct  DECIMAL(6,4)  NOT NULL,
    CONSTRAINT PK_stg_Alimentadores PRIMARY KEY (Alimentador_ID)
);

IF OBJECT_ID('stg.Clientes') IS NULL
CREATE TABLE stg.Clientes (
    Cliente_ID      INT           NOT NULL,
    Alimentador_ID  VARCHAR(10)   NOT NULL,
    Classe          NVARCHAR(20)  NOT NULL,
    Tipo_Medidor    NVARCHAR(20)  NOT NULL,
    Data_Ligacao    DATE          NOT NULL,
    CONSTRAINT PK_stg_Clientes PRIMARY KEY (Cliente_ID)
);

IF OBJECT_ID('stg.Leituras') IS NULL
CREATE TABLE stg.Leituras (
    Cliente_ID        INT   NOT NULL,
    Competencia       DATE  NOT NULL,
    Consumo_kWh       INT   NOT NULL,
    Leitura_Estimada  BIT   NOT NULL,
    CONSTRAINT PK_stg_Leituras PRIMARY KEY (Cliente_ID, Competencia)
);

IF OBJECT_ID('stg.Injecao') IS NULL
CREATE TABLE stg.Injecao (
    Alimentador_ID        VARCHAR(10)  NOT NULL,
    Competencia           DATE         NOT NULL,
    Energia_Injetada_kWh  BIGINT       NOT NULL,
    CONSTRAINT PK_stg_Injecao PRIMARY KEY (Alimentador_ID, Competencia)
);

IF OBJECT_ID('stg.Inspecoes') IS NULL
CREATE TABLE stg.Inspecoes (
    Inspecao_ID             INT           NOT NULL,
    Cliente_ID              INT           NOT NULL,
    Data_Inspecao           DATE          NOT NULL,
    Origem                  NVARCHAR(30)  NOT NULL,
    Resultado               NVARCHAR(20)  NOT NULL,
    Energia_Recuperada_kWh  INT           NOT NULL,
    CONSTRAINT PK_stg_Inspecoes PRIMARY KEY (Inspecao_ID)
);
GO

/* ------------------------------- DW -------------------------------- */
IF OBJECT_ID('dw.dAlimentador') IS NULL
CREATE TABLE dw.dAlimentador (
    Alimentador_ID     VARCHAR(10)   NOT NULL CONSTRAINT PK_dAlimentador PRIMARY KEY,
    Subestacao         NVARCHAR(60)  NOT NULL,
    Municipio          NVARCHAR(60)  NOT NULL,
    Regional           NVARCHAR(40)  NOT NULL,
    Area_Risco         BIT           NOT NULL,
    Perda_Tecnica_Pct  DECIMAL(6,4)  NOT NULL,
    Atualizado_Em      DATETIME2(0)  NOT NULL CONSTRAINT DF_dAlimentador_At DEFAULT SYSDATETIME()
);

IF OBJECT_ID('dw.dCliente') IS NULL
CREATE TABLE dw.dCliente (
    Cliente_ID      INT           NOT NULL CONSTRAINT PK_dCliente PRIMARY KEY,
    Alimentador_ID  VARCHAR(10)   NOT NULL CONSTRAINT FK_dCliente_Alim REFERENCES dw.dAlimentador (Alimentador_ID),
    Classe          NVARCHAR(20)  NOT NULL,
    Tipo_Medidor    NVARCHAR(20)  NOT NULL,
    Data_Ligacao    DATE          NOT NULL,
    Atualizado_Em   DATETIME2(0)  NOT NULL CONSTRAINT DF_dCliente_At DEFAULT SYSDATETIME()
);

IF OBJECT_ID('dw.fLeitura') IS NULL
CREATE TABLE dw.fLeitura (
    Cliente_ID        INT           NOT NULL CONSTRAINT FK_fLeitura_Cli REFERENCES dw.dCliente (Cliente_ID),
    Competencia       DATE          NOT NULL,
    Consumo_kWh       INT           NOT NULL,
    Leitura_Estimada  BIT           NOT NULL,
    Carregado_Em      DATETIME2(0)  NOT NULL CONSTRAINT DF_fLeitura_At DEFAULT SYSDATETIME(),
    CONSTRAINT PK_fLeitura PRIMARY KEY (Cliente_ID, Competencia)
);

IF OBJECT_ID('dw.fInjecao') IS NULL
CREATE TABLE dw.fInjecao (
    Alimentador_ID        VARCHAR(10)   NOT NULL CONSTRAINT FK_fInjecao_Alim REFERENCES dw.dAlimentador (Alimentador_ID),
    Competencia           DATE          NOT NULL,
    Energia_Injetada_kWh  BIGINT        NOT NULL,
    Carregado_Em          DATETIME2(0)  NOT NULL CONSTRAINT DF_fInjecao_At DEFAULT SYSDATETIME(),
    CONSTRAINT PK_fInjecao PRIMARY KEY (Alimentador_ID, Competencia)
);

IF OBJECT_ID('dw.fInspecao') IS NULL
CREATE TABLE dw.fInspecao (
    Inspecao_ID             INT           NOT NULL CONSTRAINT PK_fInspecao PRIMARY KEY,
    Cliente_ID              INT           NOT NULL CONSTRAINT FK_fInspecao_Cli REFERENCES dw.dCliente (Cliente_ID),
    Data_Inspecao           DATE          NOT NULL,
    Origem                  NVARCHAR(30)  NOT NULL,
    Resultado               NVARCHAR(20)  NOT NULL,
    Energia_Recuperada_kWh  INT           NOT NULL,
    Carregado_Em            DATETIME2(0)  NOT NULL CONSTRAINT DF_fInspecao_At DEFAULT SYSDATETIME()
);

IF OBJECT_ID('dw.fScoreRisco') IS NULL
CREATE TABLE dw.fScoreRisco (
    Cliente_ID        INT            NOT NULL,
    Competencia       DATE           NOT NULL,
    Score             DECIMAL(5,1)   NOT NULL,
    Faixa             NVARCHAR(10)   NOT NULL,
    Motivo_Principal  NVARCHAR(80)   NOT NULL,
    Pts_Queda         DECIMAL(5,1)   NOT NULL,
    Pts_Pares         DECIMAL(5,1)   NOT NULL,
    Pts_Consumo_Baixo DECIMAL(5,1)   NOT NULL,
    Pts_Estimada      DECIMAL(5,1)   NOT NULL,
    Pts_PNT           DECIMAL(5,1)   NOT NULL,
    Pts_Historico     DECIMAL(5,1)   NOT NULL,
    Calculado_Em      DATETIME2(0)   NOT NULL CONSTRAINT DF_fScore_At DEFAULT SYSDATETIME(),
    CONSTRAINT PK_fScoreRisco PRIMARY KEY (Cliente_ID, Competencia)
);

/* ------------------------------ LOGS ------------------------------- */
IF OBJECT_ID('dw.LogExecucao') IS NULL
CREATE TABLE dw.LogExecucao (
    Execucao_ID        INT IDENTITY(1,1) CONSTRAINT PK_LogExecucao PRIMARY KEY,
    Inicio             DATETIME2(0)   NOT NULL,
    Fim                DATETIME2(0)   NULL,
    Status             NVARCHAR(30)   NOT NULL,
    Arquivos           INT            NOT NULL DEFAULT 0,
    Linhas_Lidas       INT            NOT NULL DEFAULT 0,
    Linhas_Carregadas  INT            NOT NULL DEFAULT 0,
    Linhas_Rejeitadas  INT            NOT NULL DEFAULT 0,
    Scores_Calculados  INT            NOT NULL DEFAULT 0,
    Mensagem           NVARCHAR(4000) NULL
);

IF OBJECT_ID('dw.LogArquivo') IS NULL
CREATE TABLE dw.LogArquivo (
    Execucao_ID        INT            NOT NULL CONSTRAINT FK_LogArquivo_Exec REFERENCES dw.LogExecucao (Execucao_ID),
    Arquivo            NVARCHAR(200)  NOT NULL,
    Tipo               NVARCHAR(30)   NOT NULL,
    Competencia        DATE           NULL,
    Linhas_Lidas       INT            NOT NULL,
    Linhas_Carregadas  INT            NOT NULL,
    Linhas_Rejeitadas  INT            NOT NULL,
    Status             NVARCHAR(20)   NOT NULL,
    Processado_Em      DATETIME2(0)   NOT NULL DEFAULT SYSDATETIME()
);

IF OBJECT_ID('dw.Rejeicao') IS NULL
CREATE TABLE dw.Rejeicao (
    Rejeicao_ID  INT IDENTITY(1,1) CONSTRAINT PK_Rejeicao PRIMARY KEY,
    Execucao_ID  INT            NOT NULL,
    Arquivo      NVARCHAR(200)  NOT NULL,
    Linha        INT            NOT NULL,
    Motivo       NVARCHAR(200)  NOT NULL,
    Conteudo     NVARCHAR(500)  NULL
);
GO
