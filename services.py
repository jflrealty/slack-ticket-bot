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

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

client_slack = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# 🧠 Buscar nome real do usuário no Slack
def get_nome_slack(user_id):
    if not user_id or not user_id.startswith("U"):
        return user_id  # Retorna como está se não for Slack ID (ex: login, e-mail, etc.)

    try:
        user_info = client_slack.users_info(user=user_id)
        return user_info["user"]["real_name"]
    except Exception as e:
        print(f"❌ Erro ao buscar nome do usuário {user_id}: {e}")
        return user_id

# 🔧 Função para montar o modal
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
                            for opt in ["Lista de Espera", "Pré bloqueio", "Reserva", "Aditivo", "Prorrogação", "Saída Antecipada", "Saída Confirmada", "Background Check"]],
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
                            for opt in ["Short Stay", "Temporada", "Long Stay", "Comodato", "Cortesia"]],
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
                    {"text": {"type": "plain_text", "text": "Reservas"}, "value": "S08STJCNMHR"}
                ]
            },
            "label": {"type": "plain_text", "text": "Responsável"}
        }
    ]

# 🧾 Criar novo chamado
def criar_ordem_servico(data, thread_ts=None, canal_id=None):
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
            thread_ts=thread_ts,
            canal_id=canal_id
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

# Buscar chamados
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

# 📋 Exportar CSV
def enviar_relatorio(client, user_id, data_inicio=None, data_fim=None):
    chamados = buscar_chamados(data_inicio, data_fim)

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado para exportar.")
        return

    agora = datetime.now().strftime("%Y%m%d")
    caminho = f"/tmp/chamados_{agora}.csv"

    def formatar_data(data):
        return data.strftime("%d/%m/%Y") if data else "–"

    def formatar_valor(valor):
        try:
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "–"

    def resolver_nome(id_ou_grupo):
        if not id_ou_grupo:
            return "–"
        if id_ou_grupo == "S08STJCNMHR":
            return "Reservas"
        return get_nome_slack(id_ou_grupo)

    with open(caminho, mode="w", newline="", encoding="utf-8-sig") as arquivo_csv:
        writer = csv.writer(arquivo_csv)
        writer.writerow([
            "ID", "Tipo", "Contrato", "Locatário", "Moradores", "Empreendimento", "Unidade",
            "Data Entrada", "Data Saída", "Valor", "Responsável", "Solicitante",
            "Status", "Aberto em", "SLA", "Histórico Reaberturas"
        ])
        for c in chamados:
            writer.writerow([
                c.id,
                c.tipo_ticket or "–",
                c.tipo_contrato or "–",
                c.locatario or "–",
                c.moradores or "–",
                c.empreendimento or "–",
                c.unidade_metragem or "–",
                formatar_data(c.data_entrada),
                formatar_data(c.data_saida),
                formatar_valor(c.valor_locacao),
                resolver_nome(c.responsavel),
                resolver_nome(c.solicitante),
                c.status or "–",
                formatar_data(c.data_abertura),
                c.sla_status or "–",
                c.historico_reaberturas or "–"
            ])

    response = client.conversations_open(users=user_id)
    channel_id = response["channel"]["id"]

    client.files_upload_v2(
        channel=channel_id,
        file=caminho,
        title=f"Relatório de Chamados - {agora}",
        initial_comment="📎 Aqui está seu relatório de chamados."
    )
# 📤 Exportar PDF com logo JFL e histórico
def exportar_pdf(client, user_id, data_inicio=None, data_fim=None):
    db = SessionLocal()
    chamados = buscar_chamados(data_inicio, data_fim)

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="❌ Nenhum chamado encontrado para exportar.")
        return

    agora = datetime.now().strftime("%Y%m%d%")
    caminho = f"/tmp/chamados_{agora}.pdf"

    doc = SimpleDocTemplate(caminho, pagesize=landscape(A4))
    estilos = getSampleStyleSheet()
    elementos = []

    logo_url = "https://raw.githubusercontent.com/jflrealty/images/main/JFL_logotipo_completo.jpg"
    try:
        img_data = urllib.request.urlopen(logo_url).read()
        img_io = io.BytesIO(img_data)
        logo = Image(img_io)
        logo._restrictSize(5*inch, 1*inch)
        elementos.append(logo)
        elementos.append(Spacer(1, 12))
    except Exception as e:
        print(f"❌ Erro ao carregar logo: {e}")

    elementos.append(Paragraph(f"📋 Relatório de Chamados - {datetime.now().strftime('%d/%m/%Y')}", estilos["Heading2"]))
    elementos.append(Spacer(1, 12))

    dados = [[
        "ID", "Tipo", "Contrato", "Locatário", "Empreendimento", "Unidade",
        "Valor", "Responsável", "Solicitante", "Status", "SLA", "Histórico"
    ]]

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
            get_nome_slack(c.solicitante),
            c.status,
            c.data_abertura.strftime("%d/%m/%Y"),
            "🔴" if c.sla_status == "fora do prazo" else "🟢",
            c.historico_reaberturas or "–"
        ])

    tabela = Table(dados, repeatRows=1, colWidths=[
        0, 70, 70, 80, 70, 60, 50, 70, 70, 50, 60, 30, 130
    ])

    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
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
        initial_comment="📎 Aqui está seu relatório em PDF."
    )

# 📋 Exibir lista de chamados do usuário
def exibir_lista(client, user_id):
    db = SessionLocal()
    chamados = db.query(OrdemServico).filter(OrdemServico.solicitante == user_id).order_by(
        OrdemServico.status, OrdemServico.data_abertura.desc()).all()
    db.close()

    if not chamados:
        client.chat_postEphemeral(channel=user_id, user=user_id, text="✅ Você não possui chamados registrados.")
        return

    abertos, em_analise, fechados = [], [], []

    for c in chamados:
        sla_emoji = "🔴" if c.sla_status == "fora do prazo" else "🟢"
        linha = f"{sla_emoji} ID {c.id} | {c.empreendimento} | {c.tipo_ticket} | Resp: <@{c.responsavel}>"
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

    client.chat_postEphemeral(channel=user_id, user=user_id, text=texto)

# ⏰ Verificar chamados vencidos
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

# 🔔 Lembrar responsáveis sobre chamados vencidos
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

# 📄 Formatar mensagem bonitinha
def formatar_mensagem_chamado(data, user_id):
    def formatar(valor):
        if not valor or (isinstance(valor, str) and valor.strip() == ""):
            return "–"
        if isinstance(valor, str) and valor.startswith("S"):  # grupo Slack
            return f"<!subteam^{valor}>"
        if isinstance(valor, str) and valor.startswith("U"):  # usuário Slack
            return f"<@{valor}>"
        return str(valor)

    valor_raw = data.get("valor_locacao")
    valor_formatado = "–"
    try:
        if isinstance(valor_raw, (int, float)):
            valor_formatado = f"R$ {valor_raw:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif isinstance(valor_raw, str):
            valor_float = float(valor_raw.replace("R$", "").replace(".", "").replace(",", ".").strip())
            valor_formatado = f"R$ {valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        valor_formatado = str(valor_raw) if valor_raw else "–"

    return (
        f"*Tipo:* {formatar(data.get('tipo_ticket'))}\n"
        f"*Contrato:* {formatar(data.get('tipo_contrato'))}\n"
        f"*Locatário:* {formatar(data.get('locatario'))}\n"
        f"*Moradores:* {formatar(data.get('moradores'))}\n"
        f"*Empreendimento:* {formatar(data.get('empreendimento'))}\n"
        f"*Unidade:* {formatar(data.get('unidade_metragem'))}\n"
        f"*Entrada:* {formatar(data.get('data_entrada').strftime('%d/%m/%Y') if data.get('data_entrada') else '–')}\n"
        f"*Saída:* {formatar(data.get('data_saida').strftime('%d/%m/%Y') if data.get('data_saida') else '–')}\n"
        f"*Valor:* {valor_formatado}\n"
        f"*Responsável:* {formatar(data.get('responsavel'))}\n"
        f"*Solicitante:* <@{user_id}>"
    )
    
from database import SessionLocal
from models import OrdemServico
from datetime import datetime
import os

# 🔄 Capturar chamado
def capturar_chamado(client, body):
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]
    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()

    if not chamado:
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user_id, text="❌ Chamado não encontrado.")
        db.close()
        return

    if chamado.status != "aberto":
        client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text=f"⚠️ O chamado já está em status *{chamado.status}*. Não é possível capturar."
        )
        db.close()
        return

    chamado.status = "em análise"
    chamado.responsavel = user_id
    chamado.data_captura = datetime.now()
    db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"🔄 Chamado capturado por <@{user_id}>!"
    )

# ✅ Finalizar chamado
def finalizar_chamado(client, body):
    ts = body["message"]["ts"]
    user_id = body["user"]["id"]
    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()

    if not chamado:
        client.chat_postEphemeral(channel=body["channel"]["id"], user=user_id, text="❌ Chamado não encontrado.")
        db.close()
        return

    if chamado.status == "fechado":
        client.chat_postEphemeral(
            channel=body["channel"]["id"],
            user=user_id,
            text="⚠️ Esse chamado já está *fechado*. Nenhuma ação realizada."
        )
        db.close()
        return

    chamado.status = "fechado"
    chamado.data_fechamento = datetime.now()
    db.commit()
    db.close()

    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=ts,
        text=f"✅ Chamado finalizado por <@{user_id}>!"
    )

# ♻️ Abrir modal de reabertura
def abrir_modal_reabertura(client, body):
    ts = body["message"]["ts"]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "reabrir_chamado_modal",
            "title": {"type": "plain_text", "text": "Reabrir Chamado"},
            "submit": {"type": "plain_text", "text": "Salvar"},
            "private_metadata": ts,
            "blocks": [
                {
                    "type": "input",
                    "block_id": "novo_tipo_ticket",
                    "element": {
                        "type": "static_select",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "Escolha o novo tipo de ticket"},
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["Reserva", "Lista de Espera", "Pré bloqueio", "Prorrogação", "Aditivo"]]
                    },
                    "label": {"type": "plain_text", "text": "Novo Tipo de Ticket"}
                }
            ]
        }
    )

def abrir_modal_edicao(client, trigger_id, thread_ts):
    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == thread_ts).first()
    db.close()
    if not chamado:
        return

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "editar_chamado_modal",
            "title": {"type": "plain_text", "text": "Editar Chamado"},
            "submit": {"type": "plain_text", "text": "Salvar"},
            "private_metadata": thread_ts,
            "blocks": [
                {
                    "type": "section",
                    "block_id": "tipo_ticket",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Tipo de Ticket:* `{chamado.tipo_ticket}` (não editável)"
                    }
                },
                {
                    "type": "input",
                    "block_id": "tipo_contrato",
                    "element": {
                        "type": "static_select",
                        "placeholder": {"type": "plain_text", "text": "Escolha"},
                        "options": [{"text": {"type": "plain_text", "text": opt}, "value": opt}
                                    for opt in ["Short Stay", "Temporada", "Long Stay", "Comodato"]],
                        "initial_option": {
                            "text": {"type": "plain_text", "text": chamado.tipo_contrato},
                            "value": chamado.tipo_contrato
                    } if chamado.tipo_contrato else None
                },
                "label": {"type": "plain_text", "text": "Tipo de Contrato"}
                },
                {
                    "type": "input",
                    "block_id": "locatario",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "initial_value": chamado.locatario
                    },
                    "label": {"type": "plain_text", "text": "Locatário"}
                },
                {
                    "type": "input",
                    "block_id": "moradores",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "initial_value": chamado.moradores
                    },
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
                        "initial_option": {
                        "text": {"type": "plain_text", "text": chamado.empreendimento},
                        "value": chamado.empreendimento
                    } if chamado.empreendimento else None
                },
                        "label": {"type": "plain_text", "text": "Empreendimento"}
                },
                {
                    "type": "input",
                    "block_id": "unidade_metragem",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "initial_value": chamado.unidade_metragem
                    },
                    "label": {"type": "plain_text", "text": "Unidade e Metragem"}
                },
                {
                    "type": "input",
                    "block_id": "valor_locacao",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "initial_value": str(chamado.valor_locacao or "")
                    },
                    "label": {"type": "plain_text", "text": "Valor da Locação"}
                }
            ]
        }
    )

# ♻️ Reabrir chamado
def reabrir_chamado(client, body, view):
    novo_tipo = view["state"]["values"]["novo_tipo_ticket"]["value"]["selected_option"]["value"]
    ts = view["private_metadata"]
    user_id = body["user"]["id"]

    db = SessionLocal()
    chamado = db.query(OrdemServico).filter(OrdemServico.thread_ts == ts).first()

    if chamado:
        chamado.tipo_ticket = novo_tipo
        chamado.status = "aberto"
        chamado.data_captura = None
        chamado.data_fechamento = None
        chamado.responsavel = None

        now = datetime.now().strftime("%Y-%m-%d")
        nome_real = get_nome_slack(user_id)
        novo_historico = f"[{now}] {nome_real} reabriu para *{novo_tipo}*\n"
        chamado.historico_reaberturas = novo_historico

        canal_id = chamado.canal_id
        thread_ts = chamado.thread_ts

        db.commit()
        db.close()

        # ✅ Posta confirmação apenas
        client.chat_postMessage(
            channel=canal_id,
            thread_ts=thread_ts,
            text=f"♻️ Chamado reaberto por <@{user_id}>!\nNovo Tipo de Ticket: *{novo_tipo}*"
        )
    else:
        db.close()
        client.chat_postEphemeral(
            channel=os.getenv("SLACK_CANAL_CHAMADOS", "#comercial"),
            user=user_id,
            text="❌ Chamado não encontrado para reabertura."
        )

def ajustar_historico(texto):
    if not texto:
        return "–"
    palavras = texto.split()
    for palavra in palavras:
        if palavra.startswith("<@") and palavra.endswith(">"):
            user_id = palavra[2:-1]
            nome = get_nome_slack(user_id)
            texto = texto.replace(palavra, nome)
    return texto

# 📦 Modal de exportação com filtro por data e tipo
def montar_blocos_exportacao():
    return [
        {
            "type": "input",
            "block_id": "tipo_arquivo",
            "label": {
                "type": "plain_text",
                "text": "Formato do Arquivo"
            },
            "element": {
                "type": "static_select",
                "action_id": "value",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Escolha o formato"
                },
                "options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "PDF"
                        },
                        "value": "pdf"
                    },
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "CSV"
                        },
                        "value": "csv"
                    },
                    {
                        "text": {
                            "type": "plain_text",
                            "text": "Excel"
                        },
                        "value": "xlsx"
                    }
                ]
            }
        },
        {
            "type": "input",
            "block_id": "data_inicio",
            "label": {
                "type": "plain_text",
                "text": "Data Inicial"
            },
            "element": {
                "type": "datepicker",
                "action_id": "value",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Escolha a data inicial"
                }
            }
        },
        {
            "type": "input",
            "block_id": "data_fim",
            "label": {
                "type": "plain_text",
                "text": "Data Final"
            },
            "element": {
                "type": "datepicker",
                "action_id": "value",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Escolha a data final"
                }
            }
        }
    ]
