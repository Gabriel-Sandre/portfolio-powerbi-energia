# Projeto 3 (avançado) · Radar de Perdas Não Técnicas

> **Foco técnico: Python + SQL Server + Power BI.** Um pipeline automatizado que recebe os arquivos do sistema comercial, valida, carrega num data warehouse em SQL Server, calcula um **score de risco de fraude/furto** para cada cliente e alimenta um painel de Power BI que diz **onde está a perda e quem inspecionar primeiro**.

*Dados 100% simulados. Projeto de portfólio independente, sem vínculo com nenhuma empresa.*

## O problema de negócio

Toda energia que entra num alimentador (medida na subestação) e não vira fatura é **perda**:

```
Energia injetada ─┬─ Energia faturada (clientes)
                  ├─ Perda técnica (física: aquecimento de cabos e transformadores)
                  └─ Perda NÃO técnica (PNT): furto, fraude no medidor, ligação clandestina, erro de leitura
```

Perdas não técnicas são um dos maiores problemas financeiros de distribuidoras em regiões metropolitanas. No Rio de Janeiro, elas se concentram em áreas onde até o acesso das equipes é restrito. A ANEEL só reconhece na tarifa uma parte dessa perda; o resto sai do caixa da empresa.

As equipes de inspeção são caras e limitadas. Se forem a endereços **ao acaso**, encontram irregularidade em poucos casos. A pergunta é:

> **Com os dados que já temos (leituras, injeção por alimentador, histórico de inspeções), dá para apontar quem tem mais chance de estar desviando energia?**

## Arquitetura

```
 Sistema de origem               Python                      SQL Server (RadarPerdas)             Power BI
 (simulado)                      src/pipeline.py
┌──────────────────┐   copia   ┌────────────┐  valida  ┌───────────────┐  MERGE   ┌──────────────────────┐   Import   ┌──────────────┐
│ dados_fonte/*.csv │ ───────► │  entrada/  │ ───────► │ stg.* (staging)│ ───────► │ dw.d* / dw.f* (estrela)│ ────────► │  4 páginas   │
└──────────────────┘ simular_  └────────────┘    │     └───────────────┘          │ dw.vw_* (views)        │           └──────────────┘
                     chegada.py                  │                                │ dw.fn_features_cliente │
                                                 ├──► dw.Rejeicao (linhas ruins + motivo)       │
                                                 │                                └──────────┬───────────┘
                                                 │     score.py (pandas)  ◄── features ──────┘
                                                 │          └──► dw.fScoreRisco
                                                 └──► dw.LogExecucao / dw.LogArquivo
       Agendador de Tarefas do Windows (agendar_pipeline.ps1) ──► roda tudo todo dia às 06:00
```

## O que este projeto mostra

| Área | Onde |
|---|---|
| **Python: ETL** | Leitura de CSV pt-BR, validação linha a linha com motivo de rejeição (`validacao.py`), carga em massa com `fast_executemany` (`db.py`) |
| **Python: orquestração** | Ordem de processamento, carga **incremental** (só o que chegou), arquivo ruim não derruba o lote, logs em arquivo e no banco (`pipeline.py`) |
| **Python: analytics** | Score explicável com pesos e motivo principal (`score.py`), backtest honesto (`avaliar_score.py`) |
| **SQL: modelagem** | Camadas staging → dw, chaves, FKs, scripts idempotentes (`01_schema.sql`) |
| **SQL: carga** | `MERGE` em procedures: reprocessar não duplica (`02_procedures.sql`) |
| **SQL: análise** | CTEs, **funções de janela** (`AVG/SUM/COUNT OVER ROWS BETWEEN`), `LAG`, `NTILE`, `ROW_NUMBER`, função com valor de tabela (`03_views.sql`, `04_consultas_analiticas.sql`) |
| **Power BI** | Fonte SQL com parâmetros, parâmetro What-if de tarifa, medidas de backtest, página de monitoramento do pipeline |
| **Automação** | Agendador de Tarefas do Windows (`agendar_pipeline.ps1`) |

## Estrutura

```
03-avancado-radar-perdas-python-sql/
├── src/
│   ├── gerar_dados.py        # simula 22 meses do sistema de origem (12 mil clientes, 54 alimentadores)
│   ├── simular_chegada.py    # "entrega" N meses na pasta entrada/
│   ├── pipeline.py           # o pipeline (ponto de entrada)
│   ├── validacao.py          # regras de qualidade por tipo de arquivo
│   ├── score.py              # score de risco 0-100
│   ├── db.py                 # conexão e carga em massa
│   └── avaliar_score.py      # backtest + comparação com o gabarito
├── sql/
│   ├── 01_schema.sql         # schemas stg/dw, tabelas, logs
│   ├── 02_procedures.sql     # MERGE staging -> dw
│   ├── 03_views.sql          # balanço, features (janelas), backtest, fila de inspeção
│   └── 04_consultas_analiticas.sql   # consultas para estudar/mostrar
├── powerbi/
│   ├── consultas.pq          # Power Query com parâmetros Servidor/Banco
│   └── medidas.dax           # ~40 medidas
└── agendar_pipeline.ps1
```

## Como rodar

```bash
pip install -r ../requirements.txt
```

```bash
python src/gerar_dados.py
```

```bash
python src/simular_chegada.py --meses 18
```

```bash
python src/pipeline.py
```

O pipeline cria sozinho o banco `RadarPerdas` no SQL Server local (autenticação do Windows). Para outro servidor, defina a variável de ambiente `RADAR_SERVIDOR`.

**Demonstrando a carga incremental:** entregue mais um mês e rode de novo. Só os 3 arquivos novos são processados e só o score do mês novo é calculado:

```bash
python src/simular_chegada.py
```

```bash
python src/pipeline.py
```

**Avaliando o score:**

```bash
python src/avaliar_score.py
```

**Agendando** (PowerShell, na pasta do projeto): `.\agendar_pipeline.ps1 -SimularChegada` faz "chegar" um mês novo por dia e roda o pipeline às 06:00.

> **Se a máquina tiver pouca RAM livre**, o SQL Server pode ficar esperando memória (`RESOURCE_SEMAPHORE`) e o pipeline fica lento. Feche programas, pare instâncias de banco que não estiver usando, ou reserve memória para o SQL Server (`min server memory`).

## Regras de qualidade (o que o pipeline rejeita)

| Regra | Exemplo |
|---|---|
| Consumo vazio | `Consumo_kWh = ""` |
| Consumo negativo | `-245` |
| Cliente não cadastrado | `Cliente_ID = 934512` |
| Leitura duplicada no mesmo arquivo | mesma linha 2 vezes |
| Competência diferente da do arquivo | `07/2025` dentro de `leituras_2025-06.csv` |
| Valores fora do domínio | `Tipo_Leitura = "Xyz"` |

Cerca de **0,3% das linhas** são rejeitadas, e cada uma fica em `dw.Rejeicao` com arquivo, número da linha, motivo e conteúdo original.

## O score de risco

Regras ponderadas (0 a 100), e não machine learning, **de propósito**: cada ponto tem explicação, e o jurídico e a equipe de campo precisam saber *por que* um endereço foi escolhido.

| Componente | Pontos | Sinal |
|---|---|---|
| Queda de consumo | 40 | média dos últimos 3 meses × linha de base do próprio cliente (meses 3 a 12 antes) |
| Clientes parecidos | 20 | consumo muito abaixo da mediana da mesma classe no mesmo alimentador |
| Consumo mínimo | 10 | meses com ≤ 30 kWh no último semestre |
| Leitura estimada | 10 | leiturista sem acesso ao medidor |
| Alimentador com perda alta | 15 | PNT do alimentador no mês |
| Irregularidade anterior | 5 | já foi pego antes |

Faixas: **Alto** ≥ 45 (~3% dos clientes) · **Médio** ≥ 25 (~4%) · **Baixo** < 25. As escalas e os cortes foram calibrados comparando variações (AUC de 0,853 → 0,867).

### Resultado do backtest

Rode `python src/avaliar_score.py`. Com a semente padrão:

**1. Inspeções aleatórias × faixa que o cliente tinha no mês anterior** (o que daria para medir na vida real):

| Faixa no mês anterior | Inspeções | Taxa de irregularidade |
|---|---|---|
| Alto | 13 | 46% |
| Médio | 44 | 43% |
| Baixo | 1.220 | 4,7% |
| **Todas as aleatórias** | 1.280 | **6,5%** |

Clientes em Médio/Alto tiveram **~7× mais irregularidade** que a média. A amostra de Alto/Médio é pequena (57 inspeções), e isso deve ser dito na apresentação.

**2. Comparado com o gabarito da simulação** (só possível porque os dados são simulados):

| Faixa (jun/2026) | Clientes | Realmente desviando | Precisão | % de todos os desvios |
|---|---|---|---|---|
| Alto | 348 | 195 | 56% | 24% |
| Médio | 428 | 208 | 49% | 26% |
| Baixo | 11.209 | 403 | 3,6% | 50% |

Os 776 clientes de Médio/Alto (6,5% da base) concentram **metade** dos desvios ativos. Os 500 de maior score têm **55%** de fraudadores, contra 6,7% na base (8× mais). A outra metade dos desvios fica em "Baixo": são, por exemplo, desvios antigos, que já estavam na linha de base do cliente. É aí que entram os próximos passos (comparação com vizinhos mais refinada, dados de medidor inteligente).

Para comparar: a "regra de queda" usada pela empresa simulada acerta 47%, mas só olha queda brusca. O score cobre mais sinais e ordena todos os clientes, não só os que caíram.

## Power BI

### Conexão
**Obter dados > SQL Server**: servidor `localhost`, banco `RadarPerdas`, modo **Importar**. Ou cole as consultas de [`powerbi/consultas.pq`](powerbi/consultas.pq), que usam os parâmetros `Servidor` e `Banco`.

### Modelo

| De (1) | Para (*) |
|---|---|
| `dAlimentador[Alimentador_ID]` | `dCliente[Alimentador_ID]`, `fBalanco[Alimentador_ID]` |
| `dCliente[Cliente_ID]` | `fScore[Cliente_ID]`, `fInspecoes[Cliente_ID]`, `FilaInspecao[Cliente_ID]` |
| `dCalendario[Date]` | `fBalanco[Competencia]`, `fScore[Competencia]`, `fInspecoes[Data_Inspecao]` |
| `LogExecucao[Execucao_ID]` | `LogArquivo[Execucao_ID]`, `Rejeicoes[Execucao_ID]` |

Crie `dCalendario` e as medidas de [`powerbi/medidas.dax`](powerbi/medidas.dax), e o parâmetro What-if **Tarifa Referencia** (0,50 a 1,50, padrão 0,95).

### Páginas sugeridas

**1. Balanço Energético**
- Cartões: Energia Injetada · PNT (MWh) · PNT % da Injetada · PNT (R$) + segmentação da tarifa.
- Cascata: Injetada → Faturada → Perda Técnica → PNT.
- Linha: `PNT % da Energia Injetada` por mês, por `Area_Risco`.
- Matriz: Regional > Subestação > Alimentador com PNT % e formatação condicional.

**2. Risco de Clientes**
- Cartões: Clientes Monitorados · Risco Alto · Risco Médio · Na Fila de Inspeção.
- Tabela `FilaInspecao` ordenada por `Prioridade`, com `Motivo_Principal`: a "lista de trabalho" do dia.
- Barras: clientes de risco alto por `Motivo_Principal`.
- Histograma de `Score` (agrupe em faixas de 10).

**3. Efetividade das Inspeções**
- Colunas: `Taxa de Acerto` por `Origem`.
- Colunas: `Taxa de Acerto` (aleatórias) por `Faixa_Mes_Anterior`: **o gráfico que vende o projeto**.
- Cartões: `Ganho do Score (x)` · `Irregularidades Adicionais com Score` · `Receita Recuperada (R$)`.

**4. Pipeline (monitoramento)**
- Cartão com `Texto Atualização` e cor por `Cor Status Pipeline`.
- Tabela `LogExecucao` e `LogArquivo`.
- Barras: `Rejeicoes[Linhas]` por `Motivo`.
- Linha: `% Rejeição` por execução.

## Como apresentar

> "Montei um pipeline em Python que todo dia pega os arquivos do sistema comercial, valida linha a linha, carrega num SQL Server com MERGE e calcula um score de risco de perda não técnica com funções de janela. No backtest com inspeções aleatórias, os clientes que o score marcava como alto risco tinham taxa de irregularidade muito maior que a média. Ou seja: com as mesmas equipes, daria para encontrar várias vezes mais irregularidades. O painel tem uma página só para monitorar se o próprio pipeline está saudável."

Perguntas que costumam vir, e as respostas:
- *Por que não machine learning?* Explicabilidade, e ainda não há rótulos suficientes. O backtest já está pronto para comparar com um modelo depois.
- *Como evita que o score "cole" do resultado?* O backtest usa o score do **mês anterior** à inspeção.
- *E se o arquivo chegar duas vezes?* MERGE: reprocessar não duplica.
- *E se um arquivo vier corrompido?* Vai para `rejeitados/`, o erro fica no log e os outros arquivos seguem.
