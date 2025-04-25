# ✅ Atualizado: services.py

from models import OrdemServico
from database import SessionLocal
from datetime import datetime, timedelta


def criar_ordem_servico(data, thread_ts=None):
    session = SessionLocal()
    nova_os = None

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
            data_abertura=datetime.utcnow(),
            sla_limite=sla_prazo,
            sla_status="dentro do prazo",
            thread_ts=thread_ts  # Apenas se você adicionar esse campo no model
        )

        session.add(nova_os)
        session.commit()
        session.refresh(nova_os)

    except Exception as e:
        print("Erro ao salvar no banco:", e)
        session.rollback()

    finally:
        session.close()

    return nova_os
