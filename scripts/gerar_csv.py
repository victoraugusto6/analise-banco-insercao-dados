import csv
import logging
import sys
from pathlib import Path
from random import randint


def gerar_cpf_valido():
    # 9 dígitos base
    base = [randint(0, 9) for _ in range(9)]

    # 1º dígito verificador
    soma = sum((10 - i) * n for i, n in enumerate(base))
    d1 = (soma * 10 % 11) % 10

    # 2º dígito verificador
    soma = sum((11 - i) * n for i, n in enumerate(base + [d1]))
    d2 = (soma * 10 % 11) % 10

    cpf = "".join(map(str, base + [d1, d2]))
    return cpf


def gerar_cpfs_unicos(qtd):
    cpfs = set()
    while len(cpfs) < qtd:
        cpfs.add(gerar_cpf_valido())
    return list(cpfs)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def obter_quantidade_linhas():
    if len(sys.argv) != 2:
        logger.error("Uso: python -m scripts.gerar_csv <quantidade_linhas>")
        sys.exit(1)

    try:
        qtd = int(sys.argv[1])
        if qtd <= 0:
            raise ValueError
        return qtd
    except ValueError:
        logger.error("A quantidade deve ser um número inteiro positivo.")
        sys.exit(1)


ROWS = obter_quantidade_linhas()
OUTPUT = f"data/{ROWS}_pessoas.csv"

if not Path(OUTPUT).parent.exists():
    Path(OUTPUT).parent.mkdir(parents=True)

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(
        [
            "nome",
            "email",
            "cpf",
            "data_nascimento",
            "cidade",
            "estado",
            "endereco",
            "salario",
        ]
    )

    lista_cpfs = gerar_cpfs_unicos(ROWS)

    for i, _ in enumerate(range(ROWS), start=1):
        ano_nascimento_choices = randint(1960, 2005)
        mes_nascimento_choices = randint(1, 12)
        dia_nascimento_choices = randint(1, 28)

        writer.writerow(
            [
                f"Nome gerado para criação de CSV - {i}",
                f"email_{i}@example.com",
                lista_cpfs[i - 1],
                f"{ano_nascimento_choices}-{mes_nascimento_choices:02d}-{dia_nascimento_choices:02d}",
                "Taubaté",
                "SP",
                f"Rua Exemplo, {i}, Bairro Exemplo - Complemento {i} próximo Universidade de Taubaté",
                f"{randint(1000, 10000)}.{randint(0, 99):02d}",
            ]
        )

print(f"CSV gerado com {ROWS} registros")
