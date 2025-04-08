from sqlalchemy import Column, Integer, String, Date, Numeric, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class OrdemServico(Base):
    __tablename__ = "ordens_servico"

    id = Column(Integer, primary_key=True, index=True)
    tipo_ticket = Column(Text)
    tipo_contrato = Column(Text)
    locatario = Column(Text)
    moradores = Column(Text)
    empreendimento = Column(Text)
    unidade_metragem = Column(Text)
    data_entrada = Column(Date)
    data_saida = Column(Date)
    valor_locacao = Column(Numeric)
    responsavel = Column(Text)
    solicitante = Column(Text)
    status = Column(String, default="aberto")
    responsavel_id = Column(Text)
    data_abertura = Column(TIMESTAMP)
    data_captura = Column(TIMESTAMP)
    data_fechamento = Column(TIMESTAMP)
    sla_limite = Column(TIMESTAMP)
    sla_status = Column(String, default="dentro do prazo")