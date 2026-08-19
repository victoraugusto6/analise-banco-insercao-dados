from datetime import datetime
from pathlib import Path
from time import perf_counter

import psycopg

from scripts.ddl import DDL_POSTGRES_COM_UNIQUE, DDL_POSTGRES_SEM_UNIQUE, SQL_INSERT
from scripts.utils import (
    TAMANHOS_LOTE,
    carregar_linhas_csv,
    contar_linhas,
    logger,
    obter_nome_arquivo,
)

logger = logger()


conexao = psycopg.connect(
    "host=localhost dbname=postgres user=postgres password=postgres"
)


ARQUIVO_CSV = f"data/{obter_nome_arquivo()}"
ARQUIVO_SAIDA = (
    f"result/{datetime.now().strftime('%Y-%m-%d-%H-%M')}"
    f"_resultados_benchmark_insercao_postgres.csv"
)


def recriar_tabela(ddl: str):
    """
    Recria a tabela pessoas (DROP/CREATE) antes de cada execução,
    evitando influência de dados de rodadas anteriores.
    """
    with conexao.cursor() as cur:
        cur.execute(ddl)
    conexao.commit()


def listar_indices_pessoas() -> list[tuple[str, str]]:
    """
    Lista índices existentes na tabela pessoas para validar as diferenças
    entre sem unique e com unique.
    """
    sql = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = 'pessoas'
        ORDER BY indexname;
    """
    with conexao.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def obter_lsn_wal() -> str:
    """
    Obtém o LSN (Log Sequence Number) atual do WAL.
    Representa a posição corrente no fluxo de WAL do PostgreSQL.
    """
    with conexao.cursor() as cur:
        cur.execute("SELECT pg_current_wal_lsn();")
        (lsn,) = cur.fetchone()
        return lsn


def diferenca_wal_bytes(lsn_antes: str, lsn_depois: str) -> int:
    """Calcula quantos bytes de WAL foram gerados entre dois LSNs."""
    with conexao.cursor() as cur:
        cur.execute("SELECT pg_wal_lsn_diff(%s, %s);", (lsn_depois, lsn_antes))
        (diff,) = cur.fetchone()
        return int(diff)


def medir_tempo_e_wal(funcao):
    lsn_antes = obter_lsn_wal()

    inicio = perf_counter()
    funcao()
    fim = perf_counter()

    lsn_depois = obter_lsn_wal()

    return (fim - inicio), diferenca_wal_bytes(lsn_antes, lsn_depois)


def inserir_individual(linhas):
    """
    Insere um registro por comando INSERT (uma instrução por linha).
    Todas as instruções são executadas dentro de uma única transação
    (autocommit desabilitado), com commit único ao final.
    """

    def _exec():
        with conexao.cursor() as cur:
            for linha in linhas:
                cur.execute(SQL_INSERT, linha)

            conexao.commit()

    return medir_tempo_e_wal(_exec)


def inserir_individual_autocommit(linhas):
    """
    Insere um registro por comando INSERT (uma instrução por linha).
    Cada instrução é executada em uma transação separada (autocommit ativado).
    """

    def _exec():
        with conexao.cursor() as cur:
            for linha in linhas:
                cur.execute(SQL_INSERT, linha)
                conexao.commit()

    return medir_tempo_e_wal(_exec)


def inserir_em_lote(linhas, tamanho_lote=1000):
    """
    Insere em lotes usando executemany (batch do lado do cliente),
    com commit ao final de cada lote.
    """

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

    return medir_tempo_e_wal(_exec)


def inserir_com_copy_memoria(linhas):
    """
    COPY alimentado por um CSV gerado em memória a partir do dataset já carregado.
    """
    sql_copy = """
        COPY pessoas
        (nome, email, cpf, data_nascimento, cidade, estado, endereco, salario)
        FROM STDIN WITH (FORMAT csv, DELIMITER ';')
    """

    import csv
    import io

    def _exec():
        with conexao.cursor() as cur:
            # Gera CSV em memória
            buffer = io.StringIO()
            escritor = csv.writer(
                buffer, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_MINIMAL
            )

            for linha in linhas:
                escritor.writerow(linha)

            buffer.seek(0)

            # Envia em blocos para não ficar chamando write() toda hora
            with cur.copy(sql_copy) as copy:
                while True:
                    bloco = buffer.read(8 * 1024 * 1024)  # 8 MB
                    if not bloco:
                        break
                    copy.write(bloco)

            conexao.commit()

    return medir_tempo_e_wal(_exec)


def escrever_cabecalho_se_precisar(caminho: str):
    """Cria o CSV com cabeçalho se ele não existir ou estiver vazio."""
    path = Path(caminho)
    path.parent.mkdir(parents=True, exist_ok=True)

    precisa_header = not path.exists() or path.stat().st_size == 0
    if precisa_header:
        with open(caminho, "w", encoding="utf-8", newline="") as f:
            f.write(
                "timestamp,sgbd,rodada,metodo,tamanho_lote,execucao,warmup,"
                "tempo_s,linhas_inseridas,linhas_por_s,wal_bytes\n"
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
    wal_bytes,
):
    """
    Registra uma linha de resultado no CSV.
    warmup=True tipicamente para execucao=1 de cada cenário.
    """
    linhas_por_s = linhas_inseridas / tempo_s if tempo_s > 0 else 0.0
    ts = datetime.now().isoformat(timespec="seconds")

    tamanho_lote_str = tamanho_lote if tamanho_lote is not None else ""

    with open(caminho, "a", encoding="utf-8", newline="") as f:
        f.write(
            f"{ts},postgres,{rodada},{metodo},{tamanho_lote_str},{execucao},"
            f"{warmup},{tempo_s:.6f},{linhas_inseridas},{linhas_por_s:.2f},{wal_bytes}\n"
        )


def executar_cenario(
    rodada_nome: str,
    ddl: str,
    nome_metodo: str,
    funcao_execucao,
    *,
    tamanho_lote=None,
    repeticoes=6,
    descartar_primeira=True,
):
    """
    Executa um cenário repetidas vezes, recriando a tabela a cada execução.
    Se descartar_primeira=True, a execução 1 é marcada como warmup=True.
    """
    for i in range(1, repeticoes + 1):
        recriar_tabela(ddl)

        tempo_s, wal_bytes = funcao_execucao()
        linhas_inseridas = contar_linhas(conexao)

        warmup = bool(descartar_primeira and i == 1)

        registrar_resultado(
            ARQUIVO_SAIDA,
            rodada_nome,
            nome_metodo,
            tamanho_lote,
            i,
            warmup,
            tempo_s,
            linhas_inseridas,
            wal_bytes,
        )

        logger.info(
            f"[{rodada_nome}] {nome_metodo}"
            + (f"(lote={tamanho_lote})" if tamanho_lote else "")
            + f" execução {i}: {tempo_s:.2f}s | warmup={warmup} | linhas={linhas_inseridas} | wal_bytes={wal_bytes}"
        )

    if descartar_primeira:
        logger.info(
            f"[{rodada_nome}] Obs.: na análise, filtre warmup=True para remover a execução 1 de {nome_metodo}."
        )


if __name__ == "__main__":
    escrever_cabecalho_se_precisar(ARQUIVO_SAIDA)

    linhas = carregar_linhas_csv(ARQUIVO_CSV)
    logger.info(f"Dataset carregado: {len(linhas)} linhas")
    logger.info(f"Resultados salvos em: {ARQUIVO_SAIDA}")

    rodadas = [
        ("sem_unique", DDL_POSTGRES_SEM_UNIQUE),
        ("com_unique", DDL_POSTGRES_COM_UNIQUE),
    ]

    for rodada_nome, ddl in rodadas:
        recriar_tabela(ddl)
        indices = listar_indices_pessoas()
        logger.info(f"[{rodada_nome}] Índices detectados: {len(indices)}")
        for nome, definicao in indices:
            logger.info(f"[{rodada_nome}] {nome} | {definicao}")

        # Individual
        executar_cenario(
            rodada_nome,
            ddl,
            "individual",
            lambda: inserir_individual(linhas),
            repeticoes=6,
            descartar_primeira=True,
        )

        # Individual com autocommit
        executar_cenario(
            rodada_nome,
            ddl,
            "individual_autocommit",
            lambda: inserir_individual_autocommit(linhas),
            repeticoes=6,
            descartar_primeira=True,
        )

        # Lote
        for tamanho_lote in TAMANHOS_LOTE:
            executar_cenario(
                rodada_nome,
                ddl,
                "lote",
                lambda tl=tamanho_lote: inserir_em_lote(linhas, tamanho_lote=tl),
                tamanho_lote=tamanho_lote,
                repeticoes=6,
                descartar_primeira=True,
            )

        # COPY
        executar_cenario(
            rodada_nome,
            ddl,
            "copy",
            lambda: inserir_com_copy_memoria(linhas),
            repeticoes=6,
            descartar_primeira=True,
        )

    logger.info("Execução finalizada.")
