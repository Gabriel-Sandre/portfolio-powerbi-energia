"""
Biblioteca para gerar projetos do Power BI no formato PBIP (texto), usada pelos criar_pbip.py.

Um projeto PBIP tem duas partes:
    <Nome>.SemanticModel/   o modelo em TMDL (tabelas, colunas, consultas M, medidas, relacionamentos)
    <Nome>.Report/          o relatório em PBIR (um JSON por página e por visual)
    <Nome>.pbip             o arquivo que você abre no Power BI Desktop

Por que gerar por código? Porque assim o painel é reproduzível e versionável no Git, e as
consultas/medidas têm uma fonte única (os arquivos .pq e .dax de cada projeto).
Depois de gerado, o projeto é editado normalmente no Power BI (Ctrl+S grava nos mesmos arquivos).
"""
from __future__ import annotations

import itertools
import json
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

T = "\t"
TEMA = Path(__file__).resolve().parent / "TemaEnergiaRJ.json"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


# ------------------------------------------------------------------ utilidades
class Ids:
    """GUIDs determinísticos: gerar de novo produz os mesmos arquivos (diff limpo no Git)."""

    def __init__(self, semente: str):
        self.semente, self.n = semente, itertools.count(1)

    def __call__(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.semente}/{next(self.n)}"))


def q(nome: str) -> str:
    """Nome no TMDL: entre aspas simples quando tem espaço, acento ou símbolo."""
    return nome if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome) else "'" + nome.replace("'", "''") + "'"


def bloco(texto: str, tabs: int) -> str:
    return "\n".join((T * tabs + linha) if linha.strip() else "" for linha in texto.strip("\n").splitlines())


def ler_medidas(arquivo: Path) -> list[tuple[str, str, str]]:
    """Lê um .dax no formato 'Nome =' + corpo + linha em branco. Devolve (nome, expressão, pasta).
    A pasta de exibição vem do último cabeçalho '// ===== N. Título =====' antes da medida."""
    medidas, atual, linhas, pasta = [], None, [], ""
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        cab = re.match(r"^//\s*=+\s*(.+?)\s*=+\s*$", linha)
        if atual is None and cab:
            pasta = cab.group(1)
            continue
        if atual is None:
            m = re.match(r"^([^/\s].*?) =\s*$", linha)
            if m:
                atual, linhas = m.group(1), []
        elif linha.strip() == "":
            medidas.append((atual, "\n".join(linhas), pasta))
            atual = None
        else:
            linhas.append(linha)
    if atual:
        medidas.append((atual, "\n".join(linhas), pasta))
    return medidas


def ler_consultas(arquivo: Path) -> dict[str, str]:
    """Separa um .pq com várias consultas marcadas por '// Consulta: Nome'."""
    consultas, nome, linhas = {}, None, []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^// Consulta:\s*(\S+)", linha)
        if m:
            if nome:
                consultas[nome] = "\n".join(linhas).strip()
            nome, linhas = m.group(1), []
        elif nome:
            linhas.append(linha)
    if nome:
        consultas[nome] = "\n".join(linhas).strip()
    return consultas


# ------------------------------------------------------------------ modelo (TMDL)
@dataclass
class Coluna:
    nome: str
    tipo: str                      # string | int64 | double | decimal | dateTime | boolean
    oculta: bool = False
    formato: str | None = None
    categoria: str | None = None   # Place, ...
    chave: bool = False
    soma: bool = False
    ordenar_por: str | None = None


@dataclass
class Tabela:
    nome: str
    colunas: list[Coluna]
    tipo_particao: str             # "m" (Power Query) ou "calculated" (DAX)
    codigo: str
    datas: bool = False            # marcar como tabela de datas
    medidas: list[tuple[str, str, str, str | None]] = field(default_factory=list)  # nome, expr, pasta, formato


def tabela_tmdl(t: Tabela, ids: Ids) -> str:
    calc = t.tipo_particao == "calculated"
    out = [f"table {q(t.nome)}", f"{T}lineageTag: {ids()}"]
    if t.datas:
        out.append(f"{T}dataCategory: Time")
    out.append("")
    for nome, expr, pasta, formato in t.medidas:
        out.append(f"{T}measure {q(nome)} =")
        out.append(bloco(expr, 3))
        if formato:
            out.append(f"{T}{T}formatString: {formato}")
        if pasta:
            out.append(f"{T}{T}displayFolder: {pasta}")
        out.append(f"{T}{T}lineageTag: {ids()}")
        out.append("")
    for c in t.colunas:
        out.append(f"{T}column {q(c.nome)}")
        out.append(f"{T}{T}dataType: {c.tipo}")
        if c.chave:
            out.append(f"{T}{T}isKey")
        if c.formato:
            out.append(f"{T}{T}formatString: {c.formato}")
        if c.oculta:
            out.append(f"{T}{T}isHidden")
        if c.categoria:
            out.append(f"{T}{T}dataCategory: {c.categoria}")
        out.append(f"{T}{T}lineageTag: {ids()}")
        out.append(f"{T}{T}summarizeBy: {'sum' if c.soma else 'none'}")
        if calc:
            out.append(f"{T}{T}isNameInferred")
            out.append(f"{T}{T}sourceColumn: [{c.nome}]")
        else:
            out.append(f"{T}{T}sourceColumn: {c.nome}")
        if c.ordenar_por:
            out.append(f"{T}{T}sortByColumn: {q(c.ordenar_por)}")
        out += ["", f"{T}{T}annotation SummarizationSetBy = Automatic", ""]
    out.append(f"{T}partition {q(t.nome)} = {t.tipo_particao}")
    out.append(f"{T}{T}mode: import")
    out.append(f"{T}{T}source =")
    out.append(bloco(t.codigo, 4))
    out += ["", f"{T}annotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def escrever_modelo(pasta: Path, nome: str, tabelas: list[Tabela], parametros: dict[str, str],
                    relacionamentos: list[tuple[str, str]], ids: Ids) -> None:
    definicao = pasta / "definition"
    (definicao / "tables").mkdir(parents=True)
    (pasta / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (definicao / "database.tmdl").write_text(f"database\n{T}compatibilityLevel: 1606\n", encoding="utf-8")
    ordem = list(parametros) + [t.nome for t in tabelas if t.tipo_particao == "m"]
    (definicao / "model.tmdl").write_text("\n".join([
        "model Model", f"{T}culture: pt-BR", f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{T}discourageImplicitMeasures", f"{T}sourceQueryCulture: pt-BR", f"{T}dataAccessOptions",
        f"{T}{T}legacyRedirects", f"{T}{T}returnErrorValuesAsNull", "",
        f"{T}annotation PBI_QueryOrder = {json.dumps(ordem, ensure_ascii=False)}", "",
        f"{T}annotation __PBI_TimeIntelligenceEnabled = 0", "",
        *[f"ref table {q(t.nome)}" for t in tabelas], "",
    ]), encoding="utf-8")
    if parametros:
        linhas = []
        for p, valor in parametros.items():
            linhas += [f'expression {p} = "{valor}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                       f"{T}lineageTag: {ids()}", "", f"{T}annotation PBI_ResultType = Text", ""]
        (definicao / "expressions.tmdl").write_text("\n".join(linhas), encoding="utf-8")
    for t in tabelas:
        (definicao / "tables" / f"{t.nome}.tmdl").write_text(tabela_tmdl(t, ids), encoding="utf-8")
    rel = []
    for origem, destino in relacionamentos:
        rel += [f"relationship {ids()}", f"{T}fromColumn: {origem}", f"{T}toColumn: {destino}", ""]
    (definicao / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")


# ------------------------------------------------------------------ relatório (PBIR)
AZUL = "#1F4E79"


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def campo(entidade: str, prop: str, medida: bool) -> dict:
    return {("Measure" if medida else "Column"): {"Expression": {"SourceRef": {"Entity": entidade}}, "Property": prop}}


def visual(nome, tipo, x, y, w, h, papeis=None, titulo=None, objects=None, sort=None):
    """papeis = {"Category": [(tabela, campo, é_medida)], "Y": [...]}; sort = ((tabela, campo, é_medida), "Descending")."""
    v = {"visualType": tipo}
    if papeis:
        v["query"] = {"queryState": {
            p: {"projections": [{"field": campo(*c), "queryRef": f"{c[0]}.{c[1]}"} for c in cs]} for p, cs in papeis.items()}}
        if sort:
            v["query"]["sortDefinition"] = {"sort": [{"field": campo(*sort[0]), "direction": sort[1]}], "isDefaultSort": True}
    if objects:
        v["objects"] = objects
    if titulo:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit("'" + titulo.replace("'", "''") + "'")}}]}
    v["drillFilterOtherVisuals"] = True
    return {"$schema": f"{SCHEMA}/visualContainer/2.14.0/schema.json", "name": nome,
            "position": {"x": x, "y": y, "z": 1000, "height": h, "width": w}, "visual": v}


def cabecalho(nome: str, titulo: str, subtitulo: str) -> dict:
    """Caixa de texto do topo da página (68 px de altura: com menos, aparece barra de rolagem)."""
    paragrafos = [
        {"textRuns": [{"value": titulo, "textStyle": {"fontSize": "16pt", "color": AZUL, "fontWeight": "bold"}}]},
        {"textRuns": [{"value": subtitulo + " · dados simulados, projeto de portfólio",
                       "textStyle": {"fontSize": "9pt", "color": "#5F6B7A"}}]},
    ]
    v = {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paragrafos}}]},
         "visualContainerObjects": {"background": [{"properties": {"show": lit("false")}}],
                                    "border": [{"properties": {"show": lit("false")}}]},
         "drillFilterOtherVisuals": True}
    return {"$schema": f"{SCHEMA}/visualContainer/2.14.0/schema.json", "name": nome,
            "position": {"x": 16, "y": 4, "z": 0, "height": 68, "width": 1248}, "visual": v}


def cor_por_medida(tabela: str, medida_cor: str, query_ref: str, propriedade: str = "fontColor") -> dict:
    """Formatação condicional 'valor do campo': a cor vem de uma medida que devolve '#RRGGBB'."""
    return {"values": [{"properties": {propriedade: {"solid": {"color": {"expr": campo(tabela, medida_cor, True)}}}},
                        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": query_ref}}]}


def escrever_relatorio(pasta: Path, nome_modelo: str, paginas: list[tuple[str, str, list[dict]]]) -> None:
    definicao = pasta / "definition"
    (definicao / "pages").mkdir(parents=True)
    (pasta / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{nome_modelo}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (definicao / "version.json").write_text(json.dumps(
        {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    recursos = pasta / "StaticResources" / "RegisteredResources"
    recursos.mkdir(parents=True)
    shutil.copy2(TEMA, recursos / TEMA.name)
    (definicao / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/report/3.3.0/schema.json",
        "themeCollection": {"customTheme": {"name": TEMA.name, "type": "RegisteredResources",
                                            "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"}}},
        "settings": {"useStylableVisualContainerHeader": True, "useEnhancedTooltips": False},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": TEMA.name, "path": TEMA.name, "type": "CustomTheme"}]}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    for i, (pid, exibicao, visuais) in enumerate(paginas):
        pp = definicao / "pages" / pid
        (pp / "visuals").mkdir(parents=True)
        (pp / "page.json").write_text(json.dumps({
            "$schema": f"{SCHEMA}/page/2.1.0/schema.json", "name": pid, "displayName": exibicao,
            "displayOption": "FitToPage", "height": 720, "width": 1280}, ensure_ascii=False, indent=2), encoding="utf-8")
        for z, v in enumerate(visuais):
            if v["position"]["z"]:
                v["position"]["z"] = 1000 + z * 100
            (pp / "visuals" / v["name"]).mkdir()
            (pp / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    (definicao / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p[0] for p in paginas], "activePageName": paginas[0][0]}, indent=2), encoding="utf-8")


def gerar_projeto(raiz: Path, nome: str, tabelas, parametros, relacionamentos, paginas, forcar: bool) -> None:
    pbip = raiz / f"{nome}.pbip"
    if pbip.exists() and not forcar:
        raise SystemExit(f"{pbip.name} já existe e pode ter alterações salvas no Power BI. Use --forcar para recriar (apaga essas alterações).")
    for sufixo in ("SemanticModel", "Report"):
        if (raiz / f"{nome}.{sufixo}").exists():
            shutil.rmtree(raiz / f"{nome}.{sufixo}")
    ids = Ids(nome)
    escrever_modelo(raiz / f"{nome}.SemanticModel", nome, tabelas, parametros, relacionamentos, ids)
    escrever_relatorio(raiz / f"{nome}.Report", nome, paginas)
    pbip.write_text(json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{nome}.Report"}}],
                                "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    print(f"OK: {pbip}")
