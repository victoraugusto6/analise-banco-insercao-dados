import logging
import sys

TAMANHOS_LOTE = [1_000, 10_000, 50_000, 100_000]


def logger():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )
    return logging.getLogger(__name__)


def obter_nome_arquivo():
    if len(sys.argv) != 2:
        logger.error("Uso: python -m scripts.analise_* <nome_arquivo>")
        sys.exit(1)

    try:
        nome_arquivo = sys.argv[1]
        if not nome_arquivo.endswith(".csv"):
            raise ValueError("Arquivo informado deve ser do tipo CSV.")
        return nome_arquivo
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)


def contar_linhas(conexao) -> int:
    """Retorna o total de linhas na tabela pessoas."""
    with conexao.cursor() as cur:
        cur.execute("SELECT count(*) FROM pessoas;")
        (n,) = cur.fetchone()
        return int(n)


def carregar_linhas_csv(caminho_arquivo_csv):
    """
    Pré-carrega as tuplas do CSV em memória para:
    - não misturar parsing/leitura do CSV com custo do banco (no INSERT/LOTE)
    - garantir que cenários usem exatamente o mesmo dataset
    """
    import csv

    linhas = []
    try:
        with open(caminho_arquivo_csv, newline="", encoding="utf-8") as f:
            leitor = csv.DictReader(f, delimiter=";")
            for row in leitor:
                linhas.append(
                    (
                        row["nome"],
                        row["email"],
                        row["cpf"],
                        row["data_nascimento"],
                        row["cidade"],
                        row["estado"],
                        row["endereco"],
                        row["salario"],
                    )
                )
        return linhas
    except FileNotFoundError:
        logger.error(f"Arquivo {caminho_arquivo_csv} não encontrado.")
        sys.exit(1)
