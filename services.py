from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import OrdemServico
from database import SessionLocal
import csv

# 🔧 Função para montar os blocos do modal
def montar_blocos_modal():
    return [
        {
            "type": "input",
            "block_id": "tipo_ticket",
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha"},
                "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]],
            },
            "label": {"type": "plain_text", "text": "Tipo de Ticket"}
        },
        {
            "type": "input",
            "block_id": "tipo_contrato",
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha"},
                "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["Short Stay", "Temporada", "Long Stay", "Comodato"]],
            },
            "label": {"type": "plain_text", "text": "Tipo de Contrato"}
        },
        {
            "type": "input",
            "block_id": "locatario",
            "element": {"type": "plain_text_input", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Locatário"}
        },
        {
            "type": "input",
            "block_id": "moradores",
            "element": {"type": "plain_text_input", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Moradores"}
        },
        {
            "type": "input",
            "block_id": "empreendimento",
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha"},
                "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                            for opt in ["JFL125", "JML747", "VO699", "VHOUSE", "AVNU"]]
            },
            "label": {"type": "plain_text", "text": "Empreendimento"}
        },
        {
            "type": "input",
            "block_id": "unidade_metragem",
            "element": {"type": "plain_text_input", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Unidade e Metragem"}
        },
        {
            "type": "input",
            "block_id": "data_entrada",
            "element": {"type": "datepicker", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Data de Entrada"}
        },
        {
            "type": "input",
            "block_id": "data_saida",
            "element": {"type": "datepicker", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Data de Saída"}
        },
        {
            "type": "input",
            "block_id": "valor_locacao",
            "element": {"type": "plain_text_input", "action_id": "value"},
            "label": {"type": "plain_text", "text": "Valor da Locação"}
        },
        {
            "type": "input",
            "block_id": "responsavel",
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "Escolha um responsável"},
                "options": [
                    {"text": {"type": "plain_text", "text": "Rigol"}, "value": "U06TZRECVC4"},
                    {"text": {"type": "plain_text", "text": "Marcela"}, "value": "U06U3RC11G9"},
                    {"text": {"type": "plain_text", "text": "Victor"}, "value": "U07B2130TKQ"},
                    {"text": {"type": "plain_text", "text": "Gabriel"}, "value": "U06TNKNRZHT"},
                    {"text": {"type": "plain_text", "text": "Douglas"}, "value": "U08ANPS7V7Y"},
                    {"text": {"type": "plain_text", "text": "Luciana"}, "value": "U06TAJU7C95"},
                    {"text": {"type": "plain_text", "text": "Caroline"}, "value": "U08DRE18RR7"}
                ]
            },
            "label": {"type": "plain_text", "text": "Responsável"}
        }
    ]

# 🧾 Criação da Ordem de Serviço
def criar_ordem_servico(data, thread_ts=None):
    session = SessionLocal()
    nova_os = None
    try:
        sla_prazo = datetime.utcnow() + timedelta(hours=24)

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
            status="aberto",
            data_abertura=datetime.utcnow(),
            sla_limite=sla_prazo,
            sla_status="dentro do prazo",
            thread_ts=thread_ts
        )

        session.add(nova_os)
        session.commit()
        session.refresh(nova_os)

    except Exception as e:
        print("❌ Erro ao salvar no banco:", e)
        session.rollback()

    finally:
        session.close()

    return nova_os

# 📤 Exporta CSV com todos os chamados e envia por DM
def enviar_relatorio(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).order_by(OrdemServico.id.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="❌ Nenhum chamado encontrado para exportar."
        )
        return

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho = f"/tmp/chamados_{agora}.csv"

    with open(caminho, mode="w", newline="", encoding="utf-8") as arquivo_csv:
        writer = csv.writer(arquivo_csv)
        writer.writerow([
            "ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade",
            "Valor", "Responsável", "Solicitante", "Status", "SLA"
        ])
        for c in chamados:
            writer.writerow([
                c.id,
                c.tipo_ticket,
                c.tipo_contrato,
                c.locatario,
                c.empreendimento,
                c.unidade_metragem,
                f"R$ {c.valor_locacao:.2f}" if c.valor_locacao else "",
                c.responsavel,
                c.solicitante,
                c.status,
                c.sla_status
            ])

    response = client.conversations_open(users=user_id)
    channel_id = response["channel"]["id"]

    client.files_upload_v2(
        channel=channel_id,
        file=caminho,
        title=f"Relatório de Chamados - {agora}",
        initial_comment="📎 Aqui está seu relatório de chamados."
    )

# 📋 Lista os chamados do usuário no Slack
def exibir_lista(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(OrdemServico.solicitante == user_id).order_by(
        OrdemServico.status, OrdemServico.data_abertura.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(
            channel=user_id,
            user=user_id,
            text="✅ Você não possui chamados registrados."
        )
        return

    abertos, em_analise, fechados = [], [], []

    for c in chamados:
        linha = f"• ID {c.id} | {c.empreendimento} | {c.tipo_ticket} | Resp: <@{c.responsavel}>"
        if c.status == "aberto":
            abertos.append(linha)
        elif c.status == "em análise":
            em_analise.append(linha)
        elif c.status == "fechado":
            fechados.append(linha)

    texto = "📋 *Seus Chamados:*\n"
    if em_analise:
        texto += "\n🟡 *Em Análise:*\n" + "\n".join(em_analise)
    if abertos:
        texto += "\n🟢 *Abertos:*\n" + "\n".join(abertos)
    if fechados:
        texto += "\n⚪️ *Fechados:*\n" + "\n".join(fechados)

    client.chat_postEphemeral(
        channel=user_id,
        user=user_id,
        text=texto
    )

def formatar_mensagem_chamado(data, user_id):
    valor_formatado = f"R$ {data['valor_locacao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (
        "📄 *Detalhes do Chamado:*\n"
        f"• *Tipo de Ticket:* {data['tipo_ticket']}\n"
        f"• *Tipo de Contrato:* {data['tipo_contrato']}\n"
        f"• *Locatário:* {data['locatario']}\n"
        f"• *Moradores:* {data['moradores']}\n"
        f"• *Empreendimento:* {data['empreendimento']}\n"
        f"• *Unidade e Metragem:* {data['unidade_metragem']}\n"
        f"• *Data de Entrada:* {data['data_entrada'].strftime('%Y-%m-%d') if data['data_entrada'] else '–'}\n"
        f"• *Data de Saída:* {data['data_saida'].strftime('%Y-%m-%d') if data['data_saida'] else '–'}\n"
        f"• *Valor da Locação:* {valor_formatado}\n"
        f"• *Responsável:* <@{data['responsavel']}>\n"
        f"• *Solicitante:* <@{user_id}>"
    )
