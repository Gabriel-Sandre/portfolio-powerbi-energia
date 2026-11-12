# Portfólio Power BI · Distribuição de Energia

Três projetos de BI com o dia a dia de uma **distribuidora de energia no Rio de Janeiro** como tema: mercado e faturamento, qualidade do fornecimento regulada pela ANEEL (DEC/FEC) e combate a perdas não técnicas. Cada projeto aprofunda uma parte do trabalho de dados, do tratamento no **Power Query** ao **DAX** e a um **pipeline automatizado em Python + SQL Server**.

<table>
<tr>
<td width="33%"><a href="01-basico-mercado-energia-power-query/"><img src="01-basico-mercado-energia-power-query/imagens/01-visao-geral.png" alt="Projeto 1: mercado de energia"></a><br><sub><b>1 · Mercado de Energia</b></sub></td>
<td width="33%"><a href="02-medio-continuidade-dec-fec-dax/"><img src="02-medio-continuidade-dec-fec-dax/imagens/01-painel-executivo.png" alt="Projeto 2: DEC e FEC"></a><br><sub><b>2 · DEC e FEC</b></sub></td>
<td width="33%"><a href="03-avancado-radar-perdas-python-sql/"><img src="03-avancado-radar-perdas-python-sql/imagens/01-balanco-energetico.png" alt="Projeto 3: radar de perdas"></a><br><sub><b>3 · Radar de Perdas</b></sub></td>
</tr>
</table>

## Projetos

| # | Projeto | Foco técnico | Pergunta de negócio | Status |
|---|---|---|---|---|
| 1 | [Mercado de Energia da Área de Concessão](01-basico-mercado-energia-power-query/) | **Power Query**: 22 arquivos "sujos" → modelo confiável | Quanto consumimos e faturamos por município e classe? Estamos na meta? | ✅ Painel pronto (`.pbip`, 3 páginas) |
| 2 | [Qualidade do Fornecimento: DEC e FEC](02-medio-continuidade-dec-fec-dax/) | **DAX**: indicadores regulatórios, inteligência de tempo, Pareto | Quais conjuntos estouram os limites da ANEEL e por quê? | ✅ Painel pronto (`.pbip`, 4 páginas) |
| 3 | [Radar de Perdas Não Técnicas](03-avancado-radar-perdas-python-sql/) | **Python + SQL Server**: ETL validado, MERGE, funções de janela, score de risco | Onde está a energia que não é faturada, e quem inspecionar primeiro? | ✅ Pipeline + painel pronto (`.pbip`, 4 páginas) |

## Destaques

- **Dados do mundo real são bagunçados**: o projeto 1 trata cabeçalhos de relatório, totais embutidos, duplicatas, números em formato brasileiro e 15 grafias diferentes para 5 classes de consumo, num processo que roda sozinho a cada mês novo.
- **Regra de negócio certa no DAX**: DEC/FEC calculados mês a mês como a regulação pede, com média ponderada nos limites e a armadilha do "ano incompleto" tratada. Os resultados batem com um cálculo independente em Python.
- **Engenharia de dados de ponta a ponta**: carga incremental e idempotente, rejeição de linhas com motivo registrado, log de execuções e agendamento. O score de perdas foi validado com backtest: clientes de risco médio/alto tiveram **~7× mais irregularidades** que a média nas inspeções aleatórias.

## Tecnologias

Power BI Desktop (Power Query/M, DAX, PBIP/TMDL) · Python (pandas, pyodbc) · SQL Server (T-SQL, MERGE, funções de janela, funções com valor de tabela) · Git

## Como rodar

- **Projetos 1 e 2:** abra o `.pbip` da pasta no Power BI Desktop e clique em **Atualizar**. Se a pasta for outra, ajuste o parâmetro `PastaDados`.
- **Projeto 3:** rode o pipeline primeiro (README da pasta), depois abra `RadarPerdas.pbip` e clique em **Atualizar**.
- Os painéis foram gerados por código (`criar_pbip.py` de cada projeto + `ferramentas/pbip.py`) e são editáveis normalmente no Power BI.
- Python 3.11+: `pip install -r requirements.txt`. O projeto 3 usa SQL Server local com autenticação do Windows.

> **Dados simulados.** Todos os dados são gerados por scripts Python com semente fixa (reprodutíveis). Nomes de bairros e municípios dão contexto realista, mas nenhum número representa uma empresa real. Projeto pessoal e independente, sem vínculo com nenhuma distribuidora.
