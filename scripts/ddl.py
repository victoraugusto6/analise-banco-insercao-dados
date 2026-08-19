DDL_POSTGRES_SEM_UNIQUE = """
DROP TABLE IF EXISTS pessoas;
CREATE TABLE pessoas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    cpf CHAR(11) NOT NULL,
    data_nascimento DATE NOT NULL,
    cidade TEXT NOT NULL,
    estado CHAR(2) NOT NULL,
    endereco TEXT NOT NULL,
    salario NUMERIC(10,2) NOT NULL
);
"""

DDL_POSTGRES_COM_UNIQUE = """
DROP TABLE IF EXISTS pessoas;
CREATE TABLE pessoas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    cpf CHAR(11) NOT NULL UNIQUE,
    data_nascimento DATE NOT NULL,
    cidade TEXT NOT NULL,
    estado CHAR(2) NOT NULL,
    endereco TEXT NOT NULL,
    salario NUMERIC(10,2) NOT NULL
);
"""


DDL_MARIADB_SEM_UNIQUE = """
DROP TABLE IF EXISTS pessoas;
CREATE TABLE pessoas (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    cpf CHAR(11) NOT NULL,
    data_nascimento DATE NOT NULL,
    cidade TEXT NOT NULL,
    estado CHAR(2) NOT NULL,
    endereco TEXT NOT NULL,
    salario DECIMAL(10,2) NOT NULL
) ENGINE=InnoDB;
"""

DDL_MARIADB_COM_UNIQUE = """
DROP TABLE IF EXISTS pessoas;
CREATE TABLE pessoas (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    cpf CHAR(11) NOT NULL,
    data_nascimento DATE NOT NULL,
    cidade TEXT NOT NULL,
    estado CHAR(2) NOT NULL,
    endereco TEXT NOT NULL,
    salario DECIMAL(10,2) NOT NULL,
    UNIQUE KEY uq_email (email(255)),
    UNIQUE KEY uq_cpf (cpf)
) ENGINE=InnoDB;
"""

SQL_INSERT = """
    INSERT INTO pessoas
    (nome, email, cpf, data_nascimento, cidade, estado, endereco, salario)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""
