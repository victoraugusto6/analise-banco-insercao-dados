import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


ESTRATEGIAS_OTIMIZADAS = [
    "Lote 1.000",
    "Lote 10.000",
    "Lote 50.000",
    "Lote 100.000",
    "COPY",
    "LOAD DATA",
]


def obter_argumentos():
    parser = argparse.ArgumentParser(
        description="Gera gráfico de tempo médio por estratégia de inserção."
    )
    parser.add_argument("nome_arquivo", help="Arquivo CSV com os resultados.")
    parser.add_argument(
        "--otimizado",
        action="store_true",
        help="Plota somente as estratégias otimizadas.",
    )

    args = parser.parse_args()
    arquivo_csv = Path(args.nome_arquivo)

    if arquivo_csv.suffix.lower() != ".csv":
        parser.error("Arquivo informado deve ser do tipo CSV.")

    return arquivo_csv, args.otimizado


arquivo_csv, usar_otimizado = obter_argumentos()
df = pd.read_csv(arquivo_csv)

# Remove warmup
df = df.loc[~df["warmup"]].copy()
df["rodada"] = df["rodada"].replace(
    {
        "com_unique": "Com UNIQUE",
        "sem_unique": "Sem UNIQUE",
    }
)


def nome_estrategia(row):
    metodo = str(row["metodo"]).lower()

    if metodo == "individual":
        return "Individual"
    if metodo == "individual_autocommit":
        return "Individual + commit por registro"
    if metodo == "lote":
        return f"Lote {int(row['tamanho_lote']):,}".replace(",", ".")
    if metodo == "load_data":
        return "LOAD DATA"
    if metodo == "copy":
        sgbd = str(row.get("sgbd", "")).lower()
        if sgbd in {"mariadb", "mysql"}:
            return "LOAD DATA"
        return "COPY"
    return row["metodo"]


df["estrategia"] = df.apply(nome_estrategia, axis=1)

ordem = [
    "Individual",
    "Individual + commit por registro",
    "Lote 1.000",
    "Lote 10.000",
    "Lote 50.000",
    "Lote 100.000",
    "COPY",
    "LOAD DATA",
]

if usar_otimizado:
    df = df[df["estrategia"].isin(ESTRATEGIAS_OTIMIZADAS)].copy()
    ordem = ESTRATEGIAS_OTIMIZADAS

media = (
    df.groupby(["rodada", "estrategia"])["tempo_s"]
    .mean()
    .reset_index()
)

pivot = media.pivot(index="estrategia", columns="rodada", values="tempo_s")
ordem_presentes = [estrategia for estrategia in ordem if estrategia in pivot.index]
outras_estrategias = [estrategia for estrategia in pivot.index if estrategia not in ordem]
pivot = pivot.loc[ordem_presentes + outras_estrategias]

ax = pivot.plot(kind="bar", figsize=(12, 6))
ax.grid(axis="y", linestyle="--", alpha=0.4)
ax.set_axisbelow(True)

# plt.title("Tempo médio de inserção no PostgreSQL")
plt.xlabel("Estratégia de inserção")
plt.ylabel("Tempo médio (s)")
plt.xticks(rotation=35, ha="right")
plt.legend(title="Cenário")
plt.tight_layout()

pasta_graficos = Path(__file__).parent / "graficos"
pasta_graficos.mkdir(parents=True, exist_ok=True)

sufixo = "tempo_medio_otimizado" if usar_otimizado else "tempo_medio_geral"
arquivo_grafico = pasta_graficos / f"{arquivo_csv.stem}_{sufixo}.png"
plt.savefig(arquivo_grafico, dpi=300)
print(f"Gráfico salvo em: {arquivo_grafico}")
plt.show()
