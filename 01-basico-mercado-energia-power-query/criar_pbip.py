"""
Gera o projeto do Power BI (formato PBIP) do Projeto 1, pronto para abrir no Power BI Desktop.

Uso:
    python criar_pbip.py            (só funciona se o projeto ainda não existir)
    python criar_pbip.py --forcar   (recria do zero, APAGANDO o que foi salvo no Power BI)
    -> abre MercadoEnergia.pbip no Power BI Desktop e clique em "Atualizar"

Este script gera a VERSÃO INICIAL. O projeto versionado no Git já tem acabamento feito depois
(tema, cabeçalhos, página Territórios): a partir dele, edite direto no Power BI.

O PBIP guarda o relatório em arquivos de texto (TMDL para o modelo, JSON para as páginas),
o que permite versionar no Git. Este script monta:
    - as consultas Power Query da pasta powerquery/ (o caminho dos dados já vem desta pasta)
    - tipos, colunas ocultas, ordenação de meses, tabela de datas marcada
    - relacionamentos do modelo estrela
    - as medidas de dax/medidas.dax
    - duas páginas com visuais básicos (o resto do layout fica para você!)
"""
from __future__ import annotations

import itertools
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOME = "MercadoEnergia"
MODELO = RAIZ / f"{NOME}.SemanticModel"
RELATORIO = RAIZ / f"{NOME}.Report"
T = "\t"


_contador = itertools.count(1)


def guid() -> str:
    """IDs determinísticos: rodar o script de novo gera os mesmos arquivos (diff limpo no Git)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NOME}/{next(_contador)}"))


def q(nome: str) -> str:
    """Nome TMDL entre aspas simples quando necessário."""
    return nome if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome) else "'" + nome.replace("'", "''") + "'"


def bloco(texto: str, tabs: int) -> str:
    return "\n".join((T * tabs + linha) if linha.strip() else "" for linha in texto.strip("\n").splitlines())


def ler_pq(arquivo: str) -> str:
    return (RAIZ / "powerquery" / arquivo).read_text(encoding="utf-8")


# ----------------------------------------------------------------- tabelas
# coluna: (tipo TMDL, opções)
TABELAS = {
    "dMunicipios": {
        "pq": "02_dMunicipios.pq",
        "colunas": {
            "Cod_Municipio": ("string", {"oculta": True}),
            "Municipio": ("string", {}),
            "Regional": ("string", {"oculta": True}),
            "UF": ("string", {}),
            "Localizacao": ("string", {"categoria": "Place"}),
        },
    },
    "dRegional": {
        "pq": "03_dRegional.pq",
        "colunas": {
            "Regional": ("string", {"ordenar_por": "Ordem"}),
            "Ordem": ("int64", {"oculta": True}),
        },
    },
    "fFaturamento": {
        "pq": "04_fFaturamento.pq",
        "colunas": {
            "Data": ("dateTime", {"oculta": True, "formato": "dd/mm/yyyy"}),
            "Cod_Municipio": ("string", {"oculta": True}),
            "Classe": ("string", {}),
            "Qtd_Clientes": ("int64", {"formato": "#,0", "soma": True}),
            "Consumo_kWh": ("double", {"formato": "#,0", "soma": True}),
            "Valor_Faturado": ("decimal", {"formato": "R$ #,0.00", "soma": True}),
        },
    },
    "fMetas": {
        "pq": "05_fMetas.pq",
        "colunas": {
            "Data": ("dateTime", {"oculta": True, "formato": "dd/mm/yyyy"}),
            "Regional": ("string", {"oculta": True}),
            "Meta_GWh": ("double", {"formato": "#,0.0", "soma": True}),
        },
    },
    "dCalendario": {
        "pq": "06_dCalendario.pq",
        "data": True,
        "colunas": {
            "Data": ("dateTime", {"chave": True, "formato": "dd/mm/yyyy"}),
            "Ano": ("int64", {"formato": "0"}),
            "Mes_Num": ("int64", {"oculta": True}),
            "Mes": ("string", {"ordenar_por": "Mes_Num"}),
            "Mes_Ano": ("string", {"ordenar_por": "AnoMes"}),
            "AnoMes": ("int64", {"oculta": True, "formato": "0"}),
            "Trimestre": ("string", {}),
            "Periodo_Climatico": ("string", {}),
        },
    },
}

RELACIONAMENTOS = [
    ("fFaturamento.Cod_Municipio", "dMunicipios.Cod_Municipio"),
    ("dMunicipios.Regional", "dRegional.Regional"),
    ("fMetas.Regional", "dRegional.Regional"),
    ("fFaturamento.Data", "dCalendario.Data"),
    ("fMetas.Data", "dCalendario.Data"),
]

# medida -> (tabela onde fica, formato)
FORMATOS = {
    "Consumo (GWh)": ("fFaturamento", "#,0.0"),
    "Faturamento (R$)": ("fFaturamento", "R$ #,0"),
    "Tarifa Média (R$/kWh)": ("fFaturamento", "R$ #,0.000"),
    "Clientes": ("fFaturamento", "#,0"),
    "Consumo Médio por Cliente (kWh/mês)": ("fFaturamento", "#,0.0"),
    "Meta (GWh)": ("fMetas", "#,0.0"),
    "Meta Ano Completo (GWh)": ("fMetas", "#,0.0"),
    "% Atingimento da Meta": ("fMetas", "0.0%"),
    "Desvio da Meta (GWh)": ("fMetas", "+#,0.0;-#,0.0;0"),
    "Cor Atingimento": ("fMetas", None),
    "% do Consumo Total": ("fFaturamento", "0.0%"),
    "Título Dinâmico": ("fFaturamento", None),
}


def ler_medidas() -> dict[str, str]:
    medidas, atual, linhas = {}, None, []
    for linha in (RAIZ / "dax" / "medidas.dax").read_text(encoding="utf-8").splitlines():
        if atual is None:
            m = re.match(r"^([^/\s].*?) =\s*$", linha)
            if m:
                atual, linhas = m.group(1), []
        elif linha.strip() == "":
            medidas[atual] = "\n".join(linhas)
            atual = None
        else:
            linhas.append(linha)
    if atual:
        medidas[atual] = "\n".join(linhas)
    return medidas


def tabela_tmdl(nome: str, cfg: dict, medidas: dict[str, str]) -> str:
    out = [f"table {q(nome)}", f"{T}lineageTag: {guid()}"]
    if cfg.get("data"):
        out.insert(1, f"{T}dataCategory: Time")
    out.append("")
    for medida, expressao in medidas.items():
        tabela, formato = FORMATOS[medida]
        if tabela != nome:
            continue
        out.append(f"{T}measure {q(medida)} =")
        out.append(bloco(expressao, 3))
        if formato:
            out.append(f"{T}{T}formatString: {formato}")
        out.append(f"{T}{T}lineageTag: {guid()}")
        out.append("")
    for coluna, (tipo, op) in cfg["colunas"].items():
        out.append(f"{T}column {q(coluna)}")
        out.append(f"{T}{T}dataType: {tipo}")
        if op.get("chave"):
            out.append(f"{T}{T}isKey")
        if op.get("formato"):
            out.append(f"{T}{T}formatString: {op['formato']}")
        if op.get("oculta"):
            out.append(f"{T}{T}isHidden")
        if op.get("categoria"):
            out.append(f"{T}{T}dataCategory: {op['categoria']}")
        out.append(f"{T}{T}lineageTag: {guid()}")
        out.append(f"{T}{T}summarizeBy: {'sum' if op.get('soma') else 'none'}")
        out.append(f"{T}{T}sourceColumn: {coluna}")
        if op.get("ordenar_por"):
            out.append(f"{T}{T}sortByColumn: {op['ordenar_por']}")
        out.append("")
        out.append(f"{T}{T}annotation SummarizationSetBy = Automatic")
        out.append("")
    out.append(f"{T}partition {q(nome)} = m")
    out.append(f"{T}{T}mode: import")
    out.append(f"{T}{T}source =")
    out.append(bloco(ler_pq(cfg["pq"]), 4))
    out.append("")
    out.append(f"{T}annotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out)


def gerar_modelo() -> None:
    definicao = MODELO / "definition"
    (definicao / "tables").mkdir(parents=True)
    medidas = ler_medidas()
    faltando = set(medidas) - set(FORMATOS)
    if faltando:
        raise SystemExit(f"Medidas sem configuração em FORMATOS: {faltando}")

    (MODELO / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (definicao / "database.tmdl").write_text(f"database\n{T}compatibilityLevel: 1567\n", encoding="utf-8")

    ordem = ["PastaDados", "DeParaClasses", *TABELAS]
    (definicao / "model.tmdl").write_text("\n".join([
        "model Model",
        f"{T}culture: pt-BR",
        f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{T}discourageImplicitMeasures",
        f"{T}sourceQueryCulture: pt-BR",
        f"{T}dataAccessOptions",
        f"{T}{T}legacyRedirects",
        f"{T}{T}returnErrorValuesAsNull",
        "",
        f"{T}annotation PBI_QueryOrder = {json.dumps(ordem, ensure_ascii=False)}",
        "",
        f"{T}annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        *[f"ref table {q(t)}" for t in TABELAS],
        "",
    ]), encoding="utf-8")

    pasta_dados = str(RAIZ / "dados" / "brutos")
    de_para = ler_pq("01_DeParaClasses.pq")
    (definicao / "expressions.tmdl").write_text("\n".join([
        f'expression PastaDados = "{pasta_dados}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"{T}lineageTag: {guid()}",
        "",
        f"{T}annotation PBI_ResultType = Text",
        "",
        "expression DeParaClasses =",
        bloco(de_para, 2),
        f"{T}lineageTag: {guid()}",
        "",
        f"{T}annotation PBI_ResultType = Table",
        "",
    ]), encoding="utf-8")

    for nome, cfg in TABELAS.items():
        (definicao / "tables" / f"{nome}.tmdl").write_text(tabela_tmdl(nome, cfg, medidas), encoding="utf-8")

    rel = []
    for origem, destino in RELACIONAMENTOS:
        rel += [f"relationship {guid()}", f"{T}fromColumn: {origem}", f"{T}toColumn: {destino}", ""]
    (definicao / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")


# ----------------------------------------------------------------- relatório
def campo(tabela: str, nome: str, medida: bool) -> dict:
    tipo = "Measure" if medida else "Column"
    return {tipo: {"Expression": {"SourceRef": {"Source": tabela[0].lower() + tabela[1:3].lower()}}, "Property": nome},
            "Name": f"{tabela}.{nome}"}


def visual(nome: str, tipo: str, x: int, y: int, w: int, h: int, papeis: dict[str, list[tuple[str, str, bool]]],
           titulo: str | None = None) -> dict:
    tabelas = sorted({t for campos in papeis.values() for t, _, _ in campos})
    origem = [{"Name": t[0].lower() + t[1:3].lower(), "Entity": t, "Type": 0} for t in tabelas]
    selecao = [campo(t, n, m) for campos in papeis.values() for t, n, m in campos]
    projecoes = {papel: [{"queryRef": f"{t}.{n}"} for t, n, _ in campos] for papel, campos in papeis.items()}
    objetos = {}
    if titulo:
        objetos["title"] = [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "text": {"expr": {"Literal": {"Value": "'" + titulo.replace("'", "''") + "'"}}}}}]
    config = {
        "name": nome,
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h}}],
        "singleVisual": {
            "visualType": tipo,
            "projections": projecoes,
            "prototypeQuery": {"Version": 2, "From": origem, "Select": selecao},
            "drillFilterOtherVisuals": True,
            "vcObjects": objetos,
        },
    }
    return {"x": x, "y": y, "z": 0, "width": w, "height": h, "config": json.dumps(config, ensure_ascii=False), "filters": "[]"}


def gerar_relatorio() -> None:
    RELATORIO.mkdir()
    F, M, C, R = "fFaturamento", "fMetas", "dCalendario", "dRegional"
    pagina1 = [
        visual("segAno", "slicer", 20, 20, 180, 120, {"Values": [(C, "Ano", False)]}),
        visual("segRegional", "slicer", 20, 150, 180, 170, {"Values": [(R, "Regional", False)]}),
        visual("segClasse", "slicer", 20, 330, 180, 190, {"Values": [(F, "Classe", False)]}),
        visual("cartaoConsumo", "card", 220, 20, 250, 110, {"Values": [(F, "Consumo (GWh)", True)]}),
        visual("cartaoFat", "card", 485, 20, 250, 110, {"Values": [(F, "Faturamento (R$)", True)]}),
        visual("cartaoClientes", "card", 750, 20, 250, 110, {"Values": [(F, "Clientes", True)]}),
        visual("cartaoTarifa", "card", 1015, 20, 245, 110, {"Values": [(F, "Tarifa Média (R$/kWh)", True)]}),
        visual("linhaConsumo", "lineChart", 220, 145, 1040, 280,
               {"Category": [(C, "Mes_Ano", False)], "Y": [(F, "Consumo (GWh)", True)]}, "Consumo mensal (GWh)"),
        visual("barrasClasse", "clusteredBarChart", 220, 440, 515, 260,
               {"Category": [(F, "Classe", False)], "Y": [(F, "Consumo (GWh)", True)]}, "Consumo por classe (GWh)"),
        visual("barrasRegional", "clusteredBarChart", 745, 440, 515, 260,
               {"Category": [(R, "Regional", False)], "Y": [(F, "Consumo (GWh)", True)]}, "Consumo por regional (GWh)"),
    ]
    pagina2 = [
        visual("segAno2", "slicer", 20, 20, 180, 120, {"Values": [(C, "Ano", False)]}),
        visual("colunasMeta", "clusteredColumnChart", 220, 20, 1040, 330,
               {"Category": [(C, "Mes_Ano", False)], "Y": [(F, "Consumo (GWh)", True), (M, "Meta (GWh)", True)]},
               "Realizado x Meta (GWh)"),
        visual("tabelaRegional", "tableEx", 220, 365, 1040, 335,
               {"Values": [(R, "Regional", False), (F, "Consumo (GWh)", True), (M, "Meta (GWh)", True),
                           (M, "Desvio da Meta (GWh)", True), (M, "% Atingimento da Meta", True)]},
               "Atingimento por regional"),
    ]
    secoes = []
    for i, (nome, visuais) in enumerate([("Visão Geral", pagina1), ("Meta x Realizado", pagina2)]):
        secoes.append({"config": "{}", "displayName": nome, "displayOption": 1, "filters": "[]", "height": 720.0,
                       "name": f"Secao{i + 1}", "ordinal": i, "visualContainers": visuais, "width": 1280.0})
    relatorio = {
        "config": json.dumps({"version": "5.59", "themeCollection": {}, "activeSectionIndex": 0,
                              "settings": {"useStylableVisualContainerHeader": True}}),
        "layoutOptimization": 0,
        "resourcePackages": [],
        "sections": secoes,
    }
    (RELATORIO / "report.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    (RELATORIO / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}}, indent=2), encoding="utf-8")


def main() -> None:
    if (RAIZ / f"{NOME}.pbip").exists() and "--forcar" not in sys.argv:
        raise SystemExit(
            f"{NOME}.pbip já existe e pode ter alterações salvas pelo Power BI (páginas, tema, layout).\n"
            "Este script recria tudo do zero e APAGA essas alterações. Para fazer isso mesmo assim:\n"
            "    python criar_pbip.py --forcar")
    for pasta in (MODELO, RELATORIO):
        if pasta.exists():
            shutil.rmtree(pasta)
    gerar_modelo()
    gerar_relatorio()
    (RAIZ / f"{NOME}.pbip").write_text(json.dumps({
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2), encoding="utf-8")
    print(f"OK: {RAIZ / (NOME + '.pbip')}")


if __name__ == "__main__":
    main()
