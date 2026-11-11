"""
Simula o sistema de origem "depositando" arquivos na pasta entrada/.

Uso:
    python src/simular_chegada.py --meses 18   # entrega os cadastros + os 18 primeiros meses
    python src/simular_chegada.py              # entrega o próximo mês ainda não entregue
    python src/simular_chegada.py --tudo       # entrega tudo o que falta

Serve para demonstrar a carga INCREMENTAL: rode o pipeline, entregue mais um mês,
rode o pipeline de novo e veja só o mês novo ser processado.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FONTE = RAIZ / "dados_fonte"
ENTRADA = RAIZ / "entrada"
JA_ENTREGUES = [ENTRADA, RAIZ / "processados", RAIZ / "rejeitados"]
CADASTROS = ["cadastro_alimentadores.csv", "cadastro_clientes.csv"]


def main() -> None:
    parser = argparse.ArgumentParser()
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--meses", type=int, default=1, help="quantos meses entregar (padrão 1)")
    grupo.add_argument("--tudo", action="store_true", help="entrega todos os meses restantes")
    args = parser.parse_args()

    if not FONTE.exists():
        raise SystemExit("Pasta dados_fonte/ não existe. Rode antes: python src/gerar_dados.py")
    ENTRADA.mkdir(exist_ok=True)
    entregues = {p.name for pasta in JA_ENTREGUES if pasta.exists() for p in pasta.glob("*.csv")}

    copiados = []
    for nome in CADASTROS:
        if nome not in entregues:
            shutil.copy2(FONTE / nome, ENTRADA / nome)
            copiados.append(nome)

    meses = sorted({m.group(1) for p in FONTE.glob("leituras_*.csv") if (m := re.search(r"(\d{4}-\d{2})", p.name))})
    faltam = [m for m in meses if f"leituras_{m}.csv" not in entregues]
    selecionados = faltam if args.tudo else faltam[: args.meses]
    for mes in selecionados:
        for prefixo in ("injecao", "leituras", "inspecoes"):
            nome = f"{prefixo}_{mes}.csv"
            shutil.copy2(FONTE / nome, ENTRADA / nome)
            copiados.append(nome)

    if not copiados:
        print("Nada a entregar: todos os meses já chegaram.")
    else:
        print(f"Entregues {len(copiados)} arquivos em entrada/ (meses: {', '.join(selecionados) or 'nenhum'})")
        print(f"Restam {len(faltam) - len(selecionados)} meses no sistema de origem.")


if __name__ == "__main__":
    main()
