from models import OrdemServico
from database import SessionLocal
from datetime import datetime, timedelta

def criar_ordem_servico(data):
    session = SessionLocal()

    try:
        sla_prazo = datetime.utcnow() + timedelta(hours=24)  # SLA padrão 24h

        nova_os = OrdemServico(
            tipo_ticket=data["tipo_ticket"],
            tipo_contrato=data["tipo_contrato"],
            locatario=data["locatario"],
            moradores=data["moradores"],
            empreendimento=data["empreendimento"],
            unidade_metragem=data["unidade_metragem"],
            data_entrada=data["data_entrada"],
            data_saida=data["data_saida"],
            valor_locacao=data["valor_locacao"],
            responsavel=data["responsavel"],
            solicitante=data["solicitante"],
            sla_limite=sla_prazo
        )

        session.add(nova_os)
        session.commit()

    except Exception as e:
        print("Erro ao salvar no banco:", e)
        session.rollback()

    finally:
        session.close()