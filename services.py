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
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

client_slack = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🆔 Buscar nome real no Slack
def get_nome_slack(user_id):
    try:
        user_info = client_slack.users_info(user=user_id)
        return user_info["user"]["real_name"]
    except Exception as e:
        print(f"❌ Erro ao buscar nome do usuário {user_id}: {e}")
        return user_id

# 🔥 Ajustar nomes no histórico
def ajustar_historico(texto):
    if not texto:
        return "–"
    texto = texto.replace("<@", "").replace(">", "")
    for palavra in texto.split():
        if palavra.startswith("U0") or palavra.startswith("U"):
            nome = get_nome_slack(palavra)
            texto = texto.replace(palavra, nome)
    return texto

# 📋 Buscar chamados com filtro de datas
def buscar_chamados(data_inicio=None, data_fim=None):
    db = SessionLocal()
    query = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise", "fechado", "cancelado"])
    )
    if data_inicio:
        query = query.filter(OrdemServico.data_abertura >= data_inicio)
    if data_fim:
        query = query.filter(OrdemServico.data_abertura <= data_fim)

    chamados = query.order_by(OrdemServico.id.desc()).all()
    db.close()
    return chamados

# 📤 Exportar CSV
def enviar_relatorio(client, user_id, data_inicio=None, data_fim=None):
    chamados = buscar_chamados(data_inicio, data_fim)

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado no período.")
        return

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho = f"/tmp/chamados_{agora}.csv"

    with open(caminho, mode="w", newline="", encoding="utf-8") as arquivo_csv:
        writer = csv.writer(arquivo_csv)
        writer.writerow([
            "ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade",
            "Valor", "Responsável", "Solicitante", "Status", "SLA", "Histórico", "Motivo Cancelamento"
        ])
        for c in chamados:
            historico = ajustar_historico(c.historico_reaberturas)
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
                "🟢" if c.sla_status == "dentro do prazo" else "🔴",
                historico,
                c.motivo_cancelamento or "–"
            ])

    response = client.conversations_open(users=user_id)
    channel_id = response["channel"]["id"]
    client.files_upload_v2(
        channel=channel_id,
        file=caminho,
        title=f"Relatório Chamados {agora}.csv",
        initial_comment="📎 Aqui está seu relatório CSV."
    )

# 📤 Exportar PDF
def exportar_pdf(client, user_id, data_inicio=None, data_fim=None):
    chamados = buscar_chamados(data_inicio, data_fim)

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado no período.")
        return

    agora = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho = f"/tmp/chamados_{agora}.pdf"
    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    estilos = getSampleStyleSheet()
    elementos = []

    # Adiciona logo
    logo_url = "https://raw.githubusercontent.com/jflrealty/images/main/JFL_logotipo_completo.jpg"
    try:
        img_data = urllib.request.urlopen(logo_url).read()
        img_io = io.BytesIO(img_data)
        logo = Image(img_io)
        logo._restrictSize(7*inch, 2*inch)
        elementos.append(logo)
        elementos.append(Spacer(1, 20))
    except Exception as e:
        print(f"❌ Erro ao carregar logo:", e)

    elementos.append(Paragraph(f"📋 Relatório de Chamados - {datetime.now().strftime('%d/%m/%Y')}", estilos["Heading2"]))
    elementos.append(Spacer(1, 20))

    # Cabeçalho
    dados = [[
        "ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade",
        "Valor", "Responsável", "Solicitante", "Status", "SLA", "Histórico", "Motivo Cancelamento"
    ]]

    for c in chamados:
        valor = f"R$ {c.valor_locacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if c.valor_locacao else ""
        historico = ajustar_historico(c.historico_reaberturas)
        sla_formatado = "🟢 No Prazo" if c.sla_status == "dentro do prazo" else "🔴 Vencido"
        dados.append([
            c.id,
            c.tipo_ticket,
            c.tipo_contrato,
            c.locatario,
            c.empreendimento,
            c.unidade_metragem,
            valor,
            get_nome_slack(c.responsavel),
            get_nome_slack(c.solicitante),
            c.status.upper(),
            sla_formatado,
            historico,
            c.motivo_cancelamento or "–"
        ])

    tabela = Table(dados, repeatRows=1, colWidths=[30, 60, 60, 80, 60, 50, 50, 60, 60, 50, 30, 150, 100])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
    ]))

    elementos.append(tabela)
    doc.build(elementos)

    response = client.conversations_open(users=user_id)
    channel_id = response["channel"]["id"]
    client.files_upload_v2(
        channel=channel_id,
        file=caminho,
        title=f"Relatório Chamados {agora}.pdf",
        initial_comment="📎 Aqui está seu relatório PDF."
    )

# ⏰ Verificar SLA vencido
def verificar_sla_vencido():
    db = SessionLocal()
    agora = datetime.now()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise"]),
        OrdemServico.sla_limite < agora,
        OrdemServico.sla_status == "dentro do prazo"
    ).all()
    for chamado in chamados:
        chamado.sla_status = "fora do prazo"
        db.commit()
    db.close()

# 🔔 Lembrar chamados vencidos
def lembrar_chamados_vencidos(client):
    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(
        OrdemServico.status.in_(["aberto", "em análise"]),
        OrdemServico.sla_status == "fora do prazo"
    ).all()
    for chamado in chamados:
        client.chat_postMessage(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            thread_ts=chamado.thread_ts,
            text=f"🔔 *Lembrete:* <@{chamado.responsavel}> o chamado ID *{chamado.id}* ainda está vencido! 🚨"
        )
    db.close()
