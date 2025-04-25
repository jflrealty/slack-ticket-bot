import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

query = """
CREATE TABLE IF NOT EXISTS ordens_servico (
    id SERIAL PRIMARY KEY,
    tipo_ticket TEXT,
    tipo_contrato TEXT,
    locatario TEXT,
    moradores TEXT,
    empreendimento TEXT,
    unidade_metragem TEXT,
    data_entrada DATE,
    data_saida DATE,
    valor_locacao NUMERIC,
    responsavel TEXT,
    solicitante TEXT,
    status TEXT DEFAULT 'aberto',
    responsavel_id TEXT,
    data_abertura TIMESTAMP DEFAULT NOW(),
    data_captura TIMESTAMP,
    data_fechamento TIMESTAMP,
    sla_limite TIMESTAMP,
    sla_status TEXT DEFAULT 'dentro do prazo',
    thread_ts TEXT  -- ✅ Campo novo adicionado aqui
);
"""

with engine.connect() as connection:
    connection.execute(text(query))
    print("✅ Tabela 'ordens_servico' criada ou atualizada com sucesso.")
