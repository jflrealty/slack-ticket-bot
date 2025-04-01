from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class OrdemServico(Base):
    __tablename__ = "ordens_servico"

    id = Column(Integer, primary_key=True)
    tipo_ticket = Column(String)
    tipo_contrato = Column(String)
    locatario = Column(String)
    moradores = Column(Text)
    empreendimento = Column(String)
    unidade_metragem = Column(String)
    data_entrada = Column(Date)
    data_saida = Column(Date)
    valor_locacao = Column(Numeric)
    responsavel = Column(String)
    solicitante = Column(String)

    status = Column(String, default="aberto")
    responsavel_id = Column(String)

    data_abertura = Column(DateTime, default=datetime.utcnow)
    data_captura = Column(DateTime)
    data_fechamento = Column(DateTime)

    sla_limite = Column(DateTime)
    sla_status = Column(String, default="dentro do prazo")