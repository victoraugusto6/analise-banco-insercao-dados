from datetime import datetime
from pathlib import Path
from time import perf_counter

import pymysql

from scripts.ddl import DDL_MARIADB_COM_UNIQUE, DDL_MARIADB_SEM_UNIQUE, SQL_INSERT
from scripts.utils import (
    TAMANHOS_LOTE,
    carregar_linhas_csv,
    contar_linhas,
    logger,
    obter_nome_arquivo,
)

logger = logger()

conexao = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="mariadb",
    database="mariadb",
    autocommit=False,
    local_infile=True,
)


ARQUIVO_CSV = f"data/{obter_nome_arquivo()}"
ARQUIVO_SAIDA = (
    f"result/{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    f"_resultados_benchmark_insercao_mariadb.csv"
)


def recriar_tabela(ddl: str):
    with conexao.cursor() as cur:
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            cur.execute(stmt)
    conexao.commit()


def listar_indices_pessoas():
    with conexao.cursor() as cur:
        cur.execute("SHOW INDEX FROM pessoas;")
        rows = cur.fetchall()

    indices = {}
    for r in rows:
        key_name = r[2]
        non_unique = r[1]
        col_name = r[4]
        indices.setdefault(key_name, {"non_unique": non_unique, "cols": []})
        indices[key_name]["cols"].append(col_name)

    resultado = []
    for k, v in sorted(indices.items()):
        uniq = "UNIQUE" if v["non_unique"] == 0 else "NON_UNIQUE"
        cols = ",".join(v["cols"])
        resultado.append((k, f"{uniq} ({cols})"))
    return resultado


def obter_status_global_int(nome_variavel: str):
    with conexao.cursor() as cur:
        cur.execute("SHOW GLOBAL STATUS LIKE %s;", (nome_variavel,))
        row = cur.fetchone()

    if not row:
        return None

    try:
        return int(row[1])
    except Exception:
        return None


def diferenca_redo_bytes(antes, depois):
    if antes is None or depois is None:
        return None
    return max(0, depois - antes)


def medir_tempo_e_redo(funcao):
    antes = obter_status_global_int("Innodb_os_log_written")

    inicio = perf_counter()
    funcao()
    fim = perf_counter()

    depois = obter_status_global_int("Innodb_os_log_written")
    redo = diferenca_redo_bytes(antes, depois)

    return (fim - inicio), redo


def inserir_individual(linhas):
    def _exec():
        with conexao.cursor() as cur:
            for linha in linhas:
                cur.execute(SQL_INSERT, linha)
        conexao.commit()

    return medir_tempo_e_redo(_exec)


def inserir_individual_autocommit(linhas):
    def _exec():
        with conexao.cursor() as cur:
            for linha in linhas:
                cur.execute(SQL_INSERT, linha)
                conexao.commit()

    return medir_tempo_e_redo(_exec)


def inserir_em_lote(linhas, tamanho_lote=1000):
    def _exec():
        with conexao.cursor() as cur:
            lote = []
            for linha in linhas:
                lote.append(linha)
                if len(lote) == tamanho_lote:
                    cur.executemany(SQL_INSERT, lote)
                    conexao.commit()
                    lote.clear()

            if lote:
                cur.executemany(SQL_INSERT, lote)
                conexao.commit()
                lote.clear()

    return medir_tempo_e_redo(_exec)


def inserir_com_load_data(arquivo_csv: str):
    sql = r"""
    LOAD DATA LOCAL INFILE %s
    INTO TABLE pessoas
    FIELDS TERMINATED BY ';'
    LINES TERMINATED BY '\n'
    IGNORE 1 LINES
    (nome, email, cpf, data_nascimento, cidade, estado, endereco, salario);
    """

    def _exec():
        with conexao.cursor() as cur:
            cur.execute(sql, (arquivo_csv,))
        conexao.commit()

    return medir_tempo_e_redo(_exec)


def escrever_cabecalho_se_precisar(caminho: str):
    path = Path(caminho)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists() or path.stat().st_size == 0:
        with open(caminho, "w", encoding="utf-8", newline="") as f:
            f.write(
                "timestamp,sgbd,rodada,metodo,tamanho_lote,execucao,"
                "warmup,tempo_s,linhas_inseridas,linhas_por_s,redo_bytes\n"
            )


def registrar_resultado(
    caminho,
    rodada,
    metodo,
    tamanho_lote,
    execucao,
    warmup,
    tempo_s,
    linhas_inseridas,
    redo_bytes,
):
    linhas_por_s = linhas_inseridas / tempo_s if tempo_s > 0 else 0.0
    ts = datetime.now().isoformat(timespec="seconds")
    tamanho_lote_str = tamanho_lote if tamanho_lote is not None else ""
    redo_str = "" if redo_bytes is None else str(redo_bytes)

    with open(caminho, "a", encoding="utf-8", newline="") as f:
        f.write(
            f"{ts},mariadb,{rodada},{metodo},{tamanho_lote_str},{execucao},"
            f"{warmup},{tempo_s:.6f},{linhas_inseridas},{linhas_por_s:.2f},{redo_str}\n"
        )


def executar_cenario(
    rodada_nome,
    ddl,
    nome_metodo,
    funcao_execucao,
    tamanho_lote=None,
    repeticoes=6,
    descartar_primeira=True,
):
    for i in range(1, repeticoes + 1):
        recriar_tabela(ddl)

        tempo_s, redo_bytes = funcao_execucao()
        linhas_inseridas = contar_linhas(conexao)

        warmup = descartar_primeira and i == 1

        registrar_resultado(
            ARQUIVO_SAIDA,
            rodada_nome,
            nome_metodo,
            tamanho_lote,
            i,
            warmup,
            tempo_s,
            linhas_inseridas,
            redo_bytes,
        )

        logger.info(
            f"[{rodada_nome}] {nome_metodo}"
            + (f"(lote={tamanho_lote})" if tamanho_lote else "")
            + f" execução {i}: {tempo_s:.2f}s | linhas={linhas_inseridas}"
            + (f" | redo_bytes={redo_bytes}" if redo_bytes else "")
        )


if __name__ == "__main__":
    escrever_cabecalho_se_precisar(ARQUIVO_SAIDA)

    if not Path(ARQUIVO_CSV).exists():
        raise SystemExit(f"Arquivo não encontrado: {ARQUIVO_CSV}")

    linhas = carregar_linhas_csv(ARQUIVO_CSV)
    logger.info(f"Dataset carregado: {len(linhas)} linhas")
    logger.info(f"Resultados salvos em: {ARQUIVO_SAIDA}")

    rodadas = [
        ("sem_unique", DDL_MARIADB_SEM_UNIQUE),
        ("com_unique", DDL_MARIADB_COM_UNIQUE),
    ]

    for rodada_nome, ddl in rodadas:
        recriar_tabela(ddl)

        executar_cenario(
            rodada_nome,
            ddl,
            "individual",
            lambda: inserir_individual(linhas),
        )

        executar_cenario(
            rodada_nome,
            ddl,
            "individual_autocommit",
            lambda: inserir_individual_autocommit(linhas),
        )

        for tamanho_lote in TAMANHOS_LOTE:
            executar_cenario(
                rodada_nome,
                ddl,
                "lote",
                lambda tl=tamanho_lote: inserir_em_lote(linhas, tl),
                tamanho_lote=tamanho_lote,
            )

        executar_cenario(
            rodada_nome,
            ddl,
            "load_data",
            lambda: inserir_com_load_data(ARQUIVO_CSV),
        )

    logger.info("Execução finalizada.")
