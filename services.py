from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import OrdemServico
from database import SessionLocal
import csv
import os
import io
import urllib.request
from slack_sdk import WebClient
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

client_slack = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🔧 Buscar nome do Slack
def get_nome_slack(user_id):
    try:
        user_info = client_slack.users_info(user=user_id)
        return user_info["user"]["real_name"]
    except Exception as e:
        print(f"❌ Erro ao buscar nome do usuário {user_id}: {e}")
        return user_id

# 🔧 Montar blocos do modal
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
                            for opt in ["JFL125", "JML747", "VO699", "VHOUSE", "AVNU"]],
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

# 🧾 Criar novo chamado
def criar_ordem_servico(data, thread_ts=None):
    session = SessionLocal()
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
    except Exception as e:
        print(f"❌ Erro ao criar ordem: {e}")
        session.rollback()
    finally:
        session.close()

# 📤 Exportar CSV
def enviar_relatorio(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).order_by(OrdemServico.id.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado para exportar.")
        return

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho = f"/tmp/chamados_{agora}.csv"

    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(["ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade", "Valor", "Responsável", "Solicitante", "Status", "SLA", "Histórico"])
        for c in chamados:
            writer.writerow([
                c.id,
                c.tipo_ticket,
                c.tipo_contrato,
                c.locatario,
                c.empreendimento,
                c.unidade_metragem,
                f"R$ {c.valor_locacao:.2f}" if c.valor_locacao else "",
                get_nome_slack(c.responsavel),
                get_nome_slack(c.solicitante),
                c.status,
                c.sla_status,
                c.historico_reaberturas or "–"
            ])

    response = client.conversations_open(users=user_id)
    client.files_upload_v2(
        channel=response["channel"]["id"],
        file=caminho,
        title=f"Relatório de Chamados - {agora}",
        initial_comment="📎 Aqui está seu relatório de chamados."
    )

# 📤 Exportar PDF
def exportar_pdf(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).order_by(OrdemServico.id.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado para exportar.")
        return

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho = f"/tmp/chamados_{agora}.pdf"
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4))
    estilos = getSampleStyleSheet()
    elementos = []

    # Logo
    try:
        logo_data = urllib.request.urlopen("https://raw.githubusercontent.com/jflrealty/images/main/JFL_logotipo_completo.jpg").read()
        img = Image(io.BytesIO(logo_data))
        img._restrictSize(4*inch, 1*inch)
        elementos.append(img)
        elementos.append(Spacer(1, 12))
    except Exception as e:
        print(f"❌ Erro ao carregar logo: {e}")

    # Título
    elementos.append(Paragraph(f"📋 Relatório de Chamados - {datetime.now().strftime('%d/%m/%Y')}", estilos["Heading2"]))
    elementos.append(Spacer(1, 12))

    dados = [["ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade", "Valor", "Responsável", "Status", "SLA", "Histórico"]]

    for c in chamados:
        valor = f"R$ {c.valor_locacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if c.valor_locacao else ""
        dados.append([
            c.id,
            c.tipo_ticket,
            c.tipo_contrato,
            c.locatario,
            c.empreendimento,
            c.unidade_metragem,
            valor,
            get_nome_slack(c.responsavel),
            c.status,
            "🔴" if c.sla_status == "fora do prazo" else "🟢",
            c.historico_reaberturas or "–"
        ])

    tabela = Table(dados, repeatRows=1, colWidths=[30, 50, 50, 60, 60, 50, 40, 50, 40, 20, 100])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e0e0e0")),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 8),
    ]))
    elementos.append(tabela)
    doc.build(elementos)

    response = client.conversations_open(users=user_id)
    client.files_upload_v2(
        channel=response["channel"]["id"],
        file=caminho,
        title=f"Relatório Chamados {agora}.pdf",
        initial_comment="📎 Aqui está seu relatório em PDF."
    )

# 🔥 Verificar SLA vencido
def verificar_sla_vencido():
    db = SessionLocal()
    agora = datetime.utcnow()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise"]),
        OrdemServico.sla_limite < agora,
        OrdemServico.sla_status == "dentro do prazo"
    ).all()
    for chamado in chamados:
        chamado.sla_status = "fora do prazo"
    db.commit()
    db.close()

# 🔥 Lembrar chamados vencidos
def lembrar_chamados_vencidos(client):
    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise"]),
        OrdemServico.sla_status == "fora do prazo"
    ).all()
    db.close()
    for chamado in chamados:
        try:
            client.chat_postMessage(
                channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
                thread_ts=chamado.thread_ts,
                text=f"🔔 *Lembrete:* <@{chamado.responsavel}> o chamado ID *{chamado.id}* ainda está vencido! 🚨"
            )
        except Exception as e:
            print(f"❌ Erro ao enviar lembrete: {e}")
def exibir_lista(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.solicitante == user_id
    ).order_by(
        OrdemServico.status,
        OrdemServico.data_abertura.desc()
    ).all()
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
        sla_emoji = "🔴" if c.sla_status == "fora do prazo" else "🟢"
        responsavel_nome = get_nome_slack(c.responsavel)
        linha = f"{sla_emoji} ID {c.id} | {c.empreendimento} | {c.tipo_ticket} | Resp: {responsavel_nome}"
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
