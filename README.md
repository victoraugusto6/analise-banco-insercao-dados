# Análise comparativa de estratégias de inserção de dados em bancos relacionais utilizando Python

Projeto desenvolvido como Trabalho de Graduação em Análise e Desenvolvimento de
Sistemas na Universidade de Taubaté (UNITAU).

O experimento compara o desempenho de estratégias de inserção de **1 milhão de
registros** no PostgreSQL e no MariaDB. O objetivo é avaliar quanto a forma de
executar a carga — linha a linha, em lotes ou por mecanismos nativos — influencia
o tempo total de uma migração de dados.

## Estratégias avaliadas

- **Individual:** um `INSERT` por registro, com uma única transação e `commit` ao final.
- **Individual com commit por registro:** um `INSERT` e um `commit` para cada registro.
- **Lote:** inserções agrupadas em lotes de 1.000, 10.000, 50.000 e 100.000 registros.
- **Carga nativa:** `COPY` no PostgreSQL e `LOAD DATA LOCAL INFILE` no MariaDB.

Cada estratégia foi executada em tabelas com e sem restrições `UNIQUE` nas
colunas `email` e `cpf`. Para cada cenário foram realizadas seis execuções
sequenciais: a primeira foi tratada como aquecimento (*warmup*) e descartada, e
as cinco restantes foram utilizadas no cálculo das médias.

## Principais resultados

Tempos médios, em segundos, para inserir 1 milhão de registros:

| SGBD | Cenário | Individual | Commit por registro | Melhor lote | Carga nativa |
| --- | --- | ---: | ---: | ---: | ---: |
| PostgreSQL | Sem `UNIQUE` | 181,04 | 2.143,25 | 30,96 (50 mil) | **13,60 (`COPY`)** |
| PostgreSQL | Com `UNIQUE` | 229,43 | 2.198,56 | 42,32 (100 mil) | **29,07 (`COPY`)** |
| MariaDB | Sem `UNIQUE` | 243,52 | 2.174,25 | 27,15 (1 mil) | **9,21 (`LOAD DATA`)** |
| MariaDB | Com `UNIQUE` | 263,34 | 2.212,12 | 36,04 (1 mil) | **17,30 (`LOAD DATA`)** |

Os resultados mostram que:

- realizar um `commit` por registro foi a alternativa mais lenta nos dois bancos;
- inserções em lote reduziram expressivamente o tempo em relação às inserções individuais;
- os mecanismos nativos apresentaram os menores tempos em todos os cenários;
- as restrições `UNIQUE` aumentaram o custo de escrita devido à manutenção dos índices;
- neste ambiente, a escolha da estratégia teve impacto maior que a escolha entre os dois SGBDs.

Sem `UNIQUE`, o `COPY` foi aproximadamente **158 vezes mais rápido** que o commit
por registro no PostgreSQL. No MariaDB, o `LOAD DATA` foi cerca de **236 vezes
mais rápido**.

> Os números representam um ambiente local e controlado, com dados sintéticos,
> ausência de concorrência e versões/configurações específicas. Portanto, não
> devem ser interpretados como uma comparação universal de desempenho entre
> PostgreSQL e MariaDB.

## Tecnologias

- Python 3.13
- PostgreSQL 16
- MariaDB 11
- Docker Compose
- `psycopg` e `PyMySQL`
- pandas e Matplotlib
- uv para gerenciamento do ambiente Python

## Como executar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) com Docker Compose
- [uv](https://docs.astral.sh/uv/)
- [Git LFS](https://git-lfs.com/), caso queira utilizar o CSV de 1 milhão de registros versionado no repositório

### 1. Instale as dependências

```bash
uv sync
```

### 2. Inicie os bancos

```bash
docker compose up -d
```

Os serviços serão disponibilizados com as credenciais definidas em
[`docker-compose.yml`](docker-compose.yml):

| Serviço | Endereço | Banco | Usuário | Senha |
| --- | --- | --- | --- | --- |
| PostgreSQL | `localhost:5432` | `postgres` | `postgres` | `postgres` |
| MariaDB | `localhost:3306` | `mariadb` | `root` | `mariadb` |

### 3. Obtenha ou gere o conjunto de dados

Para baixar o arquivo já versionado:

```bash
git lfs pull
```

Ou gere um novo CSV sintético:

```bash
uv run python -m scripts.gerar_csv 1000000
```

O arquivo será criado em `data/1000000_pessoas.csv`.

### 4. Execute os benchmarks

PostgreSQL:

```bash
uv run python -m scripts.analise_postgres 1000000_pessoas.csv
```

MariaDB:

```bash
uv run python -m scripts.analise_mariadb 1000000_pessoas.csv
```

Os arquivos brutos são gravados em `result/`. A execução completa pode levar
algumas horas, principalmente devido aos cenários com commit por registro.

### 5. Gere novos gráficos

```bash
uv run python -m scripts.gerar_grafico result/<arquivo_resultado.csv>
uv run python -m scripts.gerar_grafico result/<arquivo_resultado.csv> --otimizado
```

Os gráficos gerados são salvos em `scripts/graficos/`.

## Estrutura do projeto

```text
.
├── data/                    # conjunto de dados sintéticos
├── result/                  # resultados brutos dos benchmarks
├── scripts/
│   ├── analise_postgres.py  # benchmark do PostgreSQL
│   ├── analise_mariadb.py   # benchmark do MariaDB
│   ├── gerar_csv.py         # geração dos registros sintéticos
│   ├── gerar_grafico.py     # consolidação visual dos resultados
│   ├── ddl.py               # estruturas das tabelas
│   └── utils.py             # funções compartilhadas
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## Documentação acadêmica

- [Apresentação do trabalho](https://github.com/victoraugusto6/postgresql-mariadb-insert-benchmark/blob/main/TG/apresentacao/apresentacao%20tcc.pdf)

**Autor:** Victor Augusto Soares de Oliveira

**Orientador:** Prof. Dr. Luis Fernando de Almeida

**Instituição:** Universidade de Taubaté — 2026
